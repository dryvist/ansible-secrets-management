"""Contract for permission-denied writes to reconcile's pinned RBAC policies."""

from pathlib import Path
import re
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles/openbao/tasks/init/08b-rbac-policy-writes.yml"
DEFAULTS = ROOT / "roles/openbao/defaults/main/05b-domain-policy-approle-names.yml"
RECONCILE_POLICY = ROOT / "roles/openbao/templates/openbao-reconcile-policy.hcl.j2"
WRITE_TASK = "Write the RBAC policies that are missing or changed"
OUTCOMES_TASK = "Resolve pinned RBAC policy write outcomes"
FAIL_TASK = "Fail when a pinned RBAC policy write has another error"
MARKER_TASK = "OpenBao pinned RBAC policies need a provisioning run"
PIN_NAMES_VAR = "openbao_reconcile_pinned_policy_names"
WRITE_RESULTS_VAR = "openbao_rbac_policy_write_results"
OUTCOMES_VAR = "openbao_pinned_rbac_write_outcomes"


def _task(name):
    for task in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if task.get("name") == name:
            return task
    raise AssertionError(f"task {name!r} not found in {TASKS}")


def _render(expression, variables, wrap=False):
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    source = "{{ " + expression + " }}" if wrap else expression
    return templar.template(trust_as_template(source))


def _when_fires(task, variables):
    return all(bool(_render(condition, variables, wrap=True)) for condition in task["when"])


class PinnedPolicyNames(unittest.TestCase):
    def test_names_derive_from_the_reconcile_template_pins(self):
        defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
        template_vars = re.findall(
            r"policy_name\s*==\s*(openbao_[A-Za-z0-9_]+_policy_name)",
            RECONCILE_POLICY.read_text(encoding="utf-8"),
        )
        list_exprs = defaults[PIN_NAMES_VAR]
        list_vars = [
            name
            for expression in list_exprs
            for name in re.findall(r"\b(openbao_[A-Za-z0-9_]+_policy_name)\b", expression)
        ]

        self.assertEqual(list_vars, template_vars)
        values = {name: defaults[name] for name in template_vars}
        self.assertEqual(
            [_render(expression, values) for expression in list_exprs],
            [values[name] for name in template_vars],
        )


class PinnedWriteOutcomes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
        template_vars = re.findall(
            r"policy_name\s*==\s*(openbao_[A-Za-z0-9_]+_policy_name)",
            RECONCILE_POLICY.read_text(encoding="utf-8"),
        )
        values = {name: defaults[name] for name in template_vars}
        cls.pinned_names = [
            _render(expression, values) for expression in defaults[PIN_NAMES_VAR]
        ]

    def test_only_pinned_reconcile_failures_are_deferred_for_classification(self):
        expression = _task(WRITE_TASK)["failed_when"]

        def fails(name, rc, reconcile):
            variables = {
                "item": {"name": name},
                "openbao_reconcile_mode": reconcile,
                PIN_NAMES_VAR: self.pinned_names,
            }
            if rc is not None:
                variables["rc"] = rc
            return bool(
                _render(
                    expression,
                    variables,
                    wrap=True,
                )
            )

        self.assertFalse(fails(self.pinned_names[0], 1, True))
        self.assertTrue(fails(self.pinned_names[0], 1, False))
        self.assertFalse(fails(self.pinned_names[0], None, True))
        self.assertTrue(fails(self.pinned_names[0], None, False))
        self.assertTrue(fails("other-policy", 1, True))
        self.assertFalse(fails(self.pinned_names[0], 0, True))

    def test_outcomes_split_permission_denials_from_every_other_pinned_error(self):
        expression = _task(OUTCOMES_TASK)["ansible.builtin.set_fact"][OUTCOMES_VAR]
        results = [
            {
                "item": {"name": self.pinned_names[0]},
                "rc": 1,
                "stderr": "permission denied: parameter policy is pinned",
            },
            {
                "item": {"name": self.pinned_names[1]},
                "rc": 1,
                "stderr": "connection refused",
            },
            {"item": {"name": self.pinned_names[1]}, "skipped": True, "stderr": "permission denied"},
            {"item": {"name": "other-policy"}, "rc": 1, "stderr": "permission denied"},
            {"item": {"name": self.pinned_names[0]}, "rc": 0, "stderr": ""},
        ]
        outcomes = _render(
            expression,
            {
                WRITE_RESULTS_VAR: {"results": results},
                PIN_NAMES_VAR: self.pinned_names,
            },
        )

        self.assertEqual(outcomes["permission_denied"], [self.pinned_names[0]])
        self.assertEqual(outcomes["other_failures"], [self.pinned_names[1]])

        missing_rc = _render(
            expression,
            {
                WRITE_RESULTS_VAR: {
                    "results": [
                        {"item": {"name": self.pinned_names[1]}, "failed": True, "stderr": ""}
                    ]
                },
                PIN_NAMES_VAR: self.pinned_names,
            },
        )
        self.assertEqual(missing_rc["other_failures"], [self.pinned_names[1]])

    def test_unexpected_failure_fails_and_marker_requires_a_denial(self):
        failed = _task(FAIL_TASK)
        marker = _task(MARKER_TASK)
        self.assertEqual(marker["name"], MARKER_TASK)
        self.assertFalse(marker.get("no_log", False))
        self.assertIs(marker["changed_when"], True)

        base = {
            "openbao_bootstrap_token": "defined",
            "openbao_reconcile_mode": True,
        }
        outcomes = {"permission_denied": [self.pinned_names[0]], "other_failures": []}
        self.assertFalse(_when_fires(failed, {**base, OUTCOMES_VAR: outcomes}))
        self.assertTrue(_when_fires(marker, {**base, OUTCOMES_VAR: outcomes}))
        self.assertEqual(
            _render(marker["ansible.builtin.debug"]["msg"], {OUTCOMES_VAR: outcomes}),
            f"needs provisioning run: {self.pinned_names[0]}",
        )
        self.assertFalse(
            _when_fires(
                marker,
                {**base, OUTCOMES_VAR: {"permission_denied": [], "other_failures": []}},
            )
        )
        self.assertFalse(
            _when_fires(
                marker,
                {**base, "openbao_reconcile_mode": False, OUTCOMES_VAR: outcomes},
            )
        )
        self.assertTrue(
            _when_fires(
                failed,
                {
                    **base,
                    OUTCOMES_VAR: {"permission_denied": [], "other_failures": [self.pinned_names[1]]},
                },
            )
        )

    def test_non_pinned_write_keeps_the_existing_loop_command_and_redaction(self):
        write = _task(WRITE_TASK)
        self.assertEqual(write["loop"], "{{ openbao_reachable_policies }}")
        self.assertEqual(write["ansible.builtin.command"]["cmd"], "bao policy write {{ item.name }} -")
        self.assertTrue(write["no_log"])
        self.assertTrue(write["changed_when"])
        self.assertEqual(write["register"], WRITE_RESULTS_VAR)


if __name__ == "__main__":
    unittest.main()
