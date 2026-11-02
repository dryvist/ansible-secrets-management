"""Policy sync unlock and elevation grants stay narrowly bounded."""

from openbao_reconcile_bounds_helpers import (
    ELEVATION_TASKS,
    ISSUER,
    POLICY_SYNC_UNLOCK,
    _render,
    _stanzas,
    _task,
    _templar,
    _trust,
    rendered_defaults,
)
import json
import re

from ansible.template import trust_as_template

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
