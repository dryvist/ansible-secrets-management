"""Rendered reconcile ACLs stay outside credentials it can mint or carry."""

import json
import os
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
POLICY_WRITE_TASKS = ROOT / "roles/openbao/tasks/init/08b-rbac-policy-writes.yml"
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
    templar = _templar(_trust(context))
    templar._loader.set_basedir(str(ROOT / "roles" / "openbao"))
    return templar.template(
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


def test_github_policy_pin_stanza_is_independent_of_app_environment(
    rendered_defaults, monkeypatch
):
    values, _approles, _policies = rendered_defaults
    mounts = _templar(_trust(values)).template(
        _trust(values["openbao_github_app_mounts"])
    )
    credentials = {
        "github": (
            "OPENBAO_GITHUB_EVERYDAY_APP_ID",
            "OPENBAO_GITHUB_EVERYDAY_APP_PRIVATE_KEY",
        ),
        "github-agents": (
            "OPENBAO_GITHUB_AGENTS_APP_ID",
            "OPENBAO_GITHUB_AGENTS_APP_PRIVATE_KEY",
        ),
        "github-hermes": (
            "OPENBAO_GITHUB_HERMES_APP_ID",
            "OPENBAO_GITHUB_HERMES_APP_PRIVATE_KEY",
        ),
        "github-work": (
            "OPENBAO_GITHUB_WORK_APP_ID",
            "OPENBAO_GITHUB_WORK_PRIVATE_KEY",
        ),
        "github-personal": (
            "OPENBAO_GITHUB_PERSONAL_APP_ID",
            "OPENBAO_GITHUB_PERSONAL_APP_PRIVATE_KEY",
        ),
        "github-enterprise-read": (
            "OPENBAO_GITHUB_ENTERPRISE_READ_APP_ID",
            "OPENBAO_GITHUB_ENTERPRISE_READ_PRIVATE_KEY",
        ),
        "github-enterprise": (
            "OPENBAO_GITHUB_ENTERPRISE_APP_ID",
            "OPENBAO_GITHUB_ENTERPRISE_PRIVATE_KEY",
        ),
        "github-runner": ("OPENBAO_GITHUB_RUNNER_APP_ID", "OPENBAO_GITHUB_RUNNER_APP_PRIVATE_KEY"),
    }
    env_names = [name for pair in credentials.values() for name in pair]

    def render_pin():
        context = dict(values)
        context["openbao_github_app_mounts"] = [
            {
                **mount,
                "app_id": os.environ.get(credentials[mount["mount"]][0], ""),
                "private_key": os.environ.get(credentials[mount["mount"]][1], ""),
            }
            for mount in mounts
        ]
        stanzas = dict(_stanzas(_render(RECONCILE, context)))
        return stanzas["sys/policies/acl/github-mount-config"]

    for name in env_names:
        monkeypatch.delenv(name, raising=False)
    unset = render_pin()

    for index, (app_id_env, private_key_env) in enumerate(credentials.values(), start=1):
        monkeypatch.setenv(app_id_env, str(100 + index))
        monkeypatch.setenv(private_key_env, f"fixture-private-key-{index}")
    set_values = render_pin()

    for index, (app_id_env, private_key_env) in enumerate(credentials.values(), start=1):
        monkeypatch.setenv(app_id_env, str(200 + index))
        monkeypatch.setenv(private_key_env, f"different-private-key-{index}")
    different_values = render_pin()

    assert unset == set_values == different_values
    assert "fixture-private-key" not in unset
    assert "different-private-key" not in unset


def _allowed_parameters(body):
    match = re.search(r"allowed_parameters\s*=\s*\{", body)
    assert match, "managed AppRole path has no allowed_parameters"
    start = match.end()
    depth = 1
    in_string = False
    escaped = False
    for end, char in enumerate(body[start:]):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                contents = body[start : start + end]
                break
    else:
        raise AssertionError("allowed_parameters block is not closed")

    allowed = {}
    decoder = json.JSONDecoder()
    position = 0
    while position < len(contents):
        entry = re.match(r'\s*"([^"]+)"\s*=\s*', contents[position:])
        if not entry:
            assert contents[position:].strip() == ""
            break
        name = entry.group(1)
        value_start = position + entry.end()
        value, value_length = decoder.raw_decode(contents[value_start:])
        allowed[name] = value
        position = value_start + value_length
    return allowed


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

    pinned_parameters = {
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
        pinned.update(pinned_parameters)
        assert set(allowed) == pinned, name
        assert all(
            isinstance(value, str) and "*" not in value
            for key in pinned
            for value in allowed[key]
        ), name
        assert not re.search(
            r'"(?:token_ttl|token_max_ttl|token_explicit_max_ttl|token_type|'
            r'secret_id_ttl|secret_id_num_uses)"\s*=\s*\[\]',
            body,
        ), name
        for key in pinned_parameters:
            assert allowed[key] == [parameters[key]], (name, key)

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
        expected_required.extend(
            [
                "token_ttl",
                "token_max_ttl",
                "token_explicit_max_ttl",
                "token_type",
                "secret_id_ttl",
                "secret_id_num_uses",
            ]
        )
        if values["openbao_approle_cli_parameters"][name]["secret_id_bound_cidrs"]:
            expected_required.extend(["secret_id_bound_cidrs", "token_bound_cidrs"])
        assert required == expected_required, name


def test_ansible_converge_writer_renders_exact_machine_bound_batch_parameters(rendered_defaults):
    values, _approles, _policies = rendered_defaults
    name = values["openbao_ansible_converge_writer_approle_name"]
    parameters = values["openbao_approle_cli_parameters"][name]

    assert (
        values["openbao_approle_cidr_class_map"][name],
        {key: parameters[key] for key in (
            "token_policies",
            "token_type",
            "token_ttl",
            "token_max_ttl",
        )},
    ) == (
        "machine",
        {
            "token_policies": "ansible-converge",
            "token_type": "batch",
            "token_ttl": "600s",
            "token_max_ttl": "600s",
        },
    )


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


def test_tofu_state_admin_policy_contains_only_the_two_state_key_paths(rendered_defaults):
    values, _approles, policies = rendered_defaults
    policy_name = values["openbao_tofu_state_admin_policy_name"]
    assert {
        "name": policy_name,
        "template": "tofu-state-admin-policy.hcl.j2",
    } in policies

    rendered = _render(TEMPLATES / "tofu-state-admin-policy.hcl.j2", values)
    admin = _render(TEMPLATES / "ai-admin-policy.hcl.j2", values)
    expected = {
        path
        for path, _body in _stanzas(admin)
        if path in {
            f"{values['openbao_transit_mount']}/datakey/plaintext/{values['openbao_tofu_state_transit_key']}",
            f"{values['openbao_transit_mount']}/decrypt/{values['openbao_tofu_state_transit_key']}",
        }
    }
    actual = []
    for path, body in _stanzas(rendered):
        capabilities = re.search(r"capabilities\s*=\s*\[([^]]*)\]", body)
        assert capabilities, path
        actual.append((path, tuple(re.findall(r'"([^"]+)"', capabilities.group(1)))))
    assert actual == [
        (f"{values['openbao_transit_mount']}/datakey/plaintext/{values['openbao_tofu_state_transit_key']}", ("update",)),
        (f"{values['openbao_transit_mount']}/decrypt/{values['openbao_tofu_state_transit_key']}", ("update",)),
    ]
    assert {path for path, _capabilities in actual} == expected


def test_reconcile_pins_the_two_human_gated_policy_bodies_and_attachments(rendered_defaults):
    values, approles, policies = rendered_defaults
    reconcile = _render(RECONCILE, values)
    policy_entries = {
        entry["name"]: entry for entry in policies
        if entry["name"] in {
            values["openbao_tofu_state_admin_policy_name"],
            values["openbao_github_mount_config_policy_name"],
        }
    }
    assert policy_entries == {
        values["openbao_tofu_state_admin_policy_name"]: {
            "name": values["openbao_tofu_state_admin_policy_name"],
            "template": "tofu-state-admin-policy.hcl.j2",
        },
        values["openbao_github_mount_config_policy_name"]: {
            "name": values["openbao_github_mount_config_policy_name"],
            "template": "github-mount-config-policy.hcl.j2",
        },
    }

    for policy_name, template_name in (
        (values["openbao_tofu_state_admin_policy_name"], "tofu-state-admin-policy.hcl.j2"),
        (values["openbao_github_mount_config_policy_name"], "github-mount-config-policy.hcl.j2"),
    ):
        path = f"sys/policies/acl/{policy_name}"
        body = next(body for candidate, body in _stanzas(reconcile) if candidate == path)
        # lookup('template') | trim removes the template terminator; the
        # command module's explicit stdin_add_newline appends one byte before
        # bao receives the policy body.
        policy_text = _render(TEMPLATES / template_name, values).strip() + "\n"
        assert _allowed_parameters(body) == {
            "policy": [policy_text]
        }
        required = re.search(
            r"(?m)^\s*required_parameters\s*=\s*(\[[^\n]*\])\s*$", body
        )
        assert required
        assert json.loads(required.group(1)) == ["policy"]

    policy_write_tasks = yaml.safe_load(POLICY_WRITE_TASKS.read_text(encoding="utf-8"))
    policy_write = next(
        task for task in policy_write_tasks
        if task.get("name") == "Write the RBAC policies that are missing or changed"
    )
    assert policy_write["ansible.builtin.command"]["stdin_add_newline"] is True

    expected_roles = {
        values["openbao_ai_admin_session_approle_name"]: values[
            "openbao_approle_cli_parameters"
        ][values["openbao_ai_admin_session_approle_name"]]["token_policies"].split(","),
        values["openbao_policy_sync_approle_name"]: values[
            "openbao_approle_cli_parameters"
        ][values["openbao_policy_sync_approle_name"]]["token_policies"].split(","),
    }
    assert values["openbao_tofu_state_admin_policy_name"] in expected_roles[
        values["openbao_ai_admin_session_approle_name"]
    ]
    assert values["openbao_github_mount_config_policy_name"] in expected_roles[
        values["openbao_policy_sync_approle_name"]
    ]
    role_declarations = {role["name"]: role for role in approles}
    assert values["openbao_ai_admin_session_approle_name"] in (
        values["openbao_reconcile_excluded_policies"]
    )
    assert values["openbao_policy_sync_policy_name"] in (
        values["openbao_reconcile_excluded_policies"]
    )
    managed_approle_names = {
        role["name"] for role in approles
        if "manage_secret_id" not in role
        and role["name"] not in values["openbao_reconcile_excluded_policies"]
    }
    for role_name, expected_policies in expected_roles.items():
        assert role_declarations[role_name]["manage_secret_id"] is False
        assert role_name not in managed_approle_names
        role_path = f"auth/approle/role/{role_name}"
        role_body = next(body for path, body in _stanzas(reconcile) if path == role_path)
        role_caps = re.search(r"capabilities\s*=\s*(\[[^\]]*\])", role_body)
        assert role_caps and json.loads(role_caps.group(1)) == ["read"]

        policies_path = f"{role_path}/policies"
        policies_body = next(
            body for path, body in _stanzas(reconcile) if path == policies_path
        )
        policy_caps = re.search(r"capabilities\s*=\s*(\[[^\]]*\])", policies_body)
        assert policy_caps and json.loads(policy_caps.group(1)) == ["update"]
        assert _allowed_parameters(policies_body) == {
            "token_policies": [",".join(expected_policies)]
        }
        required = re.search(
            r"(?m)^\s*required_parameters\s*=\s*(\[[^\n]*\])\s*$",
            policies_body,
        )
        assert required and json.loads(required.group(1)) == ["token_policies"]


def test_reconcile_does_not_grant_per_app_mount_configuration(rendered_defaults):
    values, _approles, _policies = rendered_defaults
    per_app_mounts = [
        {"mount": "github-public"},
        {"mount": "github-private"},
    ]
    context = dict(values, openbao_github_app_mounts=per_app_mounts)
    reconcile = _render(RECONCILE, context)
    paths = {path for path, _body in _stanzas(reconcile)}

    assert f"{values['openbao_github_mount']}/permissionset/*" in paths
    assert "github-agents/permissionset/agents-write" in paths
    for mount in per_app_mounts:
        assert f"{mount['mount']}/permissionset/*" in paths
    assert not any(path.startswith("sys/mounts/github-") for path in paths)
