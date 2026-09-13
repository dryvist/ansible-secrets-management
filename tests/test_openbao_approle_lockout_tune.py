"""The AppRole auth mount's login lockout must stay wider than the mount
default, or a converge that silently drops the tune reverts it to 5 failures
per 15 minutes -- locking a shared workstation alias on ordinary retry noise.

This renders the REAL tune task's `cmd`, `vars` and `when`, never a
reimplementation of them, so a renamed variable, a dropped flag, or a broken
key name fails here instead of only at converge time. A live
`sys/auth/approle/tune` read has NO nested `user_lockout_config` object -- the
fields sit flat under `.data` with a `user_` prefix and integer seconds
(`user_lockout_threshold`, `user_lockout_duration`,
`user_lockout_counter_reset_duration`), which is the shape exercised below.
"""

import json
from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main/08a-admin-and-ttls.yml"
TASKS = ROOT / "roles/openbao/tasks/init/09-auth-methods-and-terrakube-jwt.yml"
TASK_NAME = "Tune the AppRole mount login lockout"

DEFAULT_VARS = ["openbao_approle_lockout_threshold", "openbao_approle_lockout_duration",
                "openbao_approle_lockout_counter_reset"]


def _defaults():
    return yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))


def _task():
    for task in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if task.get("name") == TASK_NAME:
            return task
    raise AssertionError(f"task {TASK_NAME!r} not found in {TASKS}")


def _mark_templates(value):
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, dict):
        return {k: _mark_templates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mark_templates(v) for v in value]
    return value


def _render(template, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = _mark_templates(variables)
    return templar.template(trust_as_template(template))


def _resolve_task_vars(task, base_variables):
    """Resolve the task's own `vars:` in declaration order, matching how
    Ansible builds the namespace a `when`/`cmd` templates against."""
    namespace = dict(base_variables)
    for name, template in task.get("vars", {}).items():
        namespace[name] = _render(template, namespace)
    return namespace


def _mount_tune_read(threshold, duration_s, counter_reset_duration_s):
    return {
        "rc": 0,
        "stdout": json.dumps({"data": {
            "user_lockout_threshold": threshold,
            "user_lockout_duration": duration_s,
            "user_lockout_counter_reset_duration": counter_reset_duration_s,
        }}),
    }


class TestApproleLockoutTune(unittest.TestCase):
    def setUp(self):
        self.variables = _defaults()
        # Only exercising the drift-comparison condition, so satisfy the
        # sibling "openbao_bootstrap_token is defined" gate with a stand-in.
        self.variables["openbao_bootstrap_token"] = "test-token"
        self.task = _task()

    def test_lockout_defaults_are_declared_and_non_empty(self):
        for name in DEFAULT_VARS:
            self.assertIn(name, self.variables)
            self.assertTrue(str(self.variables[name]))

    def test_lockout_defaults_are_integer_seconds(self):
        # The tune read returns durations as integer seconds; a "5m"-style
        # string here would compare unequal to a matching live read forever.
        self.assertIsInstance(self.variables["openbao_approle_lockout_duration"], int)
        self.assertIsInstance(self.variables["openbao_approle_lockout_counter_reset"], int)

    def test_tune_command_renders_every_lockout_default_in_seconds(self):
        cmd = _render(self.task["ansible.builtin.command"]["cmd"], self.variables)
        self.assertIn(f"-user-lockout-threshold={self.variables['openbao_approle_lockout_threshold']}", cmd)
        self.assertIn(f"-user-lockout-duration={self.variables['openbao_approle_lockout_duration']}s", cmd)
        self.assertIn(
            f"-user-lockout-counter-reset-duration={self.variables['openbao_approle_lockout_counter_reset']}s",
            cmd,
        )

    def _when_is_true(self, mount_tune_current):
        namespace = _resolve_task_vars(
            self.task, {**self.variables, "openbao_approle_mount_tune_current": mount_tune_current}
        )
        conditions = self.task["when"]
        # `when:` entries are bare Jinja expressions (no {{ }}), the same way
        # Ansible itself evaluates a conditional -- wrap each to get a value.
        return all(_render("{{ (" + cond + ") }}", namespace) in ("True", True) for cond in conditions)

    def test_when_is_false_when_live_matches_declared(self):
        mount_tune_current = _mount_tune_read(
            self.variables["openbao_approle_lockout_threshold"],
            self.variables["openbao_approle_lockout_duration"],
            self.variables["openbao_approle_lockout_counter_reset"],
        )
        self.assertFalse(self._when_is_true(mount_tune_current))

    def test_when_is_true_when_live_threshold_drifted(self):
        mount_tune_current = _mount_tune_read(
            5,
            self.variables["openbao_approle_lockout_duration"],
            self.variables["openbao_approle_lockout_counter_reset"],
        )
        self.assertTrue(self._when_is_true(mount_tune_current))


if __name__ == "__main__":
    unittest.main()
