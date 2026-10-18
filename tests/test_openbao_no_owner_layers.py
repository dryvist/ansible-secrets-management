"""Prevent per-owner GitHub permission and Terrakube layers from returning."""

import json
import re
from pathlib import Path

import yaml
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
ROLES = ROOT / "roles"
DEFAULTS = ROLES / "openbao" / "defaults"
TERRAKUBE = DEFAULTS / "main" / "05c-terrakube-and-remaining-domain-names.yml"
RETIRED = DEFAULTS / "main" / "07c-approle-undeclared-exceptions.yml"
RETIRE_TASKS = ROLES / "openbao" / "tasks" / "init" / "09f-retired-terrakube-jwt-roles.yml"
JWT_TASKS = ROLES / "openbao" / "tasks" / "init" / "09-auth-methods-and-terrakube-jwt.yml"
JWT_ROLE_TEMPLATE = ROLES / "openbao" / "templates" / "terrakube-workspace-jwt-role.json.j2"

INSTALLATION_ID_LIST = re.compile(r"OPENBAO_GITHUB_[A-Z_]*INSTALLATION_IDS")
GENERATED_READ_ALL_NAME = re.compile(
    r"(?:['\"]name['\"]\s*:\s*)?['\"]read-['\"]\s*~.*?"
    r"~\s*['\"]-all['\"]",
    re.DOTALL,
)
JINJA_LOOP = re.compile(r"{%-?\s*for\b.*?{%-?\s*endfor\s*-?%}", re.DOTALL)


def _text(path):
    return path.read_text(encoding="utf-8", errors="ignore")


def _render_workspace_role_json(workspace_name, additional_policies=None):
    environment = Environment()
    environment.filters["to_json"] = json.dumps
    return environment.from_string(_text(JWT_ROLE_TEMPLATE)).render(
        openbao_terrakube_jwt_audience="openbao.workload.identity",
        openbao_terrakube_organization="dryvist",
        openbao_terrakube_jwt_token_ttl="90m",
        openbao_config_write_policy_name="config-write",
        openbao_config_write_terrakube_workspaces=["tofu-github", "iac-platform"],
        terrakube_workspace={
            "name": workspace_name,
            "additional_policies": additional_policies or [],
        },
    )


def _render_workspace_role(workspace_name, additional_policies=None):
    return json.loads(_render_workspace_role_json(workspace_name, additional_policies))


def test_roles_have_no_github_installation_id_lists():
    matches = [
        str(path.relative_to(ROOT))
        for path in ROLES.rglob("*")
        if path.is_file() and INSTALLATION_ID_LIST.search(_text(path))
    ]
    assert not matches, f"installation-ID list env names remain in roles: {matches}"


def test_defaults_do_not_generate_read_owner_all_permission_sets():
    matches = []
    for path in DEFAULTS.rglob("*.yml"):
        loops = JINJA_LOOP.findall(_text(path))
        if any(GENERATED_READ_ALL_NAME.search(block) for block in loops):
            matches.append(str(path.relative_to(ROOT)))
    assert not matches, f"generated read-<owner>-all permission sets remain: {matches}"


def test_terrakube_does_not_append_per_owner_github_workspaces():
    text = _text(TERRAKUBE)
    assert not re.search(
        r"{%-?\s*for\b.*?_workspaces\.append\(\s*\{\s*['\"]name['\"]\s*:\s*"
        r"['\"]tofu-github-['\"]\s*~",
        text,
        re.DOTALL,
    )


def test_org_secrets_workspace_is_separate_from_public_tofu_github():
    defaults = yaml.safe_load(_text(TERRAKUBE))
    workspaces = defaults["openbao_terrakube_workspaces"]
    assert isinstance(workspaces, list)
    (tofu_github,) = [w for w in workspaces if w.get("name") == "tofu-github"]
    (org_secrets,) = [
        w for w in workspaces if w.get("name") == "{{ openbao_terrakube_org_secrets_workspace_name }}"
    ]
    assert not any(key.startswith("bound_subjects") for key in tofu_github)
    assert tofu_github["github_admin_raw"] is True
    assert "github_mint" not in org_secrets
    assert "github_admin_raw" not in org_secrets
    assert "kv_write" not in org_secrets
    assert org_secrets["token_self_access"] is False
    assert "openbao_github_org_secrets_permission_sets" in org_secrets["api_read"]
    assert org_secrets["additional_policies"] == [
        "{{ openbao_github_org_secrets_read_policy_name }}"
    ]


def test_public_and_org_secrets_jwt_roles_bind_the_expected_workspace_names():
    public_role = _render_workspace_role("tofu-github")
    org_secrets_role = _render_workspace_role(
        "github-org-secrets", ["github-org-secrets-read"]
    )
    assert public_role["bound_claims"] == {
        "sub": [
            "organization:dryvist:workspace:tofu-github",
            "organization:dryvist:workspace:tofu-github-*",
        ]
    }
    assert org_secrets_role["bound_claims"] == {
        "sub": "organization:dryvist:workspace:github-org-secrets"
    }
    assert public_role["bound_claims_type"] == "glob"
    assert org_secrets_role["bound_claims_type"] == "string"
    assert isinstance(org_secrets_role["bound_claims"]["sub"], str)
    assert org_secrets_role["policies"] == [
        "github-org-secrets-read",
        "terrakube-github-org-secrets",
    ]
    assert "config-write" not in org_secrets_role["policies"]
    assert "terrakube-workspace-jwt-role.json.j2" in _text(JWT_TASKS)

    assert _render_workspace_role_json("tofu-github") == json.dumps(
        {
            "role_type": "jwt",
            "bound_audiences": ["openbao.workload.identity"],
            "bound_claims": {
                "sub": [
                    "organization:dryvist:workspace:tofu-github",
                    "organization:dryvist:workspace:tofu-github-*",
                ]
            },
            "user_claim": "sub",
            "bound_claims_type": "glob",
            "policies": ["config-write", "terrakube-tofu-github"],
            "token_ttl": "90m",
        }
    )


def test_retired_terrakube_prefix_spares_the_shared_tofu_github_identity():
    prefix = yaml.safe_load(_text(RETIRED))["openbao_retired_terrakube_prefix"]
    assert prefix == "terrakube-tofu-github-"
    live = [
        "terrakube-tofu-github",
        "terrakube-tofu-github-owner-a",
        "terrakube-github-org-secrets",
        "terrakube-iac-platform",
    ]
    assert [name for name in live if re.match("^" + re.escape(prefix), name)] == [
        "terrakube-tofu-github-owner-a"
    ]
    assert not re.match("^" + re.escape(prefix), "terrakube-github-org-secrets")
    assert "openbao_retired_terrakube_prefix | regex_escape" in _text(RETIRE_TASKS)


def test_org_secrets_workspace_is_the_only_workspace_with_a_transit_key():
    workspaces = yaml.safe_load(_text(TERRAKUBE))["openbao_terrakube_workspaces"]
    (org_secrets,) = [
        workspace
        for workspace in workspaces
        if workspace.get("name") == "{{ openbao_terrakube_org_secrets_workspace_name }}"
    ]
    assert org_secrets["state_transit_key"] == (
        "{{ openbao_github_org_secrets_state_transit_key }}"
    )
    assert [workspace for workspace in workspaces if "state_transit_key" in workspace] == [
        org_secrets
    ]
