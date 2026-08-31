"""A denied AppRole existence check must never be read as absence.

`Check whether each AppRole already exists` runs under `failed_when: false`, so
a 403 and a genuinely missing role both return a non-zero rc. The create task
treated any non-zero rc as "missing" and fired a privileged create, which 403'd
in turn -- so the run died reporting a create failure rather than the access gap
that caused it.

Reachable by design, not only by misconfiguration: the reconcile policy
enumerates AppRole paths by name and is excluded from its own managed set, so a
newly declared AppRole has no grant for the reconcile identity until an operator
run rewrites that policy.

These render the REAL expressions out of the task file, never a reimplementation
of them -- retyping a template performs its own escaping and can pass while the
real expression fails.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "10-approles.yml"
DENIED_TASK = "FAIL -- the existence check was DENIED, so absence cannot be concluded"
CREATE_TASK = "Create the missing AppRoles bound to their policy"

DENIED_ERR = "Code: 403. Errors:\n\n* 1 error occurred:\n\t* permission denied\n"
ABSENT_ERR = "No value found at auth/approle/role/nope\n"


def _task(name):
    for t in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if t.get("name") == name:
            return t
    raise AssertionError(f"task {name!r} not found in {TASKS}")


def _render(expr, variables, wrap=True):
    """Render an expression from the task file.

    `wrap` adds the braces a bare `when:` condition lacks; a `vars:` value is
    already a full `{{ ... }}` template and must be passed through untouched,
    or it double-braces into a syntax error.
    """
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    return templar.template(
        trust_as_template("{{ " + expr + " }}" if wrap else expr)
    )


def result(name, rc, stderr):
    return {"item": {"name": name}, "rc": rc, "stderr": stderr}


def denied_names(results):
    """Render the guard's own `_denied` expression."""
    expr = _task(DENIED_TASK)["vars"]["_denied"]
    return _render(
        expr, {"openbao_approle_checks": {"results": results}}, wrap=False
    )


def create_fires(check):
    """Render the create task's own rc/stderr conditions for one check result."""
    conds = [c for c in _task(CREATE_TASK)["when"] if "item.1" in str(c)]
    assert conds, "create task has no item.1 conditions"
    return all(
        _render(c, {"item": [{"name": check["item"]["name"]}, check]})
        for c in conds
    )


class DeniedIsNotAbsent(unittest.TestCase):
    def test_a_denied_check_is_reported_as_denied(self):
        self.assertEqual(
            denied_names([result("iac-platform-deploy", 2, DENIED_ERR)]),
            ["iac-platform-deploy"],
        )

    def test_a_denied_check_does_NOT_fire_the_create(self):
        # The defect itself: a 403 must never reach a privileged create.
        self.assertFalse(create_fires(result("iac-platform-deploy", 2, DENIED_ERR)))

    def test_a_genuinely_absent_role_still_fires_the_create(self):
        # The guard must not disable the feature it protects.
        self.assertTrue(create_fires(result("brand-new", 2, ABSENT_ERR)))

    def test_an_absent_role_is_not_reported_as_denied(self):
        self.assertEqual(denied_names([result("brand-new", 2, ABSENT_ERR)]), [])

    def test_an_existing_role_neither_fires_nor_is_denied(self):
        ok = result("apps", 0, "")
        self.assertFalse(create_fires(ok))
        self.assertEqual(denied_names([ok]), [])

    def test_skipped_results_are_ignored(self):
        self.assertEqual(
            denied_names([{"skipped": True, "item": {"name": "inert"}}]), []
        )


if __name__ == "__main__":
    unittest.main()
