"""Provisioning writes must be sent to the Raft leader, not to whichever node
happens to be the bootstrap host.

Raft accepts a write only on the active node. A standby is expected to forward
it, and that standby->leader hop is the one that intermittently fails in this
estate: the client sees "cannot write to readonly storage" on a write and
"internal error" on an AppRole login. The ingress already avoids the hop by
probing /v1/sys/health WITHOUT standbyok, which evicts every standby from the
pool -- but the converge never traversed the ingress. It ran `bao` against
BAO_ADDR = openbao_api_addr, this node's OWN listener, and
openbao_bootstrap_host is the alphabetically-first group member, picked for
determinism and not for leadership. So every policy/AppRole/engine/KV write in
the converge went over exactly the hop the ingress exists to bypass, for as
long as the leader was any node but the first.

Two things are asserted:

  1. The real openbao_write_addr expression out of init/02 resolves to the
     leader when the cluster reports one, and degrades to this node's own
     listener when it does not -- so a status read that fails or comes back
     leaderless leaves the pre-fix behaviour rather than breaking the converge.

  2. No task on the bootstrap host's provisioning path still pins BAO_ADDR to
     openbao_api_addr. init/01 and init/02 are the deliberate exceptions: they
     probe and initialize THIS node, before a leader is guaranteed to exist.

The expression is rendered out of the task file rather than retyped -- a
retyped template performs its own escaping and can pass while the real one
fails.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles/openbao/tasks"
INIT_02 = TASKS / "init/02-initialize-cluster.yml"

# Node-local by design: they talk to THIS node before/while a leader exists.
NODE_LOCAL = {"01-preflight-and-cluster-probe.yml", "02-initialize-cluster.yml"}

SELF_ADDR = "http://192.0.2.10:8200"
LEADER_ADDR = "http://192.0.2.11:8200"


def _render(expr, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    return templar.template(trust_as_template(expr))


def _set_fact_expr(name):
    tasks = yaml.safe_load(INIT_02.read_text(encoding="utf-8"))
    for task in tasks:
        fact = task.get("ansible.builtin.set_fact") or {}
        if name in fact:
            return fact[name]
    raise AssertionError(f"init/02 no longer sets {name}")


def _write_addr_expr():
    try:
        return _set_fact_expr("openbao_write_addr")
    except AssertionError:
        raise AssertionError(
            "init/02 no longer sets openbao_write_addr -- provisioning writes are "
            "back on whichever node the bootstrap host happens to be."
        ) from None


def _walk_tasks(node):
    """Every task mapping in a task file, descending into block/rescue/always."""
    if isinstance(node, list):
        for item in node:
            yield from _walk_tasks(item)
    elif isinstance(node, dict):
        yield node
        for key in ("block", "rescue", "always"):
            if key in node:
                yield from _walk_tasks(node[key])


def _resolve(stdout):
    return _render(
        _write_addr_expr(),
        {
            "openbao_leader_status_raw": {"stdout": stdout},
            "openbao_api_addr": SELF_ADDR,
        },
    ).strip()


class WriteAddrResolution(unittest.TestCase):
    def test_a_reported_leader_wins(self):
        self.assertEqual(
            _resolve('{"initialized": true, "leader_address": "%s"}' % LEADER_ADDR),
            LEADER_ADDR,
        )

    def test_this_node_being_the_leader_is_not_a_special_case(self):
        self.assertEqual(_resolve('{"leader_address": "%s"}' % SELF_ADDR), SELF_ADDR)

    def test_an_empty_leader_address_falls_back_to_this_node(self):
        # A sealed or freshly initialized node reports "" here.
        self.assertEqual(_resolve('{"leader_address": ""}'), SELF_ADDR)

    def test_a_status_with_no_leader_field_falls_back(self):
        self.assertEqual(_resolve('{"initialized": false}'), SELF_ADDR)

    def test_a_failed_status_read_falls_back_rather_than_breaking(self):
        # `failed_when: false` leaves stdout empty when the command errors.
        self.assertEqual(_resolve(""), SELF_ADDR)


class NoProvisioningWriteIsPinnedToThisNode(unittest.TestCase):
    def test_bao_addr_uses_the_resolved_write_address(self):
        offenders = [
            str(path.relative_to(ROOT))
            for path in sorted(TASKS.rglob("*.yml"))
            if path.name not in NODE_LOCAL
            and 'BAO_ADDR: "{{ openbao_api_addr }}"' in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(
            offenders,
            [],
            "these run on the bootstrap host and would write through the "
            "standby forwarding hop: " + ", ".join(offenders),
        )

    def test_the_node_local_exceptions_still_exist(self):
        # Guards the negative control above: if these files are renamed the
        # exception set silently stops excluding anything real.
        for name in NODE_LOCAL:
            self.assertTrue(
                (TASKS / "init" / name).is_file(), f"{name} is gone; update NODE_LOCAL"
            )


RECONCILE_ADDR = "https://openbao.ingress.example.test"


def _resolve_cli(reconcile_addr):
    variables = {
        "openbao_reconcile_addr": reconcile_addr,
        "openbao_write_addr": LEADER_ADDR,
        "inventory_hostname": "openbao-11",
    }
    return {
        name: _render(_set_fact_expr(name), variables)
        for name in ("openbao_cli_host", "openbao_cli_addr", "openbao_cli_become")
    }


class BaoCliRunsOnTheController(unittest.TestCase):
    """The provisioning reads cost one module execution per item on the
    target (measured: 559s for the policy reads, 328s for the AppRole checks).
    init/02 resolves ONE switch that moves them to the controller when it can
    reach the store, and falls back to the node for a first bootstrap."""

    def test_with_a_controller_endpoint_the_cli_runs_locally(self):
        cli = _resolve_cli(RECONCILE_ADDR)
        self.assertEqual(cli["openbao_cli_host"], "localhost")
        self.assertEqual(cli["openbao_cli_addr"], RECONCILE_ADDR)
        self.assertIs(cli["openbao_cli_become"], False)

    def test_without_one_the_cli_stays_on_the_node_with_become(self):
        cli = _resolve_cli("")
        self.assertEqual(cli["openbao_cli_host"], "openbao-11")
        self.assertEqual(cli["openbao_cli_addr"], LEADER_ADDR)
        self.assertIs(cli["openbao_cli_become"], True)


# The loops that were measured, by task name. A revert to openbao_write_addr
# on either puts the minutes back without failing anything else.
MEASURED_READ_LOOPS = {
    "init/08-rbac-policies.yml": "Read existing RBAC policy contents",
    "init/10-approles.yml": "Check whether each AppRole already exists",
}


class DelegatedBaoCallsAreConsistent(unittest.TestCase):
    def _delegated_tasks(self):
        for path in sorted(TASKS.rglob("*.yml")):
            for task in _walk_tasks(yaml.safe_load(path.read_text(encoding="utf-8"))):
                env = task.get("environment") or {}
                addr = env.get("BAO_ADDR") if isinstance(env, dict) else None
                if addr == "{{ openbao_cli_addr }}" or task.get("delegate_to") == "{{ openbao_cli_host }}":
                    yield str(path.relative_to(TASKS)), task

    def test_the_switch_is_applied_whole_or_not_at_all(self):
        # A controller-side call against a node-local address cannot reach it;
        # a node-side call without become cannot run bao. Either half alone is
        # a converge that fails somewhere far from the cause.
        broken = []
        for name, task in self._delegated_tasks():
            ok = (
                task["environment"]["BAO_ADDR"] == "{{ openbao_cli_addr }}"
                and task.get("delegate_to") == "{{ openbao_cli_host }}"
                and task.get("become") == "{{ openbao_cli_become }}"
                and (task.get("vars") or {}).get("ansible_become") == "{{ openbao_cli_become }}"
            )
            if not ok:
                broken.append(f"{name}: {task.get('name')}")
        self.assertEqual(broken, [], "partial openbao_cli_* switch on: " + ", ".join(broken))

    def test_the_measured_read_loops_run_on_the_controller(self):
        delegated = {(name, task.get("name")) for name, task in self._delegated_tasks()}
        for path, task_name in MEASURED_READ_LOOPS.items():
            self.assertIn((path, task_name), delegated, f"{path}: '{task_name}' is back on the target")


if __name__ == "__main__":
    unittest.main()
