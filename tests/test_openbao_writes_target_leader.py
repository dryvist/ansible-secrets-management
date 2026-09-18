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


def _write_addr_expr():
    tasks = yaml.safe_load(INIT_02.read_text(encoding="utf-8"))
    for task in tasks:
        fact = task.get("ansible.builtin.set_fact") or {}
        if "openbao_write_addr" in fact:
            return fact["openbao_write_addr"]
    raise AssertionError(
        "init/02 no longer sets openbao_write_addr -- provisioning writes are "
        "back on whichever node the bootstrap host happens to be."
    )


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


if __name__ == "__main__":
    unittest.main()
