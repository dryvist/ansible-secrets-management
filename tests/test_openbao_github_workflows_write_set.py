"""The PR-automation workflows set is exactly three write permissions in the admin tier."""

from test_openbao_hatchet_eval_status_policy import _defaults, _render


def _sets(installation_id):
    github = _defaults("03-github-engine.yml")
    return _render(
        github["openbao_github_workflows_write_permission_sets"],
        {
            "openbao_github_workflows_write_set_name": github["openbao_github_workflows_write_set_name"],
            "openbao_github_workflows_write_permissions": github["openbao_github_workflows_write_permissions"],
            "openbao_github_jacobpevans_installation_id": installation_id,
        },
    )


def test_set_has_only_contents_pull_requests_and_workflows_write():
    github = _defaults("03-github-engine.yml")
    assert github["openbao_github_workflows_write_permissions"] == {
        "contents": "write",
        "pull_requests": "write",
        "workflows": "write",
    }
    assert _sets("4242") == [
        {
            "name": "jacobpevans-workflows-write",
            "tier": "admin",
            "installation_id": "4242",
            "permissions": github["openbao_github_workflows_write_permissions"],
        }
    ]
    assert "openbao_github_workflows_write_permission_sets" in github["openbao_github_admin_permission_sets"]


def test_set_is_absent_without_an_installation_id():
    assert _sets("") == []


def _template(name):
    return (_defaults.__globals__["DEFAULTS"].parents[1] / "templates" / name).read_text()


def test_only_the_admin_policy_selects_the_admin_tier():
    assert "selectattr('tier', 'equalto', 'admin')" in _template("github-admin-policy.hcl.j2")
    write_policy = _template("github-write-policy.hcl.j2")
    assert "selectattr('tier', 'equalto', 'write')" in write_policy
    assert "'admin'" not in write_policy
    assert "rejectattr('tier', 'equalto', 'admin')" in _template("ai-orchestrator-policy.hcl.j2")
