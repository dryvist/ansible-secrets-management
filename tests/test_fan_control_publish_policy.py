"""The fan-control service credential has one exact publisher bucket."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PUBLISH_APPS = ROOT / "roles/openbao/defaults/main/07c-policy-composition.yml"


def test_fan_control_write_credential_is_an_exact_publisher_app() -> None:
    defaults = yaml.safe_load(PUBLISH_APPS.read_text(encoding="utf-8"))
    apps = defaults["openbao_credential_publish_apps"]

    assert defaults["openbao_fan_control_write_kv_path"] == "apps/fan-control-write"
    assert apps.count(
        "{{ openbao_fan_control_write_kv_path | regex_replace('^apps/', '') }}"
    ) == 1
