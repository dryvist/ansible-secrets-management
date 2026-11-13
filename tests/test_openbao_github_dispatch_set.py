"""Workflow dispatch is confined to one configured installation and repository."""

import yaml
from jinja2 import Environment, FileSystemLoader

from test_openbao_hatchet_eval_status_policy import DEFAULTS, _defaults, _render


def _sets(owner, repository, installations):
    defaults = _defaults("03-github-engine.yml")
    return _render(
        defaults["openbao_github_dispatch_permission_sets"],
        {
            "openbao_github_dispatch_owner": owner,
            "openbao_github_dispatch_repository": repository,
            "openbao_github_dispatch_permissions": defaults["openbao_github_dispatch_permissions"],
            "openbao_github_org_secrets_installations": installations,
        },
    )


def _policy(sets):
    environment = Environment(loader=FileSystemLoader(DEFAULTS.parents[1] / "templates"))
    environment.filters["comment"] = lambda value: "# " + str(value)
    return environment.get_template("semaphore-policy.hcl.j2").render(
        ansible_managed="managed",
        openbao_kv_mount="secret",
        openbao_github_everyday_mount="github",
        openbao_github_mount="github-admin",
        openbao_semaphore_github_raw_read_permissions={},
        openbao_semaphore_github_read_permission_sets=[],
        openbao_github_dispatch_permission_sets=sets,
    )


def test_dispatch_set_is_scoped_to_mapped_installation_and_repository():
    defaults = _defaults("03-github-engine.yml")
    env = {"openbao_platform_env": {
        "OPENBAO_GITHUB_DISPATCH_OWNER": "example-org",
        "OPENBAO_GITHUB_DISPATCH_REPOSITORY": "example-repo",
    }}
    assert _render(defaults["openbao_github_dispatch_owner"], env) == "example-org"
    assert _render(defaults["openbao_github_dispatch_repository"], env) == "example-repo"
    installations = [{"name": "example-org", "installation_id": "4242"}]
    sets = _sets("example-org", "example-repo", installations)
    assert sets == [{
        "name": "workflow-dispatch",
        "tier": "agents",
        "installation_id": "4242",
        "repositories": ["example-repo"],
        "permissions": {"actions": "write", "metadata": "read"},
    }]
    assert "openbao_github_dispatch_permission_sets" in defaults["openbao_github_admin_permission_sets"]
    assert 'path "github-admin/token/workflow-dispatch" {\n  capabilities = ["read", "create", "update"]' in _policy(sets)


def test_missing_or_unmapped_inputs_disable_set_and_semaphore_path():
    defaults = _defaults("03-github-engine.yml")
    env = {"openbao_platform_env": {"OPENBAO_GITHUB_DISPATCH_REPOSITORY": "example-repo"}}
    unset_owner = _render(defaults["openbao_github_dispatch_owner"], env)
    repository = _render(defaults["openbao_github_dispatch_repository"], env)
    assert unset_owner == ""
    assert repository == "example-repo"
    installations = [{"name": "example-org", "installation_id": "4242"}]
    for owner, repository, mappings in (
        (unset_owner, repository, installations),
        ("example-org", "", installations),
        ("example-org", "example-repo", []),
        ("example-org", "example-repo", [{"name": "example-org", "installation_id": ""}]),
    ):
        sets = _sets(owner, repository, mappings)
        assert sets == []
        assert "github-admin/token/workflow-dispatch" not in _policy(sets)


def test_incomplete_dispatch_configuration_warns_with_input_keys():
    tasks_path = DEFAULTS.parents[1] / "tasks/init/05-github-engine.yml"
    tasks = yaml.safe_load(tasks_path.read_text(encoding="utf-8"))
    warnings = [task for task in tasks if task.get("name") == "Warn when workflow dispatch configuration is incomplete"]
    assert len(warnings) == 1
    assert "openbao_github_dispatch_permission_sets | length == 0" in warnings[0]["when"]
    message = warnings[0]["ansible.builtin.debug"]["msg"]
    assert message.startswith("WARNING:")
    assert "OPENBAO_GITHUB_DISPATCH_OWNER" in message
    assert "OPENBAO_GITHUB_DISPATCH_REPOSITORY" in message
