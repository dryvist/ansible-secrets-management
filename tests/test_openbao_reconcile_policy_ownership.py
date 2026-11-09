"""Ownership and attachment boundaries in rendered reconcile policies."""

from openbao_reconcile_bounds_helpers import (
    ISSUER,
    RECONCILE,
    _assert_policy_bounds,
    _render,
    _role_policies,
    _stanzas,
    _templar,
    _trust,
    rendered_defaults,
)
import os

import pytest

def test_github_policy_pin_stanza_is_independent_of_app_environment(
    rendered_defaults, monkeypatch
):
    values, _approles, _policies = rendered_defaults
    values["openbao_platform_env"] = {
        "OPENBAO_GITHUB_PEPPER_INSTALLATION_ID": "fixture-installation"
    }
    monkeypatch.setenv("OPENBAO_GITHUB_PEPPER_APP_ID", "fixture-app-id")
    monkeypatch.setenv(
        "OPENBAO_GITHUB_PEPPER_APP_PRIVATE_KEY", "fixture-private-key"
    )
    monkeypatch.setenv("OPENBAO_GITHUB_PEPPER_REPOSITORY", "fixture-repo")
    monkeypatch.delenv("OPENBAO_GITHUB_PEPPER_REPOSITORIES", raising=False)
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
        "github-pepper": (
            "OPENBAO_GITHUB_PEPPER_APP_ID",
            "OPENBAO_GITHUB_PEPPER_APP_PRIVATE_KEY",
        ),
        "github-human-obsidian": (
            "OPENBAO_GITHUB_HUMAN_OBSIDIAN_APP_ID",
            "OPENBAO_GITHUB_HUMAN_OBSIDIAN_APP_PRIVATE_KEY",
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

def test_agent_workstation_effective_approle_policy_is_only_its_dedicated_policy(
    rendered_defaults,
):
    values, approles, policies = rendered_defaults
    role_name = values["openbao_agent_workstation_approle_name"]
    policy_name = values["openbao_agent_workstation_policy_name"]
    role = next(role for role in approles if role["name"] == role_name)

    assert _role_policies(role) == {policy_name}
    assert values["openbao_approle_cli_parameters"][role_name]["token_policies"] == (
        policy_name
    )
    assert {
        "name": policy_name,
        "template": "agent-workstation-policy.hcl.j2",
    } in policies
    assert policy_name not in values["openbao_reconcile_policy_excluded_names"]

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
