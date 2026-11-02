"""The reconcile policy limits its OpenTofu state access."""

from openbao_reconcile_bounds_helpers import (
    _capabilities, _render, _stanzas, rendered_defaults, TEMPLATES
)
import re

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
