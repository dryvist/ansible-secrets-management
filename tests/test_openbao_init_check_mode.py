"""OpenBao init probes run during check mode without forcing any writes."""

from pathlib import Path
import re

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "roles" / "openbao" / "tasks" / "init"
INSTALL = ROOT / "roles" / "openbao" / "tasks" / "main" / "install.yml"
SEED = ROOT / "roles" / "openbao" / "tasks" / "seed_generated_app_secret.yml"
HANDLERS = ROOT / "roles" / "openbao" / "handlers" / "main.yml"
READ_COMMAND_PREFIXES = (
    "bao status",
    "bao kv get",
    "bao read",
    "bao policy read",
    "bao list",
    "bao auth list",
    "bao secrets list",
    "bao policy list",
    "bao plugin info",
)
# `bao write sys/capabilities-self` only asks what the token may do; it changes nothing.
CAPABILITY_PROBE = "sys/capabilities-self"
WRITE_COMMAND = re.compile(r"\b(?:put|patch|write|delete|unseal)\b|bao\s+operator\s+init\b")


def _walk_tasks(node):
    if isinstance(node, list):
        for item in node:
            yield from _walk_tasks(item)
    elif isinstance(node, dict):
        if "name" in node:
            yield node
        for key in ("block", "rescue", "always", "tasks"):
            if key in node:
                yield from _walk_tasks(node[key])


def _tasks():
    for path in sorted((*INIT.rglob("*.yml"), SEED)):
        yield path, from_yaml(path)


def from_yaml(path):
    for task in _walk_tasks(yaml.safe_load(path.read_text(encoding="utf-8")) or []):
        yield task


def _command(task):
    spec = task.get("ansible.builtin.command", task.get("command"))
    if isinstance(spec, dict):
        if "cmd" in spec:
            return str(spec["cmd"]).strip()
        return " ".join(str(argument) for argument in spec.get("argv", []))
    return str(spec).strip()


def test_openbao_package_install_is_skipped_in_check_mode():
    install = next(
        task for task in from_yaml(INSTALL) if task.get("name") == "Install OpenBao package"
    )

    assert "not ansible_check_mode" in install["when"]


def test_read_only_openbao_commands_run_during_check_mode():
    read_tasks = [
        (path, task)
        for path, tasks in _tasks()
        for task in tasks
        if _command(task).startswith(READ_COMMAND_PREFIXES)
    ]

    assert read_tasks, "expected to find OpenBao reads in the init path"
    for path, task in read_tasks:
        assert task.get("check_mode") is False, f"{path}: {task.get('name')} skips in check mode"
        assert task.get("changed_when") is False, f"{path}: {task.get('name')} must remain read-only"


def test_write_commands_are_never_forced_in_check_mode():
    write_tasks = [
        (path, task)
        for path, tasks in _tasks()
        for task in tasks
        if WRITE_COMMAND.search(_command(task))
        and CAPABILITY_PROBE not in _command(task)
    ]

    assert write_tasks, "expected to find OpenBao write commands in the init path"
    for path, task in write_tasks:
        assert task.get("check_mode") is not False, f"{path}: {task.get('name')} forces a write"


def test_generated_secret_check_report_lists_field_names_only():
    tasks = list(from_yaml(SEED))
    report = next(task for task in tasks if task.get("name") == "Report generated app secret fields that would be written in check mode")

    assert "ansible_check_mode" in report["when"]
    assert "openbao_seed_desired.keys()" in report["ansible.builtin.debug"]["msg"]
    assert "openbao_seed_desired.values()" not in report["ansible.builtin.debug"]["msg"]


def test_policy_check_report_uses_the_existing_write_comparison():
    path = INIT / "08b-rbac-policy-writes.yml"
    tasks = list(from_yaml(path))
    task = next(
        task for task in tasks if task.get("name") == "Resolve RBAC policies that are missing or changed"
    )
    expression = task["ansible.builtin.set_fact"]["openbao_changed_policy_names"]
    variables = {
        "openbao_reachable_policies": [
            {"name": "unchanged"},
            {"name": "changed"},
            {"name": "missing"},
        ],
        "openbao_policies_raw": {"stdout": '["unchanged", "changed"]'},
        "openbao_existing_policy_map": {"unchanged": "same", "changed": "old"},
        "openbao_rendered_policy_map": {
            "unchanged": "same",
            "changed": "new",
            "missing": "new",
        },
    }
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables

    assert templar.template(trust_as_template(expression)) == ["changed", "missing"]


def test_capability_probes_run_during_check_mode():
    probes = [
        task
        for _path, tasks in _tasks()
        for task in tasks
        if CAPABILITY_PROBE in _command(task)
    ]

    assert len(probes) == 3
    for task in probes:
        assert task.get("changed_when") is False
        assert task.get("check_mode") is False
        assert task.get("no_log") is True


def test_login_calls_never_run_during_check_mode():
    """A login mints a server-side token and spends secret_id uses; not a read."""
    offenders = [
        f"{path.name}:{task['name']}"
        for path, tasks in _tasks()
        for task in tasks
        if "/login" in str((task.get("ansible.builtin.uri") or {}).get("url", ""))
        and task.get("check_mode") is False
    ]
    assert not offenders, offenders


def test_rolling_restart_handler_skips_check_mode():
    handlers = list(from_yaml(HANDLERS))
    restart = next(
        task
        for task in handlers
        if task.get("name") == "Restart flagged openbao voters one at a time"
    )

    assert restart.get("when") == "not ansible_check_mode"
