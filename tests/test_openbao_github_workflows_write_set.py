"""The PR-automation workflows sets are exactly three write permissions in the admin tier, one per installation."""

from test_openbao_hatchet_eval_status_policy import _defaults, _render


def _sets(installations):
    github = _defaults("03-github-engine.yml")
    return _render(
        github["openbao_github_workflows_write_permission_sets"],
        {
            "openbao_github_workflows_write_set_suffix": github["openbao_github_workflows_write_set_suffix"],
            "openbao_github_workflows_write_permissions": github["openbao_github_workflows_write_permissions"],
            "openbao_github_org_secrets_installations": installations,
        },
    )


def test_one_set_per_installation_with_only_three_write_permissions():
    github = _defaults("03-github-engine.yml")
    assert github["openbao_github_workflows_write_permissions"] == {
        "contents": "write",
        "pull_requests": "write",
        "workflows": "write",
    }
    sets = _sets([
        {"name": "owner-a", "installation_id": "4242"},
        {"name": "owner-b", "installation_id": "4343"},
    ])
    assert sets == [
        {
            "name": f"{name}-workflows-write",
            "tier": "admin",
            "installation_id": iid,
            "permissions": github["openbao_github_workflows_write_permissions"],
        }
        for name, iid in (("owner-a", "4242"), ("owner-b", "4343"))
    ]
    assert "openbao_github_workflows_write_permission_sets" in github["openbao_github_admin_permission_sets"]


def test_installation_without_an_id_gets_no_set():
    assert _sets([{"name": "owner-a", "installation_id": ""}]) == []


def test_sets_follow_the_shared_installation_list():
    github = _defaults("03-github-engine.yml")
    assert "openbao_github_org_secrets_installations" in github["openbao_github_workflows_write_permission_sets"]


def _template(name):
    return (_defaults.__globals__["DEFAULTS"].parents[1] / "templates" / name).read_text()


def test_only_the_admin_policy_selects_the_admin_tier_and_orchestrator_uses_allowlist():
    assert "selectattr('tier', 'equalto', 'admin')" in _template("github-admin-policy.hcl.j2")
    write_policy = _template("github-write-policy.hcl.j2")
    assert "selectattr('tier', 'equalto', 'write')" in write_policy
    assert "'admin'" not in write_policy
    orchestrator_policy = _template("ai-orchestrator-policy.hcl.j2")
    assert "selectattr('tier', 'defined')" in orchestrator_policy
    assert "selectattr('tier', 'in', openbao_ai_orchestrator_github_tiers)" in orchestrator_policy
    assert "rejectattr('tier'" not in orchestrator_policy
