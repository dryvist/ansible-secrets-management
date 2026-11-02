"""Evaluation leaves are converge-published and read apart from their app buckets."""

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
CATALOG = ROOT / "playbooks/group_vars/all/openbao_secrets.yml"
EVAL_LEAVES = ("hatchet/eval", "dify/eval")


def _defaults(name):
    return yaml.safe_load((DEFAULTS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("leaf", EVAL_LEAVES)
def test_converge_publishes_only_the_eval_leaf_not_its_app_bucket_or_siblings(leaf):
    publish = _defaults("07c-policy-composition.yml")["openbao_credential_publish_apps"]
    app = leaf.split("/", maxsplit=1)[0]
    assert publish.count(leaf) == 1
    assert [item for item in publish if item == app or item.startswith(f"{app}/")] == [leaf]


@pytest.mark.parametrize("leaf", EVAL_LEAVES)
def test_apps_domain_reads_the_eval_leaf_and_tolerates_its_absence(leaf):
    published = _defaults("05c-terrakube-and-remaining-domain-names.yml")["openbao_apps_read_published_apps"]
    assert published.count(leaf) == 1

    domains = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))["openbao_secrets_domains"]
    apps_paths = next(domain for domain in domains if domain["name"] == "apps")["paths"]
    assert {"path": f"apps/{leaf}", "optional": True} in apps_paths
