"""Global read-all stays limited to KV and approved non-secret metadata."""

from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined
import yaml


ROOT = Path(__file__).resolve().parents[1]
OPENBAO = ROOT / "roles/openbao"
DEFAULTS = OPENBAO / "defaults/main"
TEMPLATES = OPENBAO / "templates"
ROLE_DEFAULTS = DEFAULTS / "07b-base-approles.yml"
POLICY_DEFAULTS = DEFAULTS / "07c-base-policies.yml"
ELEVATED_ROLE_DEFAULTS = DEFAULTS / "07f-elevated-approles.yml"
READ_LIST = {"read", "list"}
SYSTEM_METADATA_PATHS = {
    "sys/mounts",
    "sys/auth",
    "sys/policies/acl",
    "sys/policies/acl/*",
    "sys/internal/ui/mounts",
    "sys/internal/ui/mounts/*",
}
EXCLUDED_PATHS = [
    re.compile(r"^github(?:-[^/]*)?/"),
    re.compile(r"^(?:database|db|ssh(?:-[^/]*)?|pki)/"),
    re.compile(r"^identity/oidc/token(?:/|$)"),
    re.compile(r"^auth/[^/]+/role/[^/]+/secret-id(?:/|$)"),
    re.compile(r"^sys/raw(?:/|$)"),
    re.compile(r"^sys/audit(?:/|$)"),
]


def _defaults():
    values = {}
    for path in sorted(DEFAULTS.glob("*.yml")):
        values.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return values


def _mounts():
    values = _defaults()
    renderer = Environment(undefined=StrictUndefined)
    mounts = []
    for mount in values["openbao_kv_mounts"]:
        path = mount.get("path", mount)
        mounts.append(renderer.from_string(str(path)).render(**values))
    return mounts


def _environment():
    environment = Environment(
        loader=FileSystemLoader([str(TEMPLATES), str(OPENBAO)]),
        undefined=StrictUndefined,
    )
    environment.filters["comment"] = lambda value: "# " + str(value)
    return environment


def _render(template):
    return _environment().get_template(template).render(
        ansible_managed="managed",
        openbao_kv_mounts=[{"path": path} for path in _mounts()],
    )


def _grants(policy):
    return {
        path: set(re.findall(r'"([^"]+)"', capabilities))
        for path, capabilities in re.findall(
            r'path "([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]+)\]\s*\}',
            policy,
        )
    }


def _expected_global_read_grants():
    grants = {
        path: READ_LIST.copy()
        for path in SYSTEM_METADATA_PATHS
    }
    for mount in _mounts():
        grants[f"{mount}/data/*"] = READ_LIST.copy()
        grants[f"{mount}/metadata/*"] = READ_LIST.copy()
    return grants


def test_both_global_read_policies_cover_every_declared_kv_mount():
    expected = _expected_global_read_grants()
    for template in ("ai-global-read-policy.hcl.j2", "operator-human-policy.hcl.j2"):
        grants = _grants(_render(template))
        assert {path: grants.get(path) for path in expected} == expected


def test_shared_read_all_block_has_only_read_and_list():
    grants = _grants(_render("templates/global-read-all-policy-block.j2"))
    assert grants == _expected_global_read_grants()
    assert all(capabilities == READ_LIST for capabilities in grants.values())
    assert not any(
        capabilities.intersection({"create", "update", "delete", "patch", "sudo"})
        for capabilities in grants.values()
    )


def test_read_all_policies_exclude_credential_mint_and_sensitive_system_paths():
    for template in ("ai-global-read-policy.hcl.j2", "operator-human-policy.hcl.j2"):
        for path in _grants(_render(template)):
            assert not any(pattern.search(path) for pattern in EXCLUDED_PATHS), path


def test_only_trusted_ai_roles_attach_global_read_and_elevation_split_is_unchanged():
    values = _defaults()
    roles = yaml.safe_load(ROLE_DEFAULTS.read_text(encoding="utf-8"))[
        "openbao_base_approles_core"
    ]
    by_name = {role["name"]: role for role in roles}
    trusted_readonly = by_name['{{ openbao_ai_readonly_approle_name }}']
    trusted_elevated = by_name['{{ openbao_ai_elevated_approle_name }}']
    untrusted_ai = by_name['{{ openbao_ai_public_approle_name }}']

    assert values["openbao_ai_global_read_policy_name"] == "ai-global-read"
    assert "openbao_ai_global_read_policy_name" in values[
        "openbao_ai_trusted_read_all_policies"
    ]
    assert trusted_readonly["token_policies"] == (
        "{{ openbao_ai_trusted_read_all_policies }}"
    )
    assert "openbao_ai_trusted_read_all_policies" in trusted_elevated[
        "token_policies"
    ]
    assert untrusted_ai["policy"] == "{{ openbao_ai_public_policy_name }}"
    assert "openbao_ai_global_read_policy_name" not in str(untrusted_ai)

    operator_workstation = next(
        row
        for row in yaml.safe_load(ELEVATED_ROLE_DEFAULTS.read_text(encoding="utf-8"))[
            "openbao_base_approles_elevated"
        ]
        if row["name"] == "operator-workstation"
    )
    assert "openbao_read_all_policies" in operator_workstation["token_policies"]
    assert "openbao_ai_trusted_read_all_policies" not in operator_workstation[
        "token_policies"
    ]

    elevation = {row["name"]: row["policy"] for row in values["openbao_elevate_roles"]}
    assert elevation == {
        "elevate-trusted": "{{ openbao_human_unlock_policy_name }}",
        "elevate-untrusted": "{{ openbao_human_unlock_untrusted_policy_name }}",
        "elevate-policy-sync": "{{ openbao_policy_sync_unlock_policy_name }}",
    }

    policies = yaml.safe_load(POLICY_DEFAULTS.read_text(encoding="utf-8"))[
        "openbao_base_policies_static"
    ]
    assert {
        "name": "{{ openbao_ai_global_read_policy_name }}",
        "template": "ai-global-read-policy.hcl.j2",
    } in policies
