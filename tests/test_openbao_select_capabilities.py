"""Every selected object needs a declared and live reconcile write grant."""

import pytest

from test_openbao_select import ROLE, condition, render, task


CAPABILITIES = ROLE / "tasks/init/selection-capabilities.yml"


@pytest.mark.parametrize("name", ["protected", "reconcile", "human-gated"])
def test_protected_declarations_fail_before_capability_reads(name):
    node = task("Require selected OpenBao objects to be manageable by this identity")
    outside = render(node["vars"]["_outside_grant"], {
        "openbao_object_targets": [{"name": name}],
        "openbao_select_candidates": [{"name": "apps"}],
    })
    assert not condition(node["ansible.builtin.assert"]["that"][0], {"_outside_grant": outside})
    message = render(node["ansible.builtin.assert"]["fail_msg"], {
        "_outside_grant": outside, "openbao_select_kind": "approles",
    })
    assert name in message and "human-gated path" in message


@pytest.mark.parametrize("envelope", [False, True])
def test_top_level_and_data_capability_envelopes(envelope):
    import json

    node = task("Resolve the selected-object capability response", CAPABILITIES)
    body = {"auth/approle/role/apps": ["read", "update"]}
    raw = json.dumps({"data": body} if envelope else body)
    parsed = render(node["vars"]["_body"], {"openbao_selected_capabilities_raw": {"stdout": raw}})
    caps = render(node["ansible.builtin.set_fact"]["openbao_selected_capabilities"], {"_body": parsed})
    assert caps["auth/approle/role/apps"] == ["read", "update"]


@pytest.mark.parametrize(("capabilities", "allowed"), [
    (["update"], True), (["root"], True), (["read"], False), (["deny"], False), ([], False),
])
def test_selected_object_without_a_live_write_grant_fails(capabilities, allowed):
    node = task("Require a live write grant on every selected OpenBao object", CAPABILITIES)
    item = {"name": "policies: apps", "path": "sys/policies/acl/apps", "capability": "update"}
    assert condition(node["ansible.builtin.assert"]["that"][0], {
        "item": item, "_capabilities": capabilities,
    }) is allowed
    if not allowed:
        message = render(node["ansible.builtin.assert"]["fail_msg"], {"item": item})
        assert "policies: apps" in message and "human-gated path" in message


def test_all_selected_write_endpoints_are_probed_before_phase_writes():
    node = task("Resolve the API paths addressed by selected OpenBao objects", CAPABILITIES)
    paths = render(node["ansible.builtin.set_fact"]["openbao_selected_paths"], {
        "openbao_select_profiles": {
            "approles": {"prefix": "auth/approle/role/", "suffixes": ["", "/policies"], "capability": "update"},
            "rotation_exempt": {"prefix": "", "suffixes": [""], "capability": "patch",
                                "name_pattern": ":", "name_replacement": "/metadata/"},
        },
        "openbao_selected_objects": {"approles": [{"name": "apps"}], "rotation_exempt": [{"name": "secret:key"}]},
    })
    assert [p["path"] for p in paths] == [
        "auth/approle/role/apps", "auth/approle/role/apps/policies", "secret/metadata/key",
    ]
    probe = task("Ask the server which selected objects this identity may actually write", CAPABILITIES)
    argv = render(probe["ansible.builtin.command"]["argv"], {"openbao_selected_paths": paths})
    assert argv[4:] == ["paths=" + p["path"] for p in paths]
    assert probe["no_log"] and not probe["changed_when"]

    preflight = task("Check every selected object's live reconcile grant before phase writes",
                     ROLE / "tasks/init/selection-preflight.yml")
    assert preflight["ansible.builtin.import_tasks"] == "selection-capabilities.yml"
    assert all(condition(c, {"openbao_select": {"policies": ["apps"]}, "openbao_reconcile_mode": True})
               for c in preflight["when"])
