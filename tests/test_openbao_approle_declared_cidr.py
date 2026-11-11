"""Explicit AppRole source-address binds never fall back when empty."""

from pathlib import Path
import os
from unittest import mock
import unittest

import yaml

from test_openbao_hatchet_killtest_policy_reach import REQUIRED_ENV, render, role_defaults


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles/openbao/tasks/init/10-approles.yml"
DEFAULTS = ROOT / "roles/openbao/defaults/main/08b-cidr-and-unlock.yml"
GUARD = "Refuse an unbound secret_id or token CIDR on a bound-required AppRole"
ROLE_NAME = "cidr-fixture"
CLASS_CIDRS = "192.0.2.0/24"


def _rendered(expression, variables, **env):
    with mock.patch.dict(os.environ, {**REQUIRED_ENV, **env}):
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


def _empty_bind_names(targets, parameters, manageable=None):
    variables = {"openbao_approle_cli_parameters": parameters}
    if targets is not None:
        variables["openbao_approle_config_targets"] = targets
    if manageable is not None:
        variables["openbao_manageable_approles"] = manageable
    return _rendered("{{ openbao_approle_bound_required_unbound }}", variables)


class TestDeclaredSourceAddressBind(unittest.TestCase):
    def test_empty_declared_bind_renders_empty_instead_of_the_class(self):
        params = _parameters({"secret_id_bound_cidrs": ""})
        self.assertEqual(params["secret_id_bound_cidrs"], "")
        self.assertEqual(params["token_bound_cidrs"], "")

    def test_whitespace_only_class_value_is_empty_and_unsupplied(self):
        classes = _rendered("{{ openbao_approle_cidr_classes }}", {},
                            OPENBAO_MANAGEMENT_CIDRS=" \t ")
        unsupplied = _rendered("{{ openbao_approle_unsupplied_cidr_classes }}", {},
                               OPENBAO_MANAGEMENT_CIDRS=" \t ")
        self.assertEqual(classes["machine"], "")
        self.assertIn("machine", unsupplied)

    def test_absent_bind_uses_the_role_class(self):
        params = _parameters({})
        self.assertEqual(params["secret_id_bound_cidrs"], CLASS_CIDRS)
        self.assertEqual(params["token_bound_cidrs"], CLASS_CIDRS)

    def test_declared_host_bind_renders_trimmed_exactly(self):
        host_cidr = "192.0.2.7/32"
        params = _parameters({"secret_id_bound_cidrs": f" {host_cidr} "})
        self.assertEqual(params["secret_id_bound_cidrs"], host_cidr)
        self.assertEqual(params["token_bound_cidrs"], host_cidr)

    def test_one_item_list_bind_renders_exactly(self):
        host_cidr = "192.0.2.7/32"
        params = _parameters({"secret_id_bound_cidrs": [host_cidr]})
        self.assertEqual(params["secret_id_bound_cidrs"], host_cidr)
        self.assertEqual(params["token_bound_cidrs"], host_cidr)

    def test_two_item_list_bind_joins_with_a_comma(self):
        cidrs = ["192.0.2.7/32", "198.51.100.0/24"]
        params = _parameters({"secret_id_bound_cidrs": cidrs})
        expected = ",".join(cidrs)
        self.assertEqual(params["secret_id_bound_cidrs"], expected)
        self.assertEqual(params["token_bound_cidrs"], expected)

    def test_blank_list_items_and_null_use_the_empty_bind_guard(self):
        for bind in ([""], ["  "], None, [], [None], ["192.0.2.7/32", None], ["192.0.2.7/32", "  "]):
            with self.subTest(bind=bind):
                params = _parameters({"secret_id_bound_cidrs": bind})
                bad_role = {"name": ROLE_NAME, "secret_id_bound_cidrs": bind}
                empty_names = _empty_bind_names([bad_role], {ROLE_NAME: params})
                self.assertEqual(params["secret_id_bound_cidrs"], "")
                self.assertEqual(empty_names, [ROLE_NAME])

    def test_declared_empty_bind_check_is_single_and_uses_normalized_parameters(self):
        tasks = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
        guards = [task for task in tasks
                  if task.get("ansible.builtin.assert", {}).get("that")
                  == "openbao_approle_bound_required_unbound | length == 0"]
        self.assertEqual(len(guards), 1)
        defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
        empty_names_expr = defaults["openbao_approle_bound_required_unbound"]
        self.assertIn("openbao_approle_cli_parameters[_approle.name]", empty_names_expr)
        self.assertNotIn("_approle.secret_id_bound_cidrs", empty_names_expr)

    def test_assert_fails_and_names_roles_with_an_empty_declared_bind(self):
        task = _guard_task()
        bad_role = {"name": ROLE_NAME, "secret_id_bound_cidrs": ""}
        params = _parameters({"secret_id_bound_cidrs": ""})
        empty_names = _empty_bind_names([bad_role], {ROLE_NAME: params})
        self.assertEqual(empty_names, [ROLE_NAME])

        assert_expr = task["ansible.builtin.assert"]["that"]
        self.assertFalse(_rendered("{{ " + assert_expr + " }}", {
            "openbao_approle_bound_required_unbound": empty_names,
        }))
        fail_msg = _rendered(task["ansible.builtin.assert"]["fail_msg"], {
            "openbao_approle_bound_required_unbound": empty_names,
        })
        self.assertIn(ROLE_NAME, fail_msg)
        self.assertIn("empty declared source-address bind", fail_msg)

    def test_selected_targets_limit_the_guard_and_unset_targets_fall_back(self):
        bad_role = {"name": ROLE_NAME, "secret_id_bound_cidrs": ""}
        parameters = {ROLE_NAME: _parameters({"secret_id_bound_cidrs": ""})}
        selected = _empty_bind_names([{"name": "selected-role"}], parameters, [bad_role])
        fallback = _empty_bind_names(None, parameters, [bad_role])
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
