"""Window service declarations render isolated, inert credential identities."""

import pytest

from openbao_reconcile_bounds_helpers import (
    RECONCILE,
    TEMPLATES,
    _capabilities,
    _render,
    _stanzas,
    _templar,
    _trust,
    rendered_defaults,
)
from test_openbao_rbac_policy_render import render as render_policies


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
