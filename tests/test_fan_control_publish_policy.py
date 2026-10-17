"""The fan-control service credential has one exact publisher bucket."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISH_APPS = ROOT / "roles/openbao/defaults/main/07c-base-policies.yml"


def test_fan_control_write_credential_is_an_exact_publisher_app() -> None:
    content = PUBLISH_APPS.read_text(encoding="utf-8")
    apps = content.split("openbao_credential_publish_apps:\n", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]

    assert apps.splitlines().count("  - fan-control-write") == 1
