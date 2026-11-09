"""The vault clerk gets one dormant-until-configured mount and one policy."""

import pytest
import yaml

from openbao_reconcile_bounds_helpers import (
    DEFAULTS,
    TEMPLATES,
    _capabilities,
    _render,
    _render_value,
    _stanzas,
)


@pytest.fixture
def vault_clerk_defaults(monkeypatch):
    monkeypatch.setenv("OPENBAO_TERRAKUBE_NETWORK_WORKSPACE", "fixture-network")
    monkeypatch.setenv("OPENBAO_TERRAKUBE_AWS_WORKSPACE", "fixture-aws")
    for name in (
        "OPENBAO_GITHUB_HUMAN_OBSIDIAN_APP_ID",
        "OPENBAO_GITHUB_HUMAN_OBSIDIAN_APP_PRIVATE_KEY",
        "OPENBAO_GITHUB_HUMAN_OBSIDIAN_REPOSITORIES",
    ):
        monkeypatch.delenv(name, raising=False)
    values = {}
    for path in sorted(DEFAULTS.glob("*.yml")):
        values.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    values.update(
        ansible_managed="test fixture",
        openbao_platform_env={},
        llm_router_key_catalog_facts={"openbao_router_key_catalog": {}},
    )
    return values


def _configure_vault_clerk_mount(
    monkeypatch, values, *, repositories="fixture-repo,fixture-repo-two"
):
    monkeypatch.setenv("OPENBAO_GITHUB_HUMAN_OBSIDIAN_APP_ID", "fixture-app-id")
    monkeypatch.setenv(
        "OPENBAO_GITHUB_HUMAN_OBSIDIAN_APP_PRIVATE_KEY", "fixture-private-key"
    )
    monkeypatch.setenv("OPENBAO_GITHUB_HUMAN_OBSIDIAN_REPOSITORIES", repositories)
    values["openbao_platform_env"]["OPENBAO_GITHUB_HUMAN_OBSIDIAN_INSTALLATION_ID"] = (
        "fixture-installation"
    )


def _vault_clerk_sets_and_mounts(values):
    sets = _render_value(
        values, "{{ openbao_github_human_obsidian_permission_sets }}"
    )
    mounts = _render_value(values, "{{ openbao_github_app_mounts }}")
    obsidian_mounts = [
        mount for mount in mounts if mount["mount"] == "github-human-obsidian"
    ]
    return sets, obsidian_mounts


def test_vault_clerk_mount_and_set_are_absent_without_inputs(vault_clerk_defaults):
    sets, mounts = _vault_clerk_sets_and_mounts(vault_clerk_defaults)
    assert sets == []
    assert mounts == []


@pytest.mark.parametrize(
    "missing_input",
    [
        "OPENBAO_GITHUB_HUMAN_OBSIDIAN_APP_ID",
        "OPENBAO_GITHUB_HUMAN_OBSIDIAN_APP_PRIVATE_KEY",
        "OPENBAO_GITHUB_HUMAN_OBSIDIAN_INSTALLATION_ID",
        "OPENBAO_GITHUB_HUMAN_OBSIDIAN_REPOSITORIES",
    ],
)
def test_vault_clerk_mount_is_absent_when_any_input_is_missing(
    vault_clerk_defaults, monkeypatch, missing_input
):
    _configure_vault_clerk_mount(monkeypatch, vault_clerk_defaults)
    if missing_input == "OPENBAO_GITHUB_HUMAN_OBSIDIAN_INSTALLATION_ID":
        vault_clerk_defaults["openbao_platform_env"].pop(missing_input)
    else:
        monkeypatch.delenv(missing_input, raising=False)

    sets, mounts = _vault_clerk_sets_and_mounts(vault_clerk_defaults)
    assert sets == []
    assert mounts == []


def test_vault_clerk_mount_is_absent_for_a_repository_value_with_a_slash(
    vault_clerk_defaults, monkeypatch
):
    _configure_vault_clerk_mount(
        monkeypatch, vault_clerk_defaults, repositories="fixture-owner/fixture-repo"
    )
    sets, mounts = _vault_clerk_sets_and_mounts(vault_clerk_defaults)
    assert sets == []
    assert mounts == []


def test_vault_clerk_mount_has_exactly_one_repository_scoped_write_set(
    vault_clerk_defaults, monkeypatch
):
    _configure_vault_clerk_mount(monkeypatch, vault_clerk_defaults)
    sets, mounts = _vault_clerk_sets_and_mounts(vault_clerk_defaults)

    assert sets == [
        {
            "name": "vault-clerk-write",
            "tier": "vault-clerk",
            "installation_id": "fixture-installation",
            "repositories": ["fixture-repo", "fixture-repo-two"],
            "permissions": {"contents": "write", "metadata": "read"},
        }
    ]
    assert len(mounts) == 1
    assert mounts[0]["app_id"] == "fixture-app-id"
    assert mounts[0]["private_key"] == "fixture-private-key"
    assert mounts[0]["permission_sets"] == sets

    registered_sets = _render_value(
        vault_clerk_defaults, "{{ openbao_github_permission_sets }}"
    )
    vault_clerk_registered = [
        permission_set
        for permission_set in registered_sets
        if permission_set["name"] == "vault-clerk-write"
    ]
    assert vault_clerk_registered == [dict(sets[0], mount="github-human-obsidian")]


def test_vault_clerk_policy_grants_only_its_named_set_on_github_mounts(
    vault_clerk_defaults, monkeypatch
):
    _configure_vault_clerk_mount(monkeypatch, vault_clerk_defaults)
    policy = _render(TEMPLATES / "vault-clerk-policy.hcl.j2", vault_clerk_defaults)
    stanzas = dict(_stanzas(policy))
    token_path = "github-human-obsidian/token/vault-clerk-write"
    github_paths = [
        path
        for path in stanzas
        if path == "github" or path.startswith("github-")
    ]

    assert list(stanzas) == [token_path]
    assert github_paths == [token_path]
    assert _capabilities(stanzas[token_path]) == ["create", "update"]
    assert "github-human-obsidian/token" not in stanzas


def test_other_identity_policies_do_not_grant_the_vault_clerk_token_path(
    vault_clerk_defaults, monkeypatch
):
    _configure_vault_clerk_mount(monkeypatch, vault_clerk_defaults)
    token_path = "github-human-obsidian/token/vault-clerk-write"
    for template_name in (
        "github-mint-policy.hcl.j2",
        "github-read-policy.hcl.j2",
        "github-write-policy.hcl.j2",
        "open-llm-policy.hcl.j2",
        "ai-orchestrator-policy.hcl.j2",
        "ai-public-policy.hcl.j2",
    ):
        policy = _render(TEMPLATES / template_name, vault_clerk_defaults)
        assert token_path not in dict(_stanzas(policy)), template_name

    agent_sets = _render_value(
        vault_clerk_defaults, "{{ openbao_github_agents_permission_sets }}"
    )
    assert all(item["name"] != "vault-clerk-write" for item in agent_sets)
