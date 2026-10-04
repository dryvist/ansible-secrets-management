"""Every path the `apps` secrets domain reads is readable by the `apps` policy.

roles/openbao_secrets reads each path of the `apps` domain with the `apps`
AppRole. A path the policy denies answers 403, and classify_reads.yml fails
the whole domain on any 403, `optional: true` included (optional only
tolerates a 404). The policy's per-app grants come from
openbao_apps_read_apps (roles/openbao/defaults/main/05c-...), rendered here
from the real expression with the real seeding maps; infrastructure/unifi is
granted directly by apps-policy.hcl.j2.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles" / "openbao" / "defaults" / "main"
NAMES_FILE = DEFAULTS / "05c-terrakube-and-remaining-domain-names.yml"
GENERATED_FILE = DEFAULTS / "01c-app-secrets-generated.yml"
PROMOTED_FILE = DEFAULTS / "01b-app-secrets.yml"
CRIBL_EDGE_FILE = DEFAULTS / "05h-cribl-edge-readers.yml"
DOMAINS_FILE = ROOT / "roles" / "openbao_secrets" / "defaults" / "main" / "01-domains.yml"
POLICY_TEMPLATE = ROOT / "roles" / "openbao" / "templates" / "apps-policy.hcl.j2"


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _read_apps(names: dict) -> set[str]:
    cribl_edge = _yaml(CRIBL_EDGE_FILE)
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "openbao_generated_app_secrets": _yaml(GENERATED_FILE)["openbao_generated_app_secrets"],
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


def _unreadable(paths: list[str], read_apps: set[str], template_text: str) -> list[str]:
    missing = []
    for path in paths:
        if path.startswith("apps/") and path.split("/", 1)[1] in read_apps:
            continue
        if f"data/{path}\"" in template_text:
            continue
        missing.append(path)
    return missing


def test_every_apps_domain_path_is_granted_to_the_apps_reader():
    read_apps = _read_apps(_yaml(NAMES_FILE))
    missing = _unreadable(_apps_domain_paths(), read_apps, POLICY_TEMPLATE.read_text(encoding="utf-8"))
    assert not missing, (
        f"the `apps` domain reads {missing}, which the `apps` policy does not grant; "
        "the domain fetch fails on the 403. Add the bucket to a seeding map or to "
        "openbao_apps_read_published_apps."
    )


def test_a_published_only_bucket_is_missing_without_the_published_list():
    names = dict(_yaml(NAMES_FILE))
    names["openbao_apps_read_published_apps"] = []
    read_apps = _read_apps(names)
    missing = _unreadable(_apps_domain_paths(), read_apps, POLICY_TEMPLATE.read_text(encoding="utf-8"))
    assert "apps/pve-exporter" in missing
