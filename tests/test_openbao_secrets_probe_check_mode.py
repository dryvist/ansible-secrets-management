"""The endpoint probe runs in check mode, so --check resolves the same endpoint a real run does."""

from pathlib import Path

import yaml


MAIN = Path(__file__).resolve().parent.parent / "roles/openbao_secrets/tasks/main.yml"


def test_endpoint_probe_runs_in_check_mode():
    tasks = yaml.safe_load(MAIN.read_text())
    probe = next(task for task in tasks if task["name"].startswith("Probe OpenBao endpoints"))

    assert probe["ansible.builtin.uri"]["method"] == "GET"
    assert probe["changed_when"] is False
    assert probe["check_mode"] is False
