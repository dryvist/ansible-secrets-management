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


def _role_policy_list(role):
    if "token_policies" in role:
        return role["token_policies"]
    return [role["policy"]]


def _allowed_parameters(body):
    match = re.search(r"allowed_parameters\s*=\s*\{([^}]*)\}", body, re.DOTALL)
    assert match, "managed AppRole path has no allowed_parameters"
    return {
        name: json.loads(value)
        for name, value in re.findall(r'"([^"]+)"\s*=\s*(\[[^\n]*\])', match.group(1))
    }


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
    pinned = {
        "token_policies",
        "bind_secret_id",
        "secret_id_bound_cidrs",
        "token_bound_cidrs",
    }
    for name, body in root_paths.items():
        role = roles_by_name[name]
        cidr_csv = role.get("secret_id_bound_cidrs") or values[
            "openbao_approle_cidr_classes"
        ][values["openbao_approle_cidr_class_map"][name]]
        cidrs = [part.strip() for part in cidr_csv.split(",") if part.strip()]
        allowed = _allowed_parameters(body)
        expected = {
            "token_policies": [_role_policy_list(role)],
            "bind_secret_id": [
                role.get("bind_secret_id", values["openbao_approle_bind_secret_id"])
            ],
            "secret_id_bound_cidrs": [cidrs],
            "token_bound_cidrs": [cidrs],
        }
        assert {key: allowed[key] for key in pinned} == expected, name
        assert {key: allowed[key] for key in ancillary} == {
            key: [] for key in ancillary
        }, name
        assert set(allowed) == pinned | ancillary, name

    for name, body in policy_paths.items():
        role = roles_by_name[name]
        assert _allowed_parameters(body) == {
            "token_policies": [_role_policy_list(role)]
        }, name
        assert json.loads(
            re.search(r"required_parameters\s*=\s*(\[[^\n]*\])", body).group(1)
        ) == ["token_policies"], name

    for name, body in root_paths.items():
        required = json.loads(
            re.search(r"required_parameters\s*=\s*(\[[^\n]*\])", body).group(1)
        )
        role = roles_by_name[name]
        cidr_csv = role.get("secret_id_bound_cidrs") or values[
            "openbao_approle_cidr_classes"
        ][values["openbao_approle_cidr_class_map"][name]]
        expected_required = ["token_policies", "bind_secret_id"]
        if cidr_csv:
            expected_required.extend(["secret_id_bound_cidrs", "token_bound_cidrs"])
        assert required == expected_required, name
