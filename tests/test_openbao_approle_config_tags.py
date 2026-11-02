"""Keep protected role reconciliation separate from secret_id issuance."""

from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "roles" / "openbao" / "tasks" / "init.yml"
APPROLE_TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "10-approles.yml"
APPROLE_BOUNDS_TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "10c-approle-ttl-bounds.yml"
SELECTOR_TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "select-single-object.yml"
DEFAULTS = ROOT / "roles" / "openbao" / "defaults" / "main" / "00-install-and-node.yml"
SITE_PLAY = ROOT / "playbooks" / "site" / "04a-openbao.yml"


def _named_task(tasks, name):
    return next(task for task in tasks if task.get("name") == name)


def _flatten(node):
    if isinstance(node, list):
        for value in node:
            yield from _flatten(value)
    elif isinstance(node, dict):
        if "name" in node:
            yield node
        for key in ("block", "rescue", "always", "tasks"):
            if key in node:
                yield from _flatten(node[key])


def _task(path, name):
    return next(
        task for task in yaml.safe_load(path.read_text(encoding="utf-8"))
        if task.get("name") == name
    )


def _trust(value):
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, list):
        return [_trust(v) for v in value]
    if isinstance(value, dict):
        return {k: _trust(v) for k, v in value.items()}
    return value


def _render(expr, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = _trust(variables)
    return templar.template(trust_as_template(expr))


def test_role_config_tag_does_not_select_secret_id_issuance():
    init_tasks = yaml.safe_load(INIT.read_text(encoding="utf-8"))
    config = _named_task(
        init_tasks, "Declare AppRoles and reconcile their policy and TTL bounds"
    )
    issuance = _named_task(init_tasks, "Issue per-call and stored AppRole credentials")

    assert config["ansible.builtin.import_tasks"] == "init/10-approles.yml"
    assert set(config["tags"]) == {"openbao_approle", "openbao_approle_config"}
    assert issuance["ansible.builtin.import_tasks"] == "init/10b-approle-secret-ids.yml"
    assert issuance["tags"] == ["openbao_approle"]

    declared_tasks = yaml.safe_load(APPROLE_TASKS.read_text(encoding="utf-8"))
    assert not any(
        task.get("ansible.builtin.import_tasks") == "10b-approle-secret-ids.yml"
        for task in declared_tasks
    )

    site_tasks = _flatten(yaml.safe_load(SITE_PLAY.read_text(encoding="utf-8")))
    include_role = _named_task(list(site_tasks), "Include openbao role")
    assert "openbao_approle_config" in include_role["tags"]


def test_approle_selector_is_single_exact_and_reconcile_rejected():
    defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
    assert defaults["openbao_approle_config_name"] == ""

    selection = _task(APPROLE_TASKS, "Select one AppRole config when an AppRole name was requested")
    assert selection["ansible.builtin.import_tasks"] == "select-single-object.yml"
    assert "openbao_manageable_approles" in selection["vars"]["openbao_single_object_candidates"]
    assert "openbao_approle_config_name" in selection["vars"]["openbao_single_object_selector"]

    helper = yaml.safe_load(SELECTOR_TASKS.read_text(encoding="utf-8"))
    expression = helper[1]["ansible.builtin.set_fact"]["openbao_single_object_targets"]
    candidates = [{"name": "apps"}, {"name": "ssh-ca"}]
    assert _render(expression, {
        "openbao_single_object_candidates": candidates,
        "openbao_single_object_selector": "ssh-ca",
    }) == [candidates[1]]

    reconcile_guard = helper[0]["ansible.builtin.assert"]["that"][0]
    templar = Templar(loader=DataLoader())
    templar.available_variables = _trust({"openbao_reconcile_mode": True})
    assert not templar.template(trust_as_template("{{ " + reconcile_guard + " }}"))


def test_only_selected_approle_is_read_and_reconciled_with_complete_parameters():
    read = _task(APPROLE_TASKS, "Check whether each AppRole already exists")
    create = _task(APPROLE_TASKS, "Create the missing AppRoles bound to their policy")
    policy = _task(APPROLE_TASKS, "Reconcile token_policies on existing AppRoles")
    bounds = _task(APPROLE_BOUNDS_TASKS, "Reconcile AppRole TTL and token bounds on existing AppRoles")
    targets = [{"name": "apps"}]
    all_roles = [{"name": "apps"}, {"name": "ssh-ca"}]
    check_results = [{"item": targets[0], "rc": 0}]

    selfcheck = _render(read["loop"], {
        "openbao_approle_config_targets": targets,
        "openbao_manageable_approles": all_roles,
    })
    assert selfcheck == targets
    all_checks = [{"item": role, "rc": 0} for role in all_roles]
    assert _render(read["loop"], {"openbao_manageable_approles": all_roles}) == all_roles
    for task in (create, policy, bounds):
        assert _render(task["loop"], {
            "openbao_approle_config_targets": targets,
            "openbao_manageable_approles": all_roles,
            "openbao_approle_checks": {"results": check_results},
        }) == [[targets[0], check_results[0]]]
        assert _render(task["loop"], {
            "openbao_manageable_approles": all_roles,
            "openbao_approle_checks": {"results": all_checks},
        }) == [[role, result] for role, result in zip(all_roles, all_checks)]

    fields = {
        "token_policies", "bind_secret_id", "token_ttl", "token_max_ttl",
        "token_explicit_max_ttl", "token_type", "secret_id_ttl",
        "secret_id_num_uses", "secret_id_bound_cidrs", "token_bound_cidrs",
    }
    for task in (create, bounds):
        command = task["ansible.builtin.command"]["cmd"]
        assert fields.issubset({field for field in fields if field in command})

    all_tasks = yaml.safe_load(APPROLE_TASKS.read_text(encoding="utf-8"))
    undeclared_index = next(
        i for i, task in enumerate(all_tasks)
        if task.get("name") == "Assert every live AppRole is either declared or a named exception"
    )
    selection_index = next(
        i for i, task in enumerate(all_tasks)
        if task.get("name") == "Select one AppRole config when an AppRole name was requested"
    )
    assert selection_index < undeclared_index


def test_selected_approle_still_runs_global_cidr_assertions_and_denied_read_guard():
    tasks = yaml.safe_load(APPROLE_TASKS.read_text(encoding="utf-8"))
    names = {task.get("name") for task in tasks}
    assert "Assert every CIDR class in use has been supplied" in names
    assert "Assert the sandbox-agent CIDRs are configured" in names
    assert "FAIL -- the existence check was DENIED, so absence cannot be concluded" in names

    denied = _task(APPROLE_TASKS, "FAIL -- the existence check was DENIED, so absence cannot be concluded")
    create = _task(APPROLE_TASKS, "Create the missing AppRoles bound to their policy")
    assert "openbao_approle_checks.results" in denied["vars"]["_denied"]
    assert "not (item.1.stderr | default('') is search('403'))" in create["when"]
    assert not any(
        task.get("ansible.builtin.import_tasks") == "10b-approle-secret-ids.yml"
        for task in yaml.safe_load(APPROLE_TASKS.read_text(encoding="utf-8"))
    )
