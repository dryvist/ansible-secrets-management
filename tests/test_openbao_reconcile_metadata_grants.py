"""Reconcile metadata grants stay aligned with declared defaults."""

from openbao_reconcile_bounds_helpers import (
    RECONCILE,
    _allowed_parameters,
    _capabilities,
    _render,
    _stanzas,
    _templar,
    _trust,
    rendered_defaults,
)
import re

def test_reconcile_metadata_grants_match_real_defaults(rendered_defaults):
    values, _approles, _policies = rendered_defaults
    templar = _templar(_trust(values))
    expected_metadata = {}

    rotation_exempt = templar.template(_trust(values["openbao_rotation_exempt"]))
    for entry in rotation_exempt:
        mount, path = entry.split(":", 1)
        expected_metadata[f"{mount}/metadata/{path}"] = {"read", "patch"}

    for name in (
        "openbao_roster_agent_generated_app_secrets",
        "openbao_caller_gateway_generated_app_secrets",
    ):
        seeded_apps = templar.template(_trust(values[name]))
        for app in seeded_apps:
            expected_metadata[
                f"{values['openbao_kv_mount']}/metadata/apps/{app}"
            ] = {"read", "patch"}

    agent_tier_mount = values["openbao_agent_tier_mount"]
    for reader in templar.template(_trust(values["openbao_app_agent_tier_readers"])):
        expected_metadata[
            f"{agent_tier_mount}/metadata/{reader['tier']}"
        ] = {"read"}
        if "login_path" in reader:
            expected_metadata[
                f"{agent_tier_mount}/metadata/{reader['login_path']}"
            ] = {"read"}

    reconcile_stanzas = dict(_stanzas(_render(RECONCILE, values)))
    actual_metadata_paths = {
        path for path in reconcile_stanzas if "/metadata/" in path
    }
    assert actual_metadata_paths == set(expected_metadata)
    for path, capabilities in expected_metadata.items():
        body = reconcile_stanzas[path]
        assert set(_capabilities(body)) == capabilities, path
        if "patch" in capabilities or "update" in capabilities:
            assert _allowed_parameters(body) == {"custom_metadata": []}, path
        else:
            assert not re.search(
                r"(?m)^\s*(?:allowed_parameters|denied_parameters|required_parameters)\s*=",
                body,
            ), path
