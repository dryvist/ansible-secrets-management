"""Delegation contract for the reconcile-mode policy-sync pair in
roles/openbao/tasks/init/02b-policy-sync.yml.

The only identity that ever passes the capability check below is the inert
openbao-policy-sync AppRole (defaults/main/07f-workstation-approles.yml),
which is bound to the WORKSTATION CIDR class
(defaults/main/08b-cidr-and-unlock.yml) -- a token issued to it is usable
only from the controller. Both tasks used to run ON the OpenBao node against
openbao_write_addr (the node's own bind address), so the one token that
could ever pass the capability check always failed to reach the store from
there: observed live, "Ask..." came back ok but without the update
capability, and "Sync..." SKIPPED, which then starved init/07's
controller-delegated calls of the sync they needed.

The fix delegates both tasks to the controller exactly like every other
reconcile-gated read/write in this role from init/03 onward
(openbao_cli_host/_addr/_become, resolved in
defaults/main/00-install-and-node.yml) -- the same switch the reconcile
login itself uses via openbao_reconcile_addr.

This parses the REAL task file rather than reimplementing it.
"""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "02b-policy-sync.yml"

ASK_TASK = "Ask whether this identity may sync the reconcile policy"
SYNC_TASK = "Sync the reconcile policy from the declared set (policy-sync)"


def _task(name):
    for t in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if t.get("name") == name:
            return t
    raise AssertionError(f"task {name!r} not found in {TASKS}")


class PolicySyncPairRunsFromTheController(unittest.TestCase):
    def test_ask_task_delegates_to_the_controller(self):
        task = _task(ASK_TASK)
        self.assertEqual(task.get("delegate_to"), "{{ openbao_cli_host }}")

    def test_sync_task_delegates_to_the_controller(self):
        task = _task(SYNC_TASK)
        self.assertEqual(task.get("delegate_to"), "{{ openbao_cli_host }}")

    def test_ask_task_uses_the_controller_reachable_address(self):
        task = _task(ASK_TASK)
        self.assertEqual(
            task["environment"]["BAO_ADDR"], "{{ openbao_cli_addr }}"
        )
        # Never the node's own bind address -- that is exactly the bug: the
        # workstation-bound policy-sync token cannot reach it from there.
        self.assertNotEqual(
            task["environment"]["BAO_ADDR"], "{{ openbao_write_addr }}"
        )

    def test_sync_task_uses_the_controller_reachable_address(self):
        task = _task(SYNC_TASK)
        self.assertEqual(
            task["environment"]["BAO_ADDR"], "{{ openbao_cli_addr }}"
        )
        self.assertNotEqual(
            task["environment"]["BAO_ADDR"], "{{ openbao_write_addr }}"
        )

    def test_both_tasks_do_not_escalate_on_the_controller(self):
        for name in (ASK_TASK, SYNC_TASK):
            task = _task(name)
            self.assertEqual(task.get("become"), "{{ openbao_cli_become }}")
            self.assertEqual(
                task.get("vars", {}).get("ansible_become"),
                "{{ openbao_cli_become }}",
            )

    def test_conditions_and_no_log_are_unchanged(self):
        # The fix is delegation only -- the reconcile-mode gating and the
        # no_log on both tasks must survive untouched.
        ask = _task(ASK_TASK)
        sync = _task(SYNC_TASK)
        self.assertTrue(ask.get("no_log"))
        self.assertTrue(sync.get("no_log"))
        self.assertIn("openbao_bootstrap_token is defined", ask["when"])
        self.assertIn("openbao_reconcile_mode | default(false)", ask["when"])
        self.assertIn("openbao_bootstrap_token is defined", sync["when"])
        self.assertIn("openbao_reconcile_mode | default(false)", sync["when"])


if __name__ == "__main__":
    unittest.main()
