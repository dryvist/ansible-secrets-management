"""Contract for the undeclared-live AppRole gate in 10d-approle-undeclared-live.yml.

Every task in this file iterates the DECLARED set (openbao_approles, filtered
to openbao_manageable_approles). An identity that exists in the store but was
never declared -- a rename that left the old name live, a manual break-glass
create nobody backfilled -- is a member of neither set, so reconciliation
never visits it, never bounds it, and never notices it again. This is the
only check in the role that catches that case; everywhere else assumes the
declared list is the whole truth.

Both directions render the REAL Jinja out of 10d-approle-undeclared-live.yml, never a
reimplementation -- a retyped copy of an expression tests the copy.
"""

from pathlib import Path
import json
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "10d-approle-undeclared-live.yml"

LIVE_NAMES_TASK = "Resolve the set of AppRole names that actually exist live"
UNDECLARED_TASK = "Assert every live AppRole is either declared or a named exception"
MISSING_TASK = "Warn about declared AppRoles that reconciliation cannot see live"


def _task(name):
    for t in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if t.get("name") == name:
            return t
    raise AssertionError(f"task {name!r} not found in {TASKS}")


def _trust(value):
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, list):
        return [_trust(v) for v in value]
    if isinstance(value, dict):
        return {k: _trust(v) for k, v in value.items()}
    return value


def _render(expr, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = _trust(variables)
    return templar.template(trust_as_template(expr))


def live_names(rc, keys=None):
    """Render the set_fact that turns a `bao list` result into a name list."""
    expr = _task(LIVE_NAMES_TASK)["ansible.builtin.set_fact"][
        "openbao_approle_live_names"
    ]
    # `bao list -format=json` prints a bare array, not the API envelope.
    stdout = json.dumps(keys or [])
    return _render(expr, {"openbao_approle_live_list": {"rc": rc, "stdout": stdout}})


def undeclared(live, declared, exceptions=()):
    """Render the assert task's own _undeclared expression."""
    task_vars = _task(UNDECLARED_TASK)["vars"]
    variables = {
        "openbao_approle_live_names": live,
        "openbao_approles": [{"name": n} for n in declared],
        "openbao_approle_undeclared_exceptions": [
            {"name": n, "reason": "test"} for n in exceptions
        ],
    }
    variables["_declared"] = _render(task_vars["_declared"], variables)
    variables["_excepted"] = _render(task_vars["_excepted"], variables)
    return _render(task_vars["_undeclared"], variables)


def missing(declared, live):
    """Render the warn task's own _missing expression."""
    expr = _task(MISSING_TASK)["vars"]["_missing"]
    return _render(expr, {
        "openbao_manageable_approles": [{"name": n} for n in declared],
        "openbao_approle_live_names": live,
    })


class TestLiveNames(unittest.TestCase):
    def test_successful_list_returns_the_keys(self):
        self.assertEqual(live_names(0, ["apps", "orphan"]), ["apps", "orphan"])

    def test_bare_array_stdout_is_parsed_not_dropped(self):
        # Regression: reading .data.keys off the bare array resolved to [],
        # so the retirement loop and the assert both saw an empty live set.
        names = live_names(0, ["ansible", "apps", "orphan"])
        self.assertEqual(names, ["ansible", "apps", "orphan"])
        self.assertEqual(undeclared(names, ["apps"], ["ansible"]), ["orphan"])

    def test_empty_stdout_on_success_resolves_to_empty(self):
        expr = _task(LIVE_NAMES_TASK)["ansible.builtin.set_fact"][
            "openbao_approle_live_names"
        ]
        self.assertEqual(
            _render(expr, {"openbao_approle_live_list": {"rc": 0, "stdout": ""}}), []
        )

    def test_nonzero_rc_resolves_to_empty_not_unknown(self):
        # An empty mount on a fresh cluster reads this way too -- the FAIL
        # task (not this one) is what distinguishes "empty" from "denied".
        self.assertEqual(live_names(2), [])


class TestUndeclaredLive(unittest.TestCase):
    def test_live_identity_declared_nowhere_is_flagged(self):
        self.assertEqual(
            undeclared(["apps", "orphan-role"], ["apps"]),
            ["orphan-role"],
        )

    def test_named_exception_is_covered_not_flagged(self):
        self.assertEqual(
            undeclared(["apps", "legacy-role"], ["apps"], exceptions=["legacy-role"]),
            [],
        )

    def test_fully_declared_live_set_passes(self):
        self.assertEqual(undeclared(["apps", "admin"], ["apps", "admin"]), [])

    def test_empty_live_set_passes(self):
        self.assertEqual(undeclared([], ["apps"]), [])


class TestMissingLive(unittest.TestCase):
    def test_declared_role_not_yet_live_is_named(self):
        self.assertEqual(missing(["apps", "new-role"], ["apps"]), ["new-role"])

    def test_fully_live_declared_set_is_clean(self):
        self.assertEqual(missing(["apps"], ["apps"]), [])


LIST_TASK = "List every AppRole that actually exists in the store"
DELETE_TASK = "Delete retired AppRoles that still exist live"


class TestBaoCallsRunOnTheCliHost(unittest.TestCase):
    """A provisioning token is bound to the operator's source class. Every bao
    call in init/10 runs on openbao_cli_host against openbao_cli_addr; the
    listing and the retired-role delete ran on the node against its own
    address, so the first converge with a source-bound token read the refusal
    as the policy gap and stopped before any role was reconciled."""

    def test_the_listing_and_the_delete_carry_the_full_cli_switch(self):
        for name in (LIST_TASK, DELETE_TASK):
            task = _task(name)
            self.assertEqual(task["environment"]["BAO_ADDR"], "{{ openbao_cli_addr }}", name)
            self.assertEqual(task["delegate_to"], "{{ openbao_cli_host }}", name)
            self.assertEqual(task["become"], "{{ openbao_cli_become }}", name)
            self.assertEqual(task["vars"]["ansible_become"], "{{ openbao_cli_become }}", name)

    def test_no_task_in_the_file_is_pinned_to_the_node_address(self):
        for task in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
            env = task.get("environment") or {}
            self.assertNotEqual(env.get("BAO_ADDR"), "{{ openbao_write_addr }}", task.get("name"))


if __name__ == "__main__":
    unittest.main()
