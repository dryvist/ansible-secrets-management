"""PR reconciliation mints only pinned owner tokens from the raw everyday endpoint."""

import re
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
TASKS = ROOT / "roles/openbao/tasks/init/09c-github-oidc.yml"
POLICIES = DEFAULTS / "07c-base-policies.yml"
TEMPLATES = ROOT / "roles/openbao/templates"


def _defaults(name):
    return yaml.safe_load((DEFAULTS / name).read_text(encoding="utf-8"))


def _find_task(tasks, name):
    for task in tasks:
        if task.get("name") == name:
            return task
        nested = task.get("block", [])
        if nested and (found := _find_task(nested, name)):
            return found
    return None


def _render_policy(defaults):
    environment = Environment(loader=FileSystemLoader(TEMPLATES))
    environment.filters["comment"] = lambda value: "# " + str(value)
    return environment.get_template("pr-reconcile-sweep-policy.hcl.j2").render(
        ansible_managed="managed",
        openbao_github_everyday_mount="github",
        openbao_pr_reconcile_owners=defaults["openbao_pr_reconcile_owners"],
        openbao_github_pr_reconcile_permissions=defaults[
            "openbao_github_pr_reconcile_permissions"
        ],
    )


def test_owners_and_permission_map_are_exact():
    defaults = _defaults("05f-pr-reconcile.yml")
    assert defaults["openbao_pr_reconcile_owners"] == [
        "JacobPEvans",
        "JacobPEvans-ai",
        "jpe-nix",
        "jpe-private",
        "jpe-ansible",
        "jpe-cribl",
        "jpe-splunk",
        "jpe-openbao-plugin-secrets",
    ]
    assert defaults["openbao_github_pr_reconcile_permissions"] == {
        "contents": "write",
        "issues": "write",
        "pull_requests": "write",
        "statuses": "write",
    }


def test_policy_pins_owner_names_and_permission_map_on_the_raw_endpoint():
    defaults = _defaults("05f-pr-reconcile.yml")
    rendered = _render_policy(defaults)
    paths = re.findall(r'(?m)^path "([^"]+)" \{', rendered)
    assert paths == ["github/token"]
    assert 'capabilities = ["create", "update"]' in rendered
    assert 'required_parameters = ["org_name", "permissions"]' in rendered
    owners = ", ".join(f'"{owner}"' for owner in defaults["openbao_pr_reconcile_owners"])
    assert f'"org_name" = [{owners}]' in rendered
    assert (
        '"permissions" = [{ "contents" = "write", "issues" = "write", '
        '"pull_requests" = "write", "statuses" = "write" }]'
    ) in rendered
    assert '"installation_id" = []' in rendered
    assert '"repository_ids" = []' in rendered
    assert '"repositories"' not in rendered

    policies = yaml.safe_load(POLICIES.read_text(encoding="utf-8"))
    entries = [
        item for item in policies["openbao_base_policies_static"]
        if item["name"] == "{{ openbao_github_pr_reconcile_policy_name }}"
    ]
    assert entries == [
        {
            "name": "{{ openbao_github_pr_reconcile_policy_name }}",
            "template": "pr-reconcile-sweep-policy.hcl.j2",
        }
    ]


def test_oidc_role_has_exact_claims_one_policy_short_batch_token_and_drift_guard():
    defaults = _defaults("05f-pr-reconcile.yml")
    tasks = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
    read = _find_task(tasks, "Read the pr-reconcile-sweep OIDC role")
    write = _find_task(tasks, "Reconcile the pr-reconcile-sweep OIDC role")
    assert read is not None
    assert write is not None

    assert defaults["openbao_github_pr_reconcile_policy_name"] == "pr-reconcile-sweep"
    assert defaults["openbao_github_pr_reconcile_audience"] == "openbao"
    assert defaults["openbao_github_pr_reconcile_repository"] == "JacobPEvans/.github-ai"
    assert defaults["openbao_github_pr_reconcile_workflow_ref"] == (
        "JacobPEvans/.github-ai/.github/workflows/pr-reconcile-sweep.yml@refs/heads/main"
    )
    assert defaults["openbao_github_pr_reconcile_ref"] == "refs/heads/main"
    assert defaults["openbao_github_pr_reconcile_event_names"] == [
        "schedule", "workflow_dispatch"
    ]
    assert defaults["openbao_github_pr_reconcile_runner_environment"] == "self-hosted"
    assert defaults["openbao_github_pr_reconcile_token_ttl"] == "5m"
    assert defaults["openbao_github_pr_reconcile_token_max_ttl"] == "10m"

    assert write["vars"]["_pr_reconcile_role_claims"] == {
        "repository": "{{ openbao_github_pr_reconcile_repository }}",
        "workflow_ref": "{{ openbao_github_pr_reconcile_workflow_ref }}",
        "ref": "{{ openbao_github_pr_reconcile_ref }}",
        "event_name": "{{ openbao_github_pr_reconcile_event_names }}",
        "runner_environment": "{{ openbao_github_pr_reconcile_runner_environment }}",
    }
    payload = write["ansible.builtin.command"]["stdin"]
    assert "'role_type': 'jwt'" in payload
    assert "'user_claim': 'workflow_ref'" in payload
    assert "job_workflow_ref" not in payload
    assert "job_workflow_ref" not in write["vars"]["_pr_reconcile_role_claims"]
    assert "'bound_audiences': [openbao_github_pr_reconcile_audience]" in payload
    assert "'bound_claims_type': 'string'" in payload
    assert "'token_policies': [openbao_github_pr_reconcile_policy_name]" in payload
    assert "'token_no_default_policy': true" in payload
    assert "'token_type': 'batch'" in payload
    assert "'token_ttl': openbao_github_pr_reconcile_token_ttl" in payload
    assert "'token_max_ttl': openbao_github_pr_reconcile_token_max_ttl" in payload

    assert "openbao_pr_reconcile_owners | length > 0" in read["when"]
    assert "openbao_pr_reconcile_owners | length > 0" in write["when"]
    drift_guard = write["when"][-1]
    assert "openbao_github_oidc_pr_reconcile_role_current.rc | default(1)" in drift_guard
    for field in (
        ".role_type",
        ".bound_audiences",
        ".bound_claims",
        ".bound_claims_type",
        ".user_claim",
        ".token_policies",
        ".token_no_default_policy",
        ".token_type",
        ".token_ttl",
        ".token_max_ttl",
    ):
        assert field in drift_guard
    assert "changed_when" in write


def test_existing_github_sets_policies_and_oidc_roles_keep_their_own_tiers():
    github = _defaults("03-github-engine.yml")
    app_mounts = _defaults("03b-github-app-mounts.yml")
    policies = yaml.safe_load(POLICIES.read_text(encoding="utf-8"))[
        "openbao_base_policies_static"
    ]
    tasks = yaml.safe_load(TASKS.read_text(encoding="utf-8"))

    for document in (github, app_mounts):
        assert "pr_reconcile" not in yaml.safe_dump(document)

    existing_policy_templates = {
        "{{ openbao_github_docs_publisher_policy_name }}": "github-docs-publisher-policy.hcl.j2",
        "{{ openbao_github_ci_resolver_policy_name }}": "github-ci-resolver-policy.hcl.j2",
        "{{ openbao_github_git_mirror_policy_name }}": "git-mirror-policy.hcl.j2",
        "{{ openbao_uicheck_policy_name }}": "uicheck-policy.hcl.j2",
    }
    for name, template in existing_policy_templates.items():
        assert next(item for item in policies if item["name"] == name)["template"] == template

    for role_name in (
        "Reconcile the docs-publisher OIDC role",
        "Reconcile the uicheck OIDC role",
        "Reconcile the ci-ai-review OIDC role",
        "Reconcile the ci-evals OIDC role",
    ):
        assert _find_task(tasks, role_name) is not None
