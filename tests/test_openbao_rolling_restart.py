"""Contract for the "Restart openbao" topic: voters restart one at a time.

The config and unit tasks notify the topic. The handler file flags each
notified voter, then a single run_once handler, defined after the flags, runs
restart_rolling.yml. That file restarts the flagged voters in a sequential loop
under a block that fails the play, active voter last. Each host step restarts
its own voter and waits for it to be healthy before the loop moves on.

The negative cases are the handler shape this replaces and shapes that would
restart two voters at once. The same checks must reject each of them.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles" / "openbao"
TOPIC = "Restart openbao"
ROLLING = "restart_rolling.yml"
HOST_STEP = "restart_rolling_host.yml"
SYSTEMD = "ansible.builtin.systemd"
INCLUDE = "ansible.builtin.include_tasks"
URI = "ansible.builtin.uri"
SET_FACT = "ansible.builtin.set_fact"


def _listens(handler):
    listen = handler.get("listen", [])
    topics = [listen] if isinstance(listen, str) else list(listen)
    return TOPIC in topics or handler.get("name") == TOPIC


def _restarts_openbao(task):
    module = task.get(SYSTEMD)
    return isinstance(module, dict) and module.get("name") == "openbao" and module.get("state") == "restarted"


def _sets_pending(task):
    facts = task.get(SET_FACT)
    return isinstance(facts, dict) and facts.get("openbao_restart_pending") is True


def _includes(task, target):
    return str(task.get(INCLUDE, "")).endswith(target)


def _leaves(tasks, fatal=False):
    """Yield (task, any_errors_fatal) for each leaf task, inherited from enclosing blocks."""
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        inherited = fatal or bool(task.get("any_errors_fatal"))
        if "block" in task:
            yield from _leaves(task["block"], inherited)
        else:
            yield task, inherited


def handler_violations(handlers):
    """Problems with the handlers that listen to the restart topic."""
    topic = [(i, h) for i, h in enumerate(handlers) if _listens(h)]
    if not topic:
        return ["no handler listens to the restart topic"]
    problems = [f"{h.get('name')!r} restarts openbao directly" for _, h in topic if _restarts_openbao(h)]
    rolling = [(i, h) for i, h in topic if _includes(h, ROLLING)]
    if len(rolling) != 1:
        problems.append(f"expected one handler including {ROLLING}, found {len(rolling)}")
    for index, handler in rolling:
        if handler.get("run_once") is not True:
            problems.append(f"{handler.get('name')!r} is not run_once")
        flags = [i for i, h in topic if _sets_pending(h)]
        if not flags:
            problems.append("no handler flags a voter for restart")
        if any(flag > index for flag in flags):
            problems.append(f"{handler.get('name')!r} runs before a flag handler")
    return problems


def rolling_violations(tasks):
    """Problems with restart_rolling.yml: a fail-closed, sequential per-host loop."""
    leaves = list(_leaves(tasks))
    problems = [f"{t.get('name')!r} restarts openbao outside the per-host loop" for t, _ in leaves if _restarts_openbao(t)]
    loops = [fatal for t, fatal in leaves if _includes(t, HOST_STEP) and "loop" in t]
    if not loops:
        problems.append(f"no sequential loop over {HOST_STEP}")
    elif not any(loops):
        problems.append("the per-host loop does not fail the play (any_errors_fatal)")
    return problems


def host_step_violations(tasks):
    """Problems with one host step: restart its own voter, then wait for it."""
    restarts = [i for i, t in enumerate(tasks) if _restarts_openbao(t) and "delegate_to" in t]
    waits = [i for i, t in enumerate(tasks) if URI in t and "until" in t and "delegate_to" in t]
    problems = []
    if not restarts:
        problems.append("does not restart openbao on its own voter (delegate_to)")
    if not waits:
        problems.append("does not wait for the voter's health (uri with until, delegate_to)")
    if restarts and waits and min(waits) < max(restarts):
        problems.append("waits for health before the restart")
    return problems


OLD_HANDLER = [
    {
        "name": TOPIC,
        SYSTEMD: {"name": "openbao", "state": "restarted", "daemon_reload": True},
        "when": "ansible_virtualization_type | default('') != 'docker'",
    },
]

CONCURRENT_HANDLERS = [
    {"name": "Restart every node", "listen": TOPIC, SYSTEMD: {"name": "openbao", "state": "restarted"}},
    {"name": "Restart the rest", "listen": TOPIC, INCLUDE: ROLLING},
]

ROLLING_NOT_RUN_ONCE = [
    {"name": "Flag", "listen": TOPIC, SET_FACT: {"openbao_restart_pending": True}},
    {"name": "Roll", "listen": TOPIC, INCLUDE: ROLLING},
]

ROLLING_BEFORE_FLAG = [
    {"name": "Roll", "listen": TOPIC, INCLUDE: ROLLING, "run_once": True},
    {"name": "Flag", "listen": TOPIC, SET_FACT: {"openbao_restart_pending": True}},
]

DIRECT_RESTART_IN_ROLLING = [
    {"name": "Restart openbao", SYSTEMD: {"name": "openbao", "state": "restarted"}},
]

LOOP_NOT_FAIL_CLOSED = [
    {"name": "Each host", INCLUDE: HOST_STEP, "loop": "{{ openbao_restart_order }}"},
]

WAIT_BEFORE_RESTART = [
    {"name": "Wait", URI: {"url": "x"}, "until": "true", "delegate_to": "{{ h }}"},
    {"name": "Restart", SYSTEMD: {"name": "openbao", "state": "restarted"}, "delegate_to": "{{ h }}"},
]

RESTART_NOT_DELEGATED = [
    {"name": "Restart", SYSTEMD: {"name": "openbao", "state": "restarted"}},
    {"name": "Wait", URI: {"url": "x"}, "until": "true", "delegate_to": "{{ h }}"},
]


def test_handlers_restart_one_voter_at_a_time():
    assert handler_violations(yaml.safe_load((ROLE / "handlers" / "main.yml").read_text(encoding="utf-8"))) == []


def test_rolling_restart_is_a_sequential_fail_closed_loop():
    assert rolling_violations(yaml.safe_load((ROLE / "tasks" / ROLLING).read_text(encoding="utf-8"))) == []


def test_host_step_restarts_its_voter_then_waits():
    assert host_step_violations(yaml.safe_load((ROLE / "tasks" / HOST_STEP).read_text(encoding="utf-8"))) == []


@pytest.mark.parametrize(
    "handlers",
    [OLD_HANDLER, CONCURRENT_HANDLERS, ROLLING_NOT_RUN_ONCE, ROLLING_BEFORE_FLAG],
    ids=["old-direct-restart", "two-direct-restarts", "rolling-not-run-once", "rolling-before-flag"],
)
def test_handler_check_rejects_unsafe_shapes(handlers):
    assert handler_violations(handlers)


@pytest.mark.parametrize(
    "tasks",
    [DIRECT_RESTART_IN_ROLLING, LOOP_NOT_FAIL_CLOSED],
    ids=["direct-restart", "loop-not-fail-closed"],
)
def test_rolling_check_rejects_unsafe_shapes(tasks):
    assert rolling_violations(tasks)


@pytest.mark.parametrize(
    "tasks",
    [WAIT_BEFORE_RESTART, RESTART_NOT_DELEGATED],
    ids=["wait-before-restart", "restart-not-delegated"],
)
def test_host_step_check_rejects_unsafe_shapes(tasks):
    assert host_step_violations(tasks)
