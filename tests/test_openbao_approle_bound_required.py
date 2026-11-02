"""The unbound-CIDR escape hatch is a real boolean, and bound-required roles never go unbound."""

import os
from pathlib import Path
import unittest
from unittest import mock

import yaml

from test_openbao_hatchet_killtest_policy_reach import REQUIRED_ENV, render, role_defaults

ROOT = Path(__file__).resolve().parents[1]
APPROLE_TASKS = ROOT / "roles/openbao/tasks/init/10-approles.yml"
HATCH = "OPENBAO_APPROLE_ALLOW_UNBOUND_CIDRS"


def _rendered(expression, **env):
    with mock.patch.dict(os.environ, {**REQUIRED_ENV, **env}):
        return render(role_defaults(), "{{ " + expression + " }}")


class EscapeHatch(unittest.TestCase):
    def test_only_a_true_value_opens_the_hatch(self):
        for value, expected in [("", False), ("false", False), ("False", False), ("0", False),
                                ("no", False), ("off", False), ("anything", False),
                                ("1", True), ("true", True), ("TRUE", True), (" yes ", True), ("on", True)]:
            with self.subTest(value=value):
                self.assertIs(_rendered("openbao_approle_allow_unbound_cidrs", **{HATCH: value}), expected)

    def test_every_consumer_reads_it_as_a_boolean(self):
        conditions = [condition for task in yaml.safe_load(APPROLE_TASKS.read_text(encoding="utf-8"))
                      for condition in task.get("when", []) if "allow_unbound" in condition]
        self.assertEqual(conditions, ["not (openbao_approle_allow_unbound_cidrs | bool)",
                                      "openbao_approle_allow_unbound_cidrs | bool"])


class BoundRequired(unittest.TestCase):
    def test_hatchet_killtest_renders_both_cidrs_from_the_machine_class(self):
        params = _rendered("openbao_approle_cli_parameters['hatchet-killtest']",
                           OPENBAO_MANAGEMENT_CIDRS="192.0.2.0/24")
        self.assertEqual(params["secret_id_bound_cidrs"], "192.0.2.0/24")
        self.assertEqual(params["token_bound_cidrs"], "192.0.2.0/24")
        self.assertEqual(_rendered("openbao_approle_bound_required_unbound",
                                   OPENBAO_MANAGEMENT_CIDRS="192.0.2.0/24"), [])

    def test_empty_cidrs_are_refused_even_with_the_hatch_open(self):
        self.assertEqual(_rendered("openbao_approle_bound_required_unbound", OPENBAO_MANAGEMENT_CIDRS=""),
                         ["hatchet-killtest"])
        self.assertEqual(
            _rendered("openbao_approle_bound_required_unbound", OPENBAO_MANAGEMENT_CIDRS="", **{HATCH: "true"}),
            ["hatchet-killtest"])

    def test_the_refusal_runs_before_creation_and_ignores_the_hatch(self):
        names = [task["name"] for task in yaml.safe_load(APPROLE_TASKS.read_text(encoding="utf-8"))]
        guard = "Refuse an unbound secret_id or token CIDR on a bound-required AppRole"
        task = next(t for t in yaml.safe_load(APPROLE_TASKS.read_text(encoding="utf-8")) if t["name"] == guard)
        self.assertEqual(task["ansible.builtin.assert"]["that"],
                         "openbao_approle_bound_required_unbound | length == 0")
        self.assertNotIn("allow_unbound", str(task.get("when")))
        self.assertLess(names.index(guard), names.index("Create the missing AppRoles bound to their policy"))


if __name__ == "__main__":
    unittest.main()
