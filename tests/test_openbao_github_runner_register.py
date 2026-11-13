"""Runner registration sets are limited to explicitly configured owners."""

from pathlib import Path
import re

from jinja2 import Environment
from jinja2.nativetypes import NativeEnvironment
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main/03-github-engine.yml"
TASKS = ROOT / "roles/openbao/tasks/init/05-github-engine.yml"
TEMPLATE = ROOT / "roles/openbao/templates/github-runner-policy.hcl.j2"
OWNERS_KEY = "OPENBAO_GITHUB_RUNNER_REGISTER_OWNERS"
BASE_RUNNER_SET = {
    "name": "runner-register-example-base",
    "tier": "runner",
    "installation_id": "101",
    "permissions": {"organization_self_hosted_runners": "write"},
}


def _render(expression, variables):
    return NativeEnvironment().from_string(expression).render(**variables)


def _runner_defaults(owner_csv, installations):
    defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
    variables = {
        **defaults,
        "openbao_platform_env": ({OWNERS_KEY: owner_csv} if owner_csv is not None else {}),
        "openbao_github_base_permission_sets": [BASE_RUNNER_SET],
        "openbao_github_org_secrets_installations": installations,
    }
    for name in (
        "openbao_github_runner_register_owners",
        "openbao_github_runner_register_permission_sets",
        "openbao_github_runner_register_missing_owners",
    ):
        variables[name] = _render(defaults[name], variables)
    return variables


def _admin_sets(variables):
    composition = {
        "openbao_github_base_permission_sets": [BASE_RUNNER_SET],
        "openbao_github_org_secrets_permission_sets": [],
        "openbao_github_docs_publisher_permission_sets": [],
        "openbao_github_dify_pr_automation_permission_sets": [],
        "openbao_github_ci_resolver_permission_sets": [],
        "openbao_github_router_snapshot_permission_sets": [],
        "openbao_github_git_mirror_permission_sets": [],
        "openbao_github_role_eval_status_permission_sets": [],
        "openbao_github_workflows_write_permission_sets": [],
    }
    return _render(
        variables["openbao_github_admin_permission_sets"],
        {**variables, **composition},
    )


def _warning_tasks():
    return yaml.safe_load(TASKS.read_text(encoding="utf-8"))


def test_empty_owner_list_adds_no_sets_and_warns_with_the_configuration_key():
    for owner_csv in (None, ""):
        variables = _runner_defaults(owner_csv, [])
        assert variables["openbao_github_runner_register_owners"] == []
        assert variables["openbao_github_runner_register_permission_sets"] == []
        assert variables["openbao_github_runner_register_missing_owners"] == []
        assert _admin_sets(variables) == [BASE_RUNNER_SET]

    tasks = _warning_tasks()
    empty_warning = next(
        task for task in tasks
        if task.get("name") == "Warn when runner registration owners are not configured"
    )
    assert "WARNING:" in empty_warning["ansible.builtin.debug"]["msg"]
    assert OWNERS_KEY in empty_warning["ansible.builtin.debug"]["msg"]
    assert "openbao_github_runner_register_owners | length == 0" in empty_warning["when"]


def test_two_example_owners_generate_only_their_runner_policy_paths():
    variables = _runner_defaults(
        " example-org, example-other ",
        [
            {"name": "example-org", "installation_id": "101"},
            {"name": "example-other", "installation_id": "202"},
        ],
    )
    additional = [
        {
            "name": "runner-register-example-org",
            "tier": "runner",
            "installation_id": "101",
            "permissions": {"organization_self_hosted_runners": "write"},
        },
        {
            "name": "runner-register-example-other",
            "tier": "runner",
            "installation_id": "202",
            "permissions": {"organization_self_hosted_runners": "write"},
        },
    ]
    assert variables["openbao_github_runner_register_owners"] == [
        "example-org", "example-other"
    ]
    assert variables["openbao_github_runner_register_permission_sets"] == additional
    expected = [BASE_RUNNER_SET, *additional]
    assert _admin_sets(variables) == expected

    permission_sets = [
        {**permission_set, "mount": "github-admin"} for permission_set in expected
    ] + [{"name": "read-fixture", "tier": "read", "mount": "github-admin"}]
    environment = Environment()
    environment.filters["comment"] = lambda value: "# " + str(value)
    rendered = environment.from_string(TEMPLATE.read_text(encoding="utf-8")).render(
        ansible_managed="fixture",
        openbao_github_permission_sets=permission_sets,
        openbao_github_runner_mount="github-runner",
        openbao_kv_mount="secret",
    )
    paths = re.findall(r'(?m)^path "([^"]+)" \{', rendered)
    set_paths = [path for path in paths if path.startswith("github-admin/token/")]
    assert set_paths == [
        "github-admin/token/runner-register-example-base",
        "github-admin/token/runner-register-example-org",
        "github-admin/token/runner-register-example-other",
    ]
    stanzas = dict(re.findall(r'(?ms)^path "([^"]+)" \{(.*?)^\}', rendered))
    assert all(
        'capabilities = ["read", "create", "update"]' in stanzas[path]
        for path in set_paths
    )


def test_owner_without_installation_id_is_skipped_and_warned_by_owner():
    variables = _runner_defaults(
        "example-org,example-other",
        [
            {"name": "example-org", "installation_id": "101"},
            {"name": "example-other", "installation_id": ""},
        ],
    )
    assert variables["openbao_github_runner_register_permission_sets"] == [{
        "name": "runner-register-example-org",
        "tier": "runner",
        "installation_id": "101",
        "permissions": {"organization_self_hosted_runners": "write"},
    }]
    assert variables["openbao_github_runner_register_missing_owners"] == ["example-other"]
    assert [permission_set["name"] for permission_set in _admin_sets(variables)] == [
        "runner-register-example-base",
        "runner-register-example-org",
    ]

    missing_warning = next(
        task for task in _warning_tasks()
        if task.get("name") == "Warn when a runner registration owner has no installation ID"
    )
    assert missing_warning["loop"] == "{{ openbao_github_runner_register_missing_owners }}"
    assert "WARNING:" in missing_warning["ansible.builtin.debug"]["msg"]
    assert "{{ item }}" in missing_warning["ansible.builtin.debug"]["msg"]


def test_owner_already_in_base_sets_is_not_duplicated():
    variables = _runner_defaults(
        "example-base",
        [{"name": "example-base", "installation_id": "101"}],
    )
    assert variables["openbao_github_runner_register_permission_sets"] == []
    assert _admin_sets(variables) == [BASE_RUNNER_SET]
