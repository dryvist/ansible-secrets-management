"""Rendered reconcile ACLs stay outside credentials it can mint or carry."""

import json
import re
from pathlib import Path

import pytest
import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
TEMPLATES = ROOT / "roles/openbao/templates"
RECONCILE = TEMPLATES / "openbao-reconcile-policy.hcl.j2"
ISSUER = TEMPLATES / "approle-issuer-policy.hcl.j2"
POLICY_SYNC_UNLOCK = TEMPLATES / "policy-sync-unlock-policy.hcl.j2"
APPROLE_TASKS = ROOT / "roles/openbao/tasks/init/10-approles.yml"
TTL_TASKS = ROOT / "roles/openbao/tasks/init/10c-approle-ttl-bounds.yml"
ELEVATION_TASKS = ROOT / "roles/openbao/tasks/init/09e-authelia-elevation.yml"


def _trust(value):
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, list):
        return [_trust(item) for item in value]
    if isinstance(value, dict):
        return {name: _trust(item) for name, item in value.items()}
    return value


def _templar(values):
    templar = Templar(loader=DataLoader())
    templar.available_variables = values
    return templar


@pytest.fixture
def rendered_defaults(monkeypatch):
    for key, value in {
        "OPENBAO_TERRAKUBE_NETWORK_WORKSPACE": "fixture-network",
        "OPENBAO_TERRAKUBE_AWS_WORKSPACE": "fixture-aws",
        "OPENBAO_AI_API_KEY_MOUNT": "secret",
        "OPENBAO_AI_API_KEY_PATH_PREFIX": "fixture-provider-keys",
        "PROXMOX_SUBDOMAIN": "example.com",
    }.items():
        monkeypatch.setenv(key, value)

    values = {}
    for path in sorted(DEFAULTS.glob("*.yml")):
        values.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    values.update(
        tofu_data={"agents": {}},
        ansible_managed="Ansible managed",
        llm_router_key_catalog_facts={"openbao_router_key_catalog": {}},
        openbao_management_cidrs="192.0.2.0/24",
        openbao_workstation_cidrs="198.51.100.0/24",
        openbao_ci_cidrs="203.0.113.0/24",
        openbao_ssh_source_cidrs="192.0.2.0/24",
        openbao_sandbox_agent_cidrs="203.0.113.0/24",
    )
    templar = _templar(_trust(values))
    approles = templar.template(_trust(values["openbao_approles"]))
    policies = templar.template(_trust(values["openbao_policies"]))
    values.update(openbao_approles=approles, openbao_policies=policies)
    templar = _templar(_trust(values))
    for name in (
        "openbao_approle_cidr_classes",
        "openbao_approle_cidr_class_map",
        "openbao_reconcile_excluded_policies",
        "openbao_reconcile_policy_excluded_names",
        "openbao_retired_approles",
        "openbao_retired_policies",
    ):
        values[name] = templar.template(_trust(values[name]))
    values["openbao_approle_cli_parameters"] = templar.template(
        _trust(values["openbao_approle_cli_parameters"])
    )
    return values, approles, policies


def _stanzas(policy):
    for match in re.finditer(r'(?m)^path "([^"]+)" \{', policy):
        start = match.end()
        depth = 1
        for offset, char in enumerate(policy[start:]):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    yield match.group(1), policy[start : start + offset]
                    break


def _render(template, values, *, policy_exclusions=None):
    context = dict(values)
    if policy_exclusions is not None:
        context["openbao_reconcile_policy_excluded_names"] = policy_exclusions
    return _templar(_trust(context)).template(
        trust_as_template(template.read_text(encoding="utf-8"))
    )


def _writable_policy_names(rendered):
    writable = set()
    for path, body in _stanzas(rendered):
        if not path.startswith("sys/policies/acl/"):
            continue
        capabilities = re.search(r'capabilities\s*=\s*\[([^]]*)\]', body)
        if capabilities and '"update"' in capabilities.group(1):
            writable.add(path.removeprefix("sys/policies/acl/"))
    return writable


def _role_policies(role):
    if "token_policies" in role:
        return set(role["token_policies"])
    return {role["policy"]}


def _allowed_parameters(body):
    match = re.search(r"allowed_parameters\s*=\s*\{([^}]*)\}", body, re.DOTALL)
    assert match, "managed AppRole path has no allowed_parameters"
    return {
        name: json.loads(value)
        for name, value in re.findall(r'"([^"]+)"\s*=\s*(\[[^\n]*\])', match.group(1))
    }


def _task(path, name):
    tasks = yaml.safe_load(path.read_text(encoding="utf-8"))
    return next(task for task in tasks if task.get("name") == name)


def _render_task_command(task, values, role):
    live = {
        "data": {
            "secret_id_bound_cidrs": [],
            "token_bound_cidrs": [],
            "secret_id_ttl": 0,
            "secret_id_num_uses": 0,
            "token_ttl": 0,
            "token_max_ttl": 0,
            "token_explicit_max_ttl": 0,
            "token_type": "default",
        }
    }
    command = task["ansible.builtin.command"]["cmd"]
    context = dict(
        values,
        item=(role, {"rc": 0, "stdout": json.dumps(live)}),
        live=live["data"],
        approle_cli_parameters=values["openbao_approle_cli_parameters"][role["name"]],
    )
    task_vars = task.get("vars", {})
    if "approle_cli_parameters" in task_vars:
        assert task_vars["approle_cli_parameters"] == (
            "{{ openbao_approle_cli_parameters[item.0.name] }}"
        )
    referenced = dict.fromkeys(re.findall(r"{{\s*([A-Za-z_]\w*)", command))
    for name in referenced:
        if name in task_vars and name != "approle_cli_parameters":
            context[name] = _templar(_trust(context)).template(_trust(task_vars[name]))
    return _templar(_trust(context)).template(trust_as_template(command))


def _command_arguments(command):
    return dict(re.findall(r"(?:^|\s)([a-z_]+)=([^\s]+)", command))


def _assert_policy_bounds(reconcile, issuer, values, approles):
    writable = _writable_policy_names(reconcile)
    issuer_roles = {
        path.split("/")[3]
        for path, _body in _stanzas(issuer)
        if re.fullmatch(r"auth/approle/role/[^/]+/secret-id", path)
    }
    roles_by_name = {role["name"]: role for role in approles}
    plane = values["openbao_semaphore_approle_name"]
    protected = {
        policy
        for name in issuer_roles | {plane}
        for policy in _role_policies(roles_by_name[name])
    }
    overlap = writable & protected
    assert not overlap, f"reconcile can update attached policy names: {sorted(overlap)}"
    return writable, issuer_roles, protected


def test_rendered_policy_writes_exclude_issuer_and_plane_policies(rendered_defaults):
    values, approles, _policies = rendered_defaults
    reconcile = _render(RECONCILE, values)
    issuer = _render(ISSUER, values)
    writable, issuer_roles, protected = _assert_policy_bounds(
        reconcile, issuer, values, approles
    )

    flow_lock_role = values["openbao_flow_lock_approle_name"]
    flow_lock_policy = values["openbao_flow_lock_policy_name"]
    assert flow_lock_role in issuer_roles
    assert flow_lock_policy in protected
    assert flow_lock_policy not in writable
    policy_paths = [
        path for path, _body in _stanzas(reconcile)
        if path.startswith("sys/policies/acl/")
    ]
    assert all("*" not in path and "+" not in path for path in policy_paths)

    # Mutation check: putting flow-lock back in the writable policy set must
    # make the same rendered-output invariant fail.
    exclusions = values["openbao_reconcile_policy_excluded_names"]
    mutated = [name for name in exclusions if name != flow_lock_policy]
    mutated_reconcile = _render(RECONCILE, values, policy_exclusions=mutated)
    with pytest.raises(AssertionError, match=flow_lock_policy):
        _assert_policy_bounds(mutated_reconcile, issuer, values, approles)


def test_managed_approle_writes_pin_declared_policy_binding_and_cidrs(rendered_defaults):
    values, approles, _policies = rendered_defaults
    reconcile = _render(RECONCILE, values)
    roles_by_name = {role["name"]: role for role in approles}
    root_paths = {
        path.removeprefix("auth/approle/role/"): body
        for path, body in _stanzas(reconcile)
        if re.fullmatch(r"auth/approle/role/[^/]+", path)
        and '"create"' in body
        and '"update"' in body
    }
    policy_paths = {
        path.removeprefix("auth/approle/role/").removesuffix("/policies"): body
        for path, body in _stanzas(reconcile)
        if re.fullmatch(r"auth/approle/role/[^/]+/policies", path)
        and '"create"' in body
        and '"update"' in body
    }
    assert root_paths
    assert set(root_paths) == set(policy_paths)

    ancillary = {
        "token_ttl",
        "token_max_ttl",
        "token_explicit_max_ttl",
        "token_type",
        "secret_id_ttl",
        "secret_id_num_uses",
    }
    create_task = _task(APPROLE_TASKS, "Create the missing AppRoles bound to their policy")
    policy_task = _task(APPROLE_TASKS, "Reconcile token_policies on existing AppRoles")
    ttl_task = _task(TTL_TASKS, "Reconcile AppRole TTL and token bounds on existing AppRoles")
    for name, body in root_paths.items():
        role = roles_by_name[name]
        parameters = values["openbao_approle_cli_parameters"][name]
        allowed = _allowed_parameters(body)
        assert allowed["token_policies"] == [parameters["token_policies"]], name
        assert allowed["bind_secret_id"] == [parameters["bind_secret_id"]], name
        pinned = {"token_policies", "bind_secret_id"}
        if parameters["secret_id_bound_cidrs"]:
            pinned.update({"secret_id_bound_cidrs", "token_bound_cidrs"})
            assert allowed["secret_id_bound_cidrs"] == [parameters["secret_id_bound_cidrs"]], name
            assert allowed["token_bound_cidrs"] == [parameters["token_bound_cidrs"]], name
        assert set(allowed) == pinned | ancillary, name
        assert all(
            isinstance(value, str) and "*" not in value
            for key in pinned
            for value in allowed[key]
        ), name
        assert {key: allowed[key] for key in ancillary} == {
            key: [] for key in ancillary
        }, name

        for task in (create_task, ttl_task):
            sent = _command_arguments(_render_task_command(task, values, role))
            for key in pinned:
                assert sent[key].encode() == allowed[key][0].encode(), (name, task["name"], key)
            if not parameters["secret_id_bound_cidrs"]:
                assert not {"secret_id_bound_cidrs", "token_bound_cidrs"} & sent.keys(), name

    for name, body in policy_paths.items():
        role = roles_by_name[name]
        parameters = values["openbao_approle_cli_parameters"][name]
        allowed = _allowed_parameters(body)
        assert allowed == {"token_policies": [parameters["token_policies"]]}, name
        assert "*" not in allowed["token_policies"][0], name
        sent = _command_arguments(_render_task_command(policy_task, values, role))
        assert sent["token_policies"].encode() == allowed["token_policies"][0].encode(), name
        assert json.loads(
            re.search(r"required_parameters\s*=\s*(\[[^\n]*\])", body).group(1)
        ) == ["token_policies"], name

    for name, body in root_paths.items():
        required = json.loads(
            re.search(r"required_parameters\s*=\s*(\[[^\n]*\])", body).group(1)
        )
        role = roles_by_name[name]
        expected_required = ["token_policies", "bind_secret_id"]
        if values["openbao_approle_cli_parameters"][name]["secret_id_bound_cidrs"]:
            expected_required.extend(["secret_id_bound_cidrs", "token_bound_cidrs"])
        assert required == expected_required, name


def test_policy_sync_unlock_renders_only_its_four_exact_paths(rendered_defaults):
    values, _approles, policies = rendered_defaults
    policy_name = values["openbao_policy_sync_unlock_policy_name"]
    expected_entry = {
        "name": policy_name,
        "template": "policy-sync-unlock-policy.hcl.j2",
    }
    assert expected_entry in policies

    rendered = _render(POLICY_SYNC_UNLOCK, values)
    actual = []
    for path, body in _stanzas(rendered):
        capabilities = re.search(r"capabilities\s*=\s*\[([^]]*)\]", body)
        assert capabilities, path
        actual.append((path, tuple(re.findall(r'"([^"]+)"', capabilities.group(1)))))
    assert actual == [
        ("auth/approle/role/openbao-policy-sync/secret-id", ("create", "update")),
        ("auth/approle/role/openbao-policy-sync/role-id", ("read",)),
        ("sys/wrapping/wrap", ("update",)),
        ("auth/token/lookup-self", ("read",)),
    ]
    assert all("*" not in path and "+" not in path for path, _capabilities in actual)


def test_policy_sync_unlock_stays_out_of_reconcile_and_issuer_grants(rendered_defaults):
    values, _approles, _policies = rendered_defaults
    policy_name = values["openbao_policy_sync_unlock_policy_name"]
    assert policy_name in values["openbao_reconcile_excluded_policies"]

    issuer = _render(ISSUER, values)
    issuer_paths = [path for path, _body in _stanzas(issuer)]
    assert not any(policy_name in path for path in issuer_paths)
    assert not any(
        path == f"auth/approle/role/{values['openbao_policy_sync_approle_name']}/secret-id"
        for path in issuer_paths
    )


def test_policy_sync_elevation_role_has_one_policy_and_workstation_bounds(rendered_defaults):
    values, _approles, _policies = rendered_defaults
    roles = _templar(_trust(values)).template(_trust(values["openbao_elevate_roles"]))
    role = next(row for row in roles if row["name"] == "elevate-policy-sync")
    policy_name = values["openbao_policy_sync_unlock_policy_name"]
    assert role == {
        "name": "elevate-policy-sync",
        "audience": "bao-elevate-policy-sync",
        "policy": policy_name,
    }

    task = _task(ELEVATION_TASKS, "Reconcile the phone-approval JWT roles")
    workstation_class = ["workstation-range-one", "workstation-range-two"]
    def render_payload(elevation_role):
        context = dict(values)
        context["item"] = elevation_role
        context["openbao_elevate_subject"] = "operator-subject"
        context["openbao_approle_cidr_classes"] = {
            **values["openbao_approle_cidr_classes"],
            "workstation": ",".join(workstation_class),
        }
        return json.loads(
            _templar(_trust(context)).template(
                trust_as_template(task["ansible.builtin.command"]["stdin"])
            )
        )

    payload = render_payload(role)
    trusted_role = next(row for row in roles if row["name"] == "elevate-trusted")
    trusted_payload = render_payload(trusted_role)
    assert payload["token_policies"] == [policy_name]
    assert payload["token_bound_cidrs"] == trusted_payload["token_bound_cidrs"]
    assert payload["token_bound_cidrs"] == workstation_class
    for field in ("token_ttl", "token_max_ttl"):
        assert payload[field] == trusted_payload[field]
