"""Window service declarations render isolated, inert credential identities."""

import pytest
import time

from openbao_reconcile_bounds_helpers import (
    RECONCILE,
    TEMPLATES,
    _allowed_parameters,
    _capabilities,
    _render,
    _stanzas,
    _templar,
    _trust,
    rendered_defaults,
)
from test_openbao_rbac_policy_render import render as render_policies
from test_openbao_hatchet_killtest_policy_reach import _call, _dev_server

GUARD = TEMPLATES / "ai-admin-guard-policy.hcl.j2"
IDENTITY_FAMILIES = ["entity", "entity-alias", "group", "group-alias"]
DENIED_PATHS = [
    "sys/seal", "sys/seal/child", "sys/unseal", "sys/unseal/child",
    "sys/rekey", "sys/rekey/init", "sys/rekey/verify", "sys/rekey-recovery-key/init",
    "sys/generate-root/attempt", "sys/generate-root-token/attempt",
    "sys/generate-recovery-token/attempt", "sys/rotate", "sys/rotate/keyring",
    "sys/rotate/keyring/config", "sys/rotate/root/init", "sys/rotate/recovery/update",
    "sys/raw/core/keyring", "auth/token/create-orphan", "auth/token/create/fixture",
    "auth/token/roles/fixture", "auth/token/revoke-orphan",
    "auth/approle/role/window-github", "auth/approle/role/window-github/secret-id",
    "auth/approle/role/ordinary/secret-id", "auth/approle/role/ordinary/custom-secret-id",
    "auth/approle/role/ordinary", "auth/jwt/role/fixture",
] + [f"identity/{family}{suffix}"
     for family in IDENTITY_FAMILIES
     for suffix in ("", "/id/fixture", "/name/fixture", "/id/fixture/nested", "-fixture")]


def _session_policies(values):
    role = next(role for role in values["openbao_approles"]
                if role["name"] == values["openbao_ai_admin_session_approle_name"])
    return role["token_policies"] + ["default"]


@pytest.mark.parametrize("service_name", ["github"])
def test_service_role_scope_and_render(service_name, rendered_defaults):
    values, approles, policies = rendered_defaults
    services = _templar(_trust(values)).template(_trust(values["openbao_window_services"]))
    service = next(service for service in services if service["name"] == service_name)
    name = f"window-{service_name}"
    roles = [role for role in approles if role["name"] == name]
    assert len(roles) == 1
    role = roles[0]
    assert role["policy"] == name
    assert role["manage_secret_id"] is False
    assert role["secret_id_num_uses"] == 1
    assert role["token_type"] == "batch"
    assert role["token_ttl"] == role["token_max_ttl"] == "15m"
    assert values["openbao_approle_cidr_class_map"][name] == "workstation"
    parameters = values["openbao_approle_cli_parameters"][name]
    assert parameters["token_bound_cidrs"] == values["openbao_workstation_cidrs"]
    policy = next(policy for policy in policies if policy["name"] == name)
    # Run the controller's actual nested template lookup with its item parameters.
    text = render_policies([policy])[0]["value"]
    stanzas = dict(_stanzas(text))
    assert service["credential_paths"]
    assert set(stanzas) == set(service["credential_paths"])
    assert all(path.startswith("github-admin/token/") for path in stanzas)
    assert all("*" not in path and "+" not in path for path in stanzas)
    assert all(_capabilities(body) == ["create", "update"] for body in stanzas.values())
    assert all('"*" = []' in body for body in stanzas.values())


def test_window_policy_and_role_are_outside_routine_reconcile(rendered_defaults):
    values, _, _ = rendered_defaults
    reconcile = dict(_stanzas(_render(RECONCILE, values)))
    assert "sys/policies/acl/window-github" not in reconcile
    assert "auth/approle/role/window-github" not in reconcile
    assert "auth/approle/role/window-github/secret-id" not in reconcile


def test_generic_template_does_not_grant_undeclared_paths(rendered_defaults):
    values, _, _ = rendered_defaults
    item = {"service": {"name": "fixture", "credential_paths": [], "scope": ["read"], "lifetime": "15m"}}
    text = _render(TEMPLATES / "window-service-policy.hcl.j2", dict(values, item=item))
    assert dict(_stanzas(text)) == {}


def test_guard_retains_protected_roles_and_policies(rendered_defaults):
    values, approles, _ = rendered_defaults
    stanzas = dict(_stanzas(_render(GUARD, values)))
    for role in approles:
        if role.get("manage_secret_id") is False or role["name"] == "admin":
            for suffix in ("", "/*"):
                assert _capabilities(stanzas[f"auth/approle/role/{role['name']}{suffix}"]) == ["deny"]
    for key in (
        "openbao_ai_admin_policy_name", "openbao_ai_admin_guard_policy_name",
        "openbao_human_unlock_policy_name", "openbao_human_unlock_untrusted_policy_name",
    ):
        for suffix in ("", "/*"):
            assert _capabilities(stanzas[f"sys/policies/acl/{values[key]}{suffix}"]) == ["deny"]
    for name in _session_policies(values) + ["window-github"]:
        for suffix in ("", "/*"):
            assert _capabilities(stanzas[f"sys/policies/acl/{name}{suffix}"]) == ["deny"]


def test_guard_pins_child_token_parameters(rendered_defaults):
    values, _, _ = rendered_defaults
    body = dict(_stanzas(_render(GUARD, values)))["auth/token/create"]
    assert _allowed_parameters(body) == {name: [value] for name, value in _request().items()}


@pytest.mark.parametrize("family", IDENTITY_FAMILIES)
def test_guard_denies_identity_family_and_descendants(family, rendered_defaults):
    values, _, _ = rendered_defaults
    stanzas = dict(_stanzas(_render(GUARD, values)))
    for suffix in ("", "/*", "*"):
        assert _capabilities(stanzas[f"identity/{family}{suffix}"]) == ["deny"]


def test_guard_protects_additional_attached_policy(rendered_defaults):
    values, approles, _ = rendered_defaults
    session = next(role for role in approles
                   if role["name"] == values["openbao_ai_admin_session_approle_name"])
    session["token_policies"] = session["token_policies"] + ["fixture-attached"]
    stanzas = dict(_stanzas(_render(GUARD, values)))
    for suffix in ("", "/*"):
        assert _capabilities(stanzas[f"sys/policies/acl/fixture-attached{suffix}"]) == ["deny"]


def test_no_declared_services_denies_child_issuance(rendered_defaults):
    values, _, _ = rendered_defaults
    text = _render(GUARD, dict(values, openbao_window_service_policies=[]))
    assert _capabilities(dict(_stanzas(text))["auth/token/create"]) == ["deny"]


@pytest.fixture
def window_server(rendered_defaults):
    values, _, policies = rendered_defaults
    window = next(policy for policy in policies if policy["name"] == "window-github")
    rendered = {
        values["openbao_ai_admin_policy_name"]: _render(TEMPLATES / "ai-admin-policy.hcl.j2", values),
        values["openbao_ai_admin_guard_policy_name"]: _render(GUARD, values),
        values["openbao_tofu_state_admin_policy_name"]: _render(TEMPLATES / "tofu-state-admin-policy.hcl.j2", values),
        window["name"]: _render(TEMPLATES / window["template"], dict(values, item=window)),
    }
    server, base = _dev_server()
    try:
        for name, text in rendered.items():
            assert _call(base, "root", "PUT", f"sys/policies/acl/{name}", {"policy": text})[0] == 204
        yield base, values, window
    finally:
        server.terminate()
        server.wait(timeout=30)


def _parent(base, values, ttl="1h"):
    status, result = _call(base, "root", "POST", "auth/token/create", {
        "policies": _session_policies(values),
        "ttl": ttl,
    })
    assert status == 200
    return result["auth"]["client_token"]


def _request():
    return {"policies": ["window-github"], "type": "batch", "ttl": "15m",
            "no_parent": False, "no_default_policy": True, "renewable": False}


def test_native_composition_denies_dangerous_and_protected_paths(window_server):
    base, values, _ = window_server
    parent = _parent(base, values)
    paths = DENIED_PATHS + [f"sys/policies/acl/{values[key]}" for key in (
        "openbao_ai_admin_policy_name", "openbao_ai_admin_guard_policy_name",
        "openbao_human_unlock_policy_name", "openbao_human_unlock_untrusted_policy_name",
    )] + [f"sys/policies/acl/{name}{suffix}"
          for name in _session_policies(values) + ["window-github"]
          for suffix in ("", "/nested", "/nested/descendant")]
    status, result = _call(base, "root", "POST", "sys/capabilities", {"token": parent, "paths": paths})
    assert status == 200
    assert {path: result[path] for path in paths} == dict.fromkeys(paths, ["deny"])
    status, result = _call(base, parent, "GET", "auth/token/lookup-self")
    assert status == 200, result if status != 200 else ""
    assert _call(base, parent, "POST", "auth/token/renew-self", {})[0] == 200


def test_native_session_cannot_write_attached_policies_or_widen_issuance(window_server):
    base, values, _ = window_server
    parent = _parent(base, values)
    policy = ('path "auth/token/create" { capabilities = ["create", "update", "sudo"] }\n'
              'path "sys/rekey/init" { capabilities = ["update", "sudo"] }')
    for name in _session_policies(values):
        for suffix in ("", "/nested", "/nested/descendant"):
            path = f"sys/policies/acl/{name}{suffix}"
            for method in ("POST", "PUT", "DELETE"):
                assert _call(base, parent, method, path, {"policy": policy})[0] == 403
    assert _call(base, parent, "POST", "auth/token/create", _request())[0] == 200
    assert _call(base, parent, "POST", "auth/token/create", _request() | {"ttl": "1h"})[0] == 403
    assert _call(base, parent, "POST", "auth/token/create", _request() | {"policies": ["ai-admin"]})[0] == 403


@pytest.mark.parametrize("family", ["entity", "group"])
def test_native_session_cannot_attach_policy_through_identity(family, window_server):
    base, values, _ = window_server
    parent = _parent(base, values)
    policy_name = "fixture-identity-policy"
    policy = 'path "sys/rekey/init" { capabilities = ["update", "sudo"] }'
    assert _call(base, parent, "PUT", f"sys/policies/acl/{policy_name}", {"policy": policy})[0] == 204
    path = f"identity/{family}"
    status, result = _call(base, "root", "POST", path, {"name": "fixture", "policies": []})
    assert status == 200
    identity_id = result["data"]["id"]
    request = {"name": "fixture", "policies": [policy_name]}
    for target in (path, f"{path}/id/{identity_id}", f"{path}/name/fixture"):
        for method in ("POST", "PUT", "DELETE"):
            assert _call(base, parent, method, target, request)[0] == 403
    assert _call(base, parent, "POST", path, request | {"name": "fixture-new"})[0] == 403
    status, result = _call(base, "root", "GET", f"{path}/id/{identity_id}")
    assert status == 200
    assert result["data"]["policies"] == []


def test_native_child_is_scoped_and_stops_with_parent(window_server):
    base, values, window = window_server
    parent = _parent(base, values)
    status, result = _call(base, parent, "POST", "auth/token/create", _request())
    assert status == 200, result if status != 200 else ""
    assert result["auth"]["token_type"] == "batch"
    assert result["auth"]["policies"] == ["window-github"]
    assert result["auth"]["renewable"] is False
    assert result["auth"]["lease_duration"] <= 900
    child = result["auth"]["client_token"]
    allowed = window["service"]["credential_paths"]
    denied = ["secret/data/apps/fixture", "secrets-external/data/fixture", "aws/sts/fixture",
              "github-admin/config", "github-admin/token", "github-admin/token/undeclared",
              "auth/token/create", "auth/token/create-orphan", "sys/seal"]
    status, result = _call(base, "root", "POST", "sys/capabilities", {"token": child, "paths": allowed + denied})
    assert status == 200
    assert all(result[path] == ["create", "update"] for path in allowed)
    assert all(result[path] == ["deny"] for path in denied)
    assert _call(base, "root", "POST", "auth/token/revoke", {"token": parent})[0] == 204
    assert _call(base, "root", "POST", "sys/capabilities", {"token": child, "paths": allowed})[0] == 400


def test_native_child_stops_when_remaining_window_expires(window_server):
    base, values, window = window_server
    parent = _parent(base, values, "2s")
    status, result = _call(base, parent, "POST", "auth/token/create", _request())
    assert status == 200, result if status != 200 else ""
    child = result["auth"]["client_token"]
    time.sleep(3)
    assert _call(base, "root", "POST", "sys/capabilities", {
        "token": child, "paths": window["service"]["credential_paths"],
    })[0] == 400


def test_native_issuance_rejects_policy_lifetime_and_orphan_overrides(window_server):
    base, values, _ = window_server
    parent = _parent(base, values)
    changes = [
        {"policies": ["root"]}, {"policies": []}, {"policies": ["ai-admin"]},
        {"policies": ["window-github", "default"]}, {"type": "service"},
        {"ttl": "16m"}, {"no_parent": True}, {"no_default_policy": False},
        {"renewable": True}, {"period": "1h"}, {"role_name": "fixture"},
        {"entity_alias": "fixture"},
    ]
    for change in changes:
        assert _call(base, parent, "POST", "auth/token/create", _request() | change)[0] == 403
    for parameter in _request():
        request = _request()
        del request[parameter]
        assert _call(base, parent, "POST", "auth/token/create", request)[0] == 403
