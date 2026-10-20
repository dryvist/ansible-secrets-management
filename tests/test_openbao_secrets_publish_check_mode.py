"""Credential publishing is skipped in check mode, where vault_login returns no token."""

from pathlib import Path

import yaml


PUBLISH = Path(__file__).resolve().parent.parent / "roles/openbao_secrets/tasks/publish.yml"


def test_publish_write_is_skipped_in_check_mode():
    tasks = yaml.safe_load(PUBLISH.read_text())
    outer = next(task for task in tasks if task["name"] == "Publish generated credentials to OpenBao")
    write = next(task for task in outer["block"] if task["name"] == "Write the credentials")

    assert "not ansible_check_mode" in write["when"]
