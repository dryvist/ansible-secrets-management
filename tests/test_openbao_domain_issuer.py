"""The repo-owned domain catalog declares its workstation issuer roles."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
DOMAINS = ROOT / "playbooks/group_vars/all/openbao_secrets.yml"


def test_workstation_domains_are_declared_at_the_domain_source():
    domains = yaml.safe_load(DOMAINS.read_text(encoding="utf-8"))["openbao_secrets_domains"]
    workstation_roles = {
        domain["name"]: domain["workstation_issuer_role"]
        for domain in domains
        if domain.get("workstation_issuer_role")
    }

    assert workstation_roles == {
        "apps": "apps-workstation",
        "media": "media-workstation",
        "monitoring": "monitoring-workstation",
        "local-cloud": "local-cloud-workstation",
        "observability": "observability-workstation",
    }
