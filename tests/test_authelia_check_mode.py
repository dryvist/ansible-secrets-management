"""Authelia controller-side staging runs under --check so later tasks can read it."""

from pathlib import Path

import yaml


TASKS = Path(__file__).resolve().parents[1] / "roles" / "authelia" / "tasks" / "main.yml"


def _walk_tasks(node):
    if isinstance(node, list):
        for item in node:
            yield from _walk_tasks(item)
    elif isinstance(node, dict):
        if "name" in node:
            yield node
        for key in ("block", "rescue", "always"):
            if key in node:
                yield from _walk_tasks(node[key])


def test_controller_staging_tasks_run_in_check_mode():
    staged = [t for t in _walk_tasks(yaml.safe_load(TASKS.read_text())) if t.get("delegate_to") == "localhost"]
    assert staged
    assert [t["name"] for t in staged if t.get("check_mode") is not False] == []
