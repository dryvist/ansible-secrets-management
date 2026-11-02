"""The Hatchet eval leaf is converge-published and read by the apps domain, apart from apps/hatchet."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
CATALOG = ROOT / "playbooks/group_vars/all/openbao_secrets.yml"
LEAF = "hatchet/eval"


def _defaults(name):
    return yaml.safe_load((DEFAULTS / name).read_text(encoding="utf-8"))


def test_converge_publishes_only_the_eval_leaf_not_the_hatchet_bucket():
    publish = _defaults("07c-policy-composition.yml")["openbao_credential_publish_apps"]
    assert LEAF in publish
    assert "hatchet" not in publish


def test_apps_domain_reads_the_eval_leaf_and_tolerates_its_absence():
    published = _defaults("05c-terrakube-and-remaining-domain-names.yml")["openbao_apps_read_published_apps"]
    assert LEAF in published

    domains = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))["openbao_secrets_domains"]
    apps_paths = next(domain for domain in domains if domain["name"] == "apps")["paths"]
    assert {"path": f"apps/{LEAF}", "optional": True} in apps_paths
