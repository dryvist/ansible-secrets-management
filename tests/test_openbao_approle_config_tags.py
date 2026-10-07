"""Keep protected role reconciliation separate from secret_id issuance."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "roles" / "openbao" / "tasks" / "init.yml"
APPROLE_TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "10-approles.yml"
SITE_PLAY = ROOT / "playbooks" / "site" / "04a-openbao.yml"


def _named_task(tasks, name):
    return next(task for task in tasks if task.get("name") == name)


def _flatten(node):
    if isinstance(node, list):
        for value in node:
            yield from _flatten(value)
    elif isinstance(node, dict):
        if "name" in node:
            yield node
        for key in ("block", "rescue", "always", "tasks"):
            if key in node:
                yield from _flatten(node[key])


def test_role_config_tag_does_not_select_secret_id_issuance():
    init_tasks = yaml.safe_load(INIT.read_text(encoding="utf-8"))
    config = _named_task(
        init_tasks, "Declare AppRoles and reconcile their policy and TTL bounds"
    )
    issuance = _named_task(init_tasks, "Issue per-call and stored AppRole credentials")

    assert config["ansible.builtin.import_tasks"] == "init/10-approles.yml"
    assert set(config["tags"]) == {"openbao_approle", "openbao_approle_config"}
    assert issuance["ansible.builtin.import_tasks"] == "init/10b-approle-secret-ids.yml"
    assert issuance["tags"] == ["openbao_approle"]

    declared_tasks = yaml.safe_load(APPROLE_TASKS.read_text(encoding="utf-8"))
    assert not any(
        task.get("ansible.builtin.import_tasks") == "10b-approle-secret-ids.yml"
        for task in declared_tasks
    )

    site_tasks = _flatten(yaml.safe_load(SITE_PLAY.read_text(encoding="utf-8")))
    include_role = _named_task(list(site_tasks), "Include openbao role")
    assert "openbao_approle_config" in include_role["tags"]
