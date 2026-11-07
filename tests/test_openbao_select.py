"""Per-kind OpenBao selection uses the role's tasks and native templating."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/openbao"


def test_selection_defaults_keep_full_set_behavior():
    defaults = yaml.safe_load(
        (ROLE / "defaults/main/00-install-and-node.yml").read_text()
    )
    assert defaults["openbao_select"] == {}
    assert defaults["openbao_select_max"] == 25
