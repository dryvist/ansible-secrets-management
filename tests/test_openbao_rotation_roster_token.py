"""Which token the rotation roster guard hands to inventory_resolve.

Scheduled mode must read the published inventory with the execution plane's
token (BAO_TOKEN), never the rotator's own login: the rotator identity has no
read on platform/object-storage, so using it made every scheduled run fail.

These render the REAL token expression out of the guard task file.
"""

from pathlib import Path
import os
import unittest
from unittest import mock

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "playbooks" / "tasks" / "rotate-roster-guard.yml"
LOAD = "Load the agent roster when a roster-owned key reader is live"

ROTATOR_TOKEN = "rotator-login-token"
PLANE_TOKEN = "plane-ambient-token"


def _token_expression():
    for task in yaml.safe_load(GUARD.read_text(encoding="utf-8")):
        if task.get("name") == LOAD:
            return task["vars"]["inventory_resolve_openbao_token"]
    raise AssertionError(f"task {LOAD!r} not found in {GUARD}")


def _resolved_token(scheduled):
    variables = {
        "rotate_scheduled_mode": scheduled,
        "rotate_login": {"json": {"auth": {"client_token": ROTATOR_TOKEN}}},
    }
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    return templar.template(trust_as_template(_token_expression()))


class RosterGuardToken(unittest.TestCase):
    def test_scheduled_mode_uses_the_plane_token_not_the_rotator_login(self):
        with mock.patch.dict(os.environ, {"BAO_TOKEN": PLANE_TOKEN}):
            self.assertEqual(_resolved_token(True), PLANE_TOKEN)

    def test_scheduled_mode_never_reads_the_rotator_token(self):
        with mock.patch.dict(os.environ, {"BAO_TOKEN": PLANE_TOKEN}):
            self.assertNotEqual(_resolved_token(True), ROTATOR_TOKEN)

    def test_scheduled_mode_without_a_plane_token_is_empty_not_the_rotator_token(self):
        with mock.patch.dict(os.environ, {"BAO_TOKEN": ""}):
            self.assertEqual(_resolved_token(True), "")

    def test_human_mode_keeps_the_rotator_login_token(self):
        with mock.patch.dict(os.environ, {"BAO_TOKEN": PLANE_TOKEN}):
            self.assertEqual(_resolved_token(False), ROTATOR_TOKEN)


if __name__ == "__main__":
    unittest.main()
