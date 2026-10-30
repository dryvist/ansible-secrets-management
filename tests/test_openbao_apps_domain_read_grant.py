"""Every path read with the `apps` AppRole is readable by the `apps` policy.

The repo-owned domain catalog assigns each path to the `apps` AppRole.
The policy must grant each declared path. Its per-app grants come from
openbao_apps_read_apps (roles/openbao/defaults/main/05c-...), rendered here
from the real expression with the real seeding maps; infrastructure/unifi is
granted directly by apps-policy.hcl.j2.
"""

from __future__ import annotations

from pathlib import Path

import jinja2
import pytest
import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles" / "openbao" / "defaults" / "main"
NAMES_FILE = DEFAULTS / "05c-terrakube-and-remaining-domain-names.yml"
GENERATED_FILE = DEFAULTS / "01c-app-secrets-generated.yml"
GENERATED_PATHS_FILE = DEFAULTS / "01d-app-secret-paths.yml"
PROMOTED_FILE = DEFAULTS / "01b-app-secrets.yml"
CRIBL_EDGE_FILE = DEFAULTS / "05h-cribl-edge-readers.yml"
DOMAINS_FILE = ROOT / "playbooks" / "group_vars" / "all" / "openbao_secrets.yml"
POLICY_TEMPLATE = ROOT / "roles" / "openbao" / "templates" / "apps-policy.hcl.j2"
MEDIA_POLICY_TEMPLATE = ROOT / "roles" / "openbao" / "templates" / "media-policy.hcl.j2"


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _read_apps(names: dict) -> set[str]:
    cribl_edge = _yaml(CRIBL_EDGE_FILE)
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "openbao_generated_app_secrets": _yaml(GENERATED_FILE)["openbao_generated_app_secrets"],
        "openbao_generated_app_secret_paths": _yaml(GENERATED_PATHS_FILE)["openbao_generated_app_secret_paths"],
        "openbao_promoted_app_secrets": _yaml(PROMOTED_FILE)["openbao_promoted_app_secrets"],
        "openbao_router_key_catalog": names.get("openbao_router_key_catalog", {}),
        "openbao_apps_read_published_apps": names.get("openbao_apps_read_published_apps", []),
        "openbao_cribl_edge_mac_a_app": cribl_edge["openbao_cribl_edge_mac_a_app"],
        "openbao_cribl_edge_mac_b_app": cribl_edge["openbao_cribl_edge_mac_b_app"],
    }
    templar.available_variables["openbao_apps_read_excluded_generated_apps"] = (
        [
            templar.template(trust_as_template(app))
            for app in cribl_edge["openbao_apps_read_excluded_generated_apps"]
        ]
    )
    return set(templar.template(trust_as_template(names["openbao_apps_read_apps"])))


def _apps_domain_paths() -> list[str]:
    for domain in _yaml(DOMAINS_FILE)["openbao_secrets_domains"]:
        if domain["name"] == "apps":
            return [p["path"] if isinstance(p, dict) else p for p in domain["paths"]]
    raise AssertionError("no `apps` domain in openbao_secrets_domains")


def _domain(name: str) -> dict:
    for domain in _yaml(DOMAINS_FILE)["openbao_secrets_domains"]:
        if domain["name"] == name:
            return domain
    raise AssertionError(f"no `{name}` domain in openbao_secrets_domains")


def _media_domain_paths() -> list[str]:
    return [
        item["path"] if isinstance(item, dict) else item
        for item in _domain("media")["paths"]
    ]


def _unreadable(paths: list[str], read_apps: set[str], template_text: str) -> list[str]:
    missing = []
    for path in paths:
        if path.startswith("apps/") and path.split("/", 1)[1] in read_apps:
            continue
        if f"data/{path}\"" in template_text:
            continue
        missing.append(path)
    return missing


def _render_apps_policy(read_apps: set[str]) -> str:
    environment = jinja2.Environment()
    environment.filters["comment"] = str
    return environment.from_string(POLICY_TEMPLATE.read_text(encoding="utf-8")).render(
        ansible_managed="",
        openbao_kv_mount="secret",
        openbao_apps_read_apps=sorted(read_apps),
    )


def _render_media_policy() -> str:
    environment = jinja2.Environment()
    environment.filters["comment"] = str
    return environment.from_string(MEDIA_POLICY_TEMPLATE.read_text(encoding="utf-8")).render(
        ansible_managed="",
        openbao_kv_mount="secret",
    )


def test_every_apps_domain_path_is_granted_to_the_apps_reader():
    read_apps = _read_apps(_yaml(NAMES_FILE))
    missing = _unreadable(_apps_domain_paths(), read_apps, POLICY_TEMPLATE.read_text(encoding="utf-8"))
    assert not missing, (
        f"the `apps` domain reads {missing}, which the `apps` policy does not grant; "
        "the domain fetch fails on the 403. Add the bucket to a seeding map or to "
        "openbao_apps_read_published_apps."
    )


def test_idrac_console_user_paths_are_optional_and_have_exact_reads():
    paths = _domain("apps")["paths"]
    console_paths = {
        item["path"] if isinstance(item, dict) else item: item
        for item in paths
        if (item["path"] if isinstance(item, dict) else item).startswith("apps/idrac-kvm-")
    }
    assert set(console_paths) == {"apps/idrac-kvm-r410", "apps/idrac-kvm-r710"}
    assert console_paths == {
        "apps/idrac-kvm-r410": {"path": "apps/idrac-kvm-r410", "optional": True},
        "apps/idrac-kvm-r710": {"path": "apps/idrac-kvm-r710", "optional": True},
    }

    promoted_apps = _yaml(PROMOTED_FILE)["openbao_promoted_app_secrets"]
    assert not {"idrac-kvm-r410", "idrac-kvm-r710"} & set(promoted_apps)

    policy = _render_apps_policy(_read_apps(_yaml(NAMES_FILE)))
    for app in ("idrac-kvm-r410", "idrac-kvm-r710"):
        assert f'path "secret/data/apps/{app}" {{\n  capabilities = ["read"]\n}}' in policy
        assert f'path "secret/metadata/apps/{app}" {{\n  capabilities = ["read", "list"]\n}}' in policy
    assert 'path "secret/data/apps/idrac-kvm-*"' not in policy


def test_media_domain_prefetches_sortarr_and_autobrr_paths():
    media_paths = _media_domain_paths()

    assert "apps/media/sortarr" in media_paths
    assert "apps/media/autobrr" in media_paths
    assert "apps/media/autobrr-private" in media_paths
    assert "apps/media/autobrr-priority" in media_paths


def test_every_media_domain_path_has_a_media_reader_grant():
    media_paths = _media_domain_paths()
    policy = _render_media_policy()
    read_grant = 'path "secret/data/apps/media/*" {\n  capabilities = ["read"]\n}'

    assert media_paths
    assert all(path.startswith("apps/media/") for path in media_paths)
    assert read_grant in policy


def test_openproject_secret_is_promoted_and_prefetched():
    assert "apps/openproject" in _apps_domain_paths()
    assert _yaml(PROMOTED_FILE)["openbao_promoted_app_secrets"]["openproject"] == {
        "openproject_secret_key_base": "OPENPROJECT_SECRET_KEY_BASE"
    }


def test_benchmark_and_promoted_sandbox_agent_paths_render_in_apps_policy():
    policy = _render_apps_policy(_read_apps(_yaml(NAMES_FILE)))

    for app in ("benchmark", "sandbox-agent"):
        assert f'path "secret/data/apps/{app}"' in policy
        assert f'path "secret/metadata/apps/{app}"' in policy


def test_a_published_only_bucket_is_missing_without_the_published_list():
    names = dict(_yaml(NAMES_FILE))
    names["openbao_apps_read_published_apps"] = []
    read_apps = _read_apps(names)
    missing = _unreadable(_apps_domain_paths(), read_apps, POLICY_TEMPLATE.read_text(encoding="utf-8"))
    assert "apps/pve-exporter" in missing


def test_the_ci_resolver_bucket_is_not_granted_to_the_apps_reader():
    assert "ci-resolver" in _yaml(PROMOTED_FILE)["openbao_promoted_app_secrets"]
    assert "ci-resolver" not in _read_apps(_yaml(NAMES_FILE))


def test_postgres_backup_domain_reuses_apps_credentials_and_is_optional():
    domain = _domain("postgres_backup_s3")

    assert domain["credential_domain"] == "apps"
    assert domain["paths"] == [
        {"path": "rustfs/dryvist-homelab-backups/rw", "optional": True}
    ]


def test_postgres_backup_path_has_one_exact_read_grant():
    policy = _render_apps_policy(_read_apps(_yaml(NAMES_FILE)))

    assert (
        'path "secret/data/rustfs/dryvist-homelab-backups/rw" {\n'
        '  capabilities = ["read"]\n}'
    ) in policy
    assert 'path "secret/data/rustfs/*"' not in policy


@pytest.mark.parametrize("service", ["homebox", "nautobot"])
def test_backblaze_domain_reuses_apps_credentials_and_is_optional(service):
    domain = _domain(f"{service}_backup_b2")

    assert domain["credential_domain"] == "apps"
    assert domain["paths"] == [
        {
            "mount": "secrets-external",
            "path": f"backblaze/dryvist-{service}-backups/rw",
            "optional": True,
        }
    ]


@pytest.mark.parametrize("service", ["homebox", "nautobot"])
def test_backblaze_path_has_exact_external_grants_and_no_wildcard(service):
    policy = _render_apps_policy(_read_apps(_yaml(NAMES_FILE)))

    for kind in ("data", "metadata"):
        assert (
            f'path "secrets-external/{kind}/backblaze/dryvist-{service}-backups/rw" {{\n'
            '  capabilities = ["read"]\n}'
        ) in policy
    assert 'path "secrets-external/data/backblaze/*"' not in policy
    assert 'path "secrets-external/metadata/backblaze/*"' not in policy
