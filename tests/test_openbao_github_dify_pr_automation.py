"""Dify PR automation gets only its installation-pinned, repository-scoped sets."""

from pathlib import Path
import re

from test_openbao_hatchet_killtest_policy_reach import render, role_defaults

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "roles/openbao/templates"
READ_SET = "dify-pr-automation-read"
WRITE_SET = "dify-pr-automation-write"
REPOSITORIES = ["pr-automation-fixture"]
READ_PERMISSIONS = {
    "contents": "read",
    "pull_requests": "read",
    "checks": "read",
    "statuses": "read",
    "metadata": "read",
}
WRITE_PERMISSIONS = {
    **READ_PERMISSIONS,
    "contents": "write",
    "pull_requests": "write",
}
ROLE_SET_NAMES = {
    "agent-pr-keeper": READ_SET,
    "agent-github-clerk": READ_SET,
    "agent-merge-steward": WRITE_SET,
}


def _variables():
    variables = role_defaults()
    variables["openbao_github_jacobpevans_ai_installation_id"] = "4242"
    return variables


def _render_policy(name, variables):
    source = (TEMPLATES / name).read_text(encoding="utf-8")
    return render(variables, source)


def test_permission_sets_share_one_repository_list_and_exact_maps():
    variables = _variables()
    sets = render(variables, "{{ openbao_github_dify_pr_automation_permission_sets }}")

    assert variables["openbao_dify_pr_automation_repositories"] == REPOSITORIES
    assert sets == [
        {
            "name": READ_SET,
            "tier": "agents",
            "installation_id": "4242",
            "repositories": REPOSITORIES,
            "permissions": READ_PERMISSIONS,
        },
        {
            "name": WRITE_SET,
            "tier": "agents",
            "installation_id": "4242",
            "repositories": REPOSITORIES,
            "permissions": WRITE_PERMISSIONS,
        },
    ]
    admin_sets = render(variables, "{{ openbao_github_admin_permission_sets }}")
    assert all(permission_set in admin_sets for permission_set in sets)
    mounted_sets = render(variables, "{{ openbao_github_permission_sets }}")
    assert all(
        next(permission_set for permission_set in mounted_sets
             if permission_set["name"] == expected["name"])["mount"]
        == variables["openbao_github_mount"]
        for expected in sets
    )


def test_unconfigured_owner_does_not_declare_unbounded_sets():
    variables = _variables()
    variables["openbao_github_jacobpevans_ai_installation_id"] = ""
    assert render(variables, "{{ openbao_github_dify_pr_automation_permission_sets }}") == []


def test_empty_repository_allowlist_does_not_declare_permission_sets():
    variables = _variables()
    variables["openbao_dify_pr_automation_repositories"] = []
    assert render(variables, "{{ openbao_github_dify_pr_automation_permission_sets }}") == []


def test_role_policies_mint_only_their_assigned_set():
    variables = _variables()
    policy_templates = {
        entry["name"]: entry["template"]
        for entry in render(variables, "{{ openbao_dify_agent_policies }}")
    }
    shared_read_template = "agent-dify-pr-automation-read-policy.hcl.j2"
    assert policy_templates["agent-pr-keeper"] == shared_read_template
    assert policy_templates["agent-github-clerk"] == shared_read_template
    policy_files = {
        "agent-pr-keeper": shared_read_template,
        "agent-github-clerk": shared_read_template,
        "agent-merge-steward": "agent-merge-steward-policy.hcl.j2",
    }
    for role_name, template_name in policy_files.items():
        policy = _render_policy(template_name, variables)
        expected_path = (
            f'{variables["openbao_github_mount"]}/token/{ROLE_SET_NAMES[role_name]}'
        )
        assert re.findall(r'^path "([^"]+)"', policy, flags=re.MULTILINE) == [expected_path]
        assert re.findall(r"capabilities = (.*)", policy) == ['["create", "update"]']


def test_only_new_roles_get_one_use_secret_ids_and_issuer_targets():
    variables = _variables()
    roles = render(variables, "{{ openbao_dify_agent_approles }}")
    for name in ROLE_SET_NAMES:
        role = next(role for role in roles if role["name"] == name)
        assert role["policy"] == name
        assert role["secret_id_ttl"] == "720h"
        assert role["secret_id_num_uses"] == 1
        assert role["token_ttl"] == "15m"
        assert role["token_max_ttl"] == "15m"
        assert role["secret_id_bound_cidrs"]
        assert role["manage_secret_id"] is False
    assert set(ROLE_SET_NAMES) <= set(
        render(variables, "{{ openbao_dify_secret_id_issuer_targets }}")
    )


def test_general_mint_policies_do_not_inherit_the_dedicated_sets():
    variables = _variables()
    for template_name in (
        "github-mint-policy.hcl.j2",
        "github-write-policy.hcl.j2",
        "ai-orchestrator-policy.hcl.j2",
        "github-admin-policy.hcl.j2",
    ):
        policy = _render_policy(template_name, variables)
        assert READ_SET not in policy
        assert WRITE_SET not in policy
