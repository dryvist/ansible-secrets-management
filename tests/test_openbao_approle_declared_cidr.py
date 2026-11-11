"""Explicit AppRole source-address binds never fall back when empty."""

from pathlib import Path
import os
from unittest import mock
import unittest

import yaml

from test_openbao_hatchet_killtest_policy_reach import REQUIRED_ENV, render, role_defaults


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles/openbao/tasks/init/10-approles.yml"
GUARD = "Refuse AppRoles with an empty declared source-address bind"
ROLE_NAME = "cidr-fixture"
CLASS_CIDRS = "192.0.2.0/24"


def _rendered(expression, variables):
    with mock.patch.dict(os.environ, REQUIRED_ENV):
        return render({**role_defaults(), **variables}, expression)


def _parameters(declaration):
    variables = {
        "openbao_approles": [{"name": ROLE_NAME, "policy": ROLE_NAME, **declaration}],
        "openbao_approle_cidr_class_map": {ROLE_NAME: "machine"},
        "openbao_approle_cidr_classes": {"machine": CLASS_CIDRS},
    }
    return _rendered("{{ openbao_approle_cli_parameters }}", variables)[ROLE_NAME]


def _guard_task():
    tasks = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
    return next(task for task in tasks if task.get("name") == GUARD)


class TestDeclaredSourceAddressBind(unittest.TestCase):
    def test_empty_declared_bind_renders_empty_instead_of_the_class(self):
        params = _parameters({"secret_id_bound_cidrs": ""})
        self.assertEqual(params["secret_id_bound_cidrs"], "")
        self.assertEqual(params["token_bound_cidrs"], "")

    def test_absent_bind_uses_the_role_class(self):
        params = _parameters({})
        self.assertEqual(params["secret_id_bound_cidrs"], CLASS_CIDRS)
        self.assertEqual(params["token_bound_cidrs"], CLASS_CIDRS)

    def test_declared_host_bind_renders_trimmed_exactly(self):
        host_cidr = "192.0.2.7/32"
        params = _parameters({"secret_id_bound_cidrs": f" {host_cidr} "})
        self.assertEqual(params["secret_id_bound_cidrs"], host_cidr)
        self.assertEqual(params["token_bound_cidrs"], host_cidr)

    def test_assert_fails_and_names_roles_with_an_empty_declared_bind(self):
        task = _guard_task()
        names_expr = task["vars"]["_empty_declared_source_address_binds"]
        bad_role = {"name": ROLE_NAME, "secret_id_bound_cidrs": ""}
        empty_names = _rendered(names_expr, {"openbao_approle_config_targets": [bad_role]})
        self.assertEqual(empty_names, [ROLE_NAME])

        assert_expr = task["ansible.builtin.assert"]["that"][0]
        self.assertFalse(_rendered("{{ " + assert_expr + " }}", {
            "_empty_declared_source_address_binds": empty_names,
        }))
        fail_msg = _rendered(task["ansible.builtin.assert"]["fail_msg"], {
            "_empty_declared_source_address_binds": empty_names,
        })
        self.assertIn(ROLE_NAME, fail_msg)
        self.assertIn("declared source-address bind that is empty", fail_msg)

    def test_selected_targets_limit_the_guard_and_unset_targets_fall_back(self):
        task = _guard_task()
        names_expr = task["vars"]["_empty_declared_source_address_binds"]
        bad_role = {"name": ROLE_NAME, "secret_id_bound_cidrs": ""}
        selected = _rendered(names_expr, {
            "openbao_approle_config_targets": [{"name": "selected-role"}],
            "openbao_manageable_approles": [bad_role],
        })
        fallback = _rendered(names_expr, {"openbao_manageable_approles": [bad_role]})
        self.assertEqual(selected, [])
        self.assertEqual(fallback, [ROLE_NAME])

    def test_guard_precedes_remote_approle_reads_and_writes(self):
        tasks = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
        names = [task["name"] for task in tasks]
        guard_index = names.index(GUARD)
        for remote_task in (
            "Assert every live AppRole is either declared or a named exception",
            "Check whether each AppRole already exists",
            "Create the missing AppRoles bound to their policy",
        ):
            self.assertLess(guard_index, names.index(remote_task), remote_task)


if __name__ == "__main__":
    unittest.main()
