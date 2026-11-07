"""Shared fixtures and parsers for OpenBao reconcile bound tests."""

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

FLOW_LOCK = TEMPLATES / "flow-lock-policy.hcl.j2"

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
def rendered_defaults(monkeypatch, request):
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
        tofu_data=getattr(request, "param", {"agents": {}}),
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

def _capabilities(body):
    match = re.search(r"capabilities\s*=\s*(\[[^\]]*\])", body)
    assert match, body
    return json.loads(match.group(1))

def _effective_policy_union(policy_stanzas, target):
    matching = []
    for stanzas in policy_stanzas:
        for path, body in stanzas.items():
            pattern = re.escape(path).replace(r"\*", ".*").replace(r"\+", "[^/]+")
            if re.fullmatch(pattern, target):
                matching.append(set(_capabilities(body)))
    if any("deny" in capabilities for capabilities in matching):
        return {"deny"}
    return set().union(*matching) if matching else set()

def _render(template, values, *, policy_exclusions=None):
    context = dict(values)
    if policy_exclusions is not None:
        context["openbao_reconcile_policy_excluded_names"] = policy_exclusions
    loader = DataLoader()
    loader.set_basedir(str(ROOT / "roles" / "openbao"))
    # Mirrors Ansible's search path so a bare include in a converge template resolves.
    templar = Templar(loader=loader, variables=_trust(context)).copy_with_new_env(
        searchpath=[str(TEMPLATES), str(ROOT / "roles" / "openbao")],
    )
    return templar.template(
        trust_as_template(template.read_text(encoding="utf-8"))
    )

def _attached_stanzas(values, approles, policies, approle_name):
    role = next(role for role in approles if role["name"] == approle_name)
    policy_by_name = {policy["name"]: policy for policy in policies}
    stanzas = []
    for policy_name in _role_policies(role):
        policy = policy_by_name.get(policy_name)
        if policy is None:
            continue
        context = dict(values, item=policy)
        stanzas.append(dict(_stanzas(_render(TEMPLATES / policy["template"], context))))
    return stanzas

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

def _task(path, name):
    tasks = yaml.safe_load(path.read_text(encoding="utf-8"))
    return next(task for task in tasks if task.get("name") == name)

def _render_value(values, value, **overrides):
    return _templar(_trust(dict(values, **overrides))).template(_trust(value))

def _task_file(path):
    def flatten(tasks):
        for task in tasks or []:
            yield task
            for key in ("block", "rescue", "always"):
                yield from flatten(task.get(key, []))

    return list(flatten(yaml.safe_load(path.read_text(encoding="utf-8"))))

def _named_task(path, name):
    return next(task for task in _task_file(path) if task.get("name") == name)

def _include_details(task):
    modules = {
        module: module.rsplit(".", 1)[-1]
        for module in (
            "include_tasks",
            "ansible.builtin.include_tasks",
            "import_tasks",
            "ansible.builtin.import_tasks",
            "include_role",
            "ansible.builtin.include_role",
        )
    }
    matches = [(module, modules[module]) for module in modules if module in task]
    if not matches:
        return None
    if len(matches) != 1:
        raise AssertionError(
            f"task {task.get('name')!r} has multiple include/import actions"
        )

    module, action = matches[0]
    declaration = task[module]
    if isinstance(declaration, str):
        include = {"name" if action == "include_role" else "file": declaration}
    elif isinstance(declaration, dict):
        include = declaration
    else:
        raise AssertionError(
            f"cannot interpret {action} declaration in task {task.get('name')!r}"
        )

    target_key = "name" if action == "include_role" else "file"
    target = include.get(target_key)
    if not isinstance(target, str) or not target.strip():
        raise AssertionError(
            f"{action} task {task.get('name')!r} has no usable {target_key!r}"
        )

    task_vars = task.get("vars", {})
    if task_vars is None:
        task_vars = {}
    if not isinstance(task_vars, dict):
        raise AssertionError(
            f"vars on {action} task {task.get('name')!r} are not a mapping"
        )
    return action, include, task_vars

def _loop_values(values, expression):
    result = _render_value(values, expression)
    return yaml.safe_load(result) if isinstance(result, str) else result

def _command_text(task, values):
    command = task.get("ansible.builtin.command", {})
    text = command.get("cmd", " ".join(command.get("argv", [])))
    return _render_value(values, text) if text else ""
