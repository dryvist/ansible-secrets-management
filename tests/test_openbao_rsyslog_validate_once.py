# Copyright (c) 2026 JacobPEvans
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""rsyslog is validated once, after every drop-in writer has run.

audit.yml and secret_age.yml each write a rsyslog.d drop-in that can load
imfile. A `rsyslogd -N1` placed inside audit.yml validated the assembled
config before secret_age.yml had rewritten its drop-in, so a drop-in from
before the imfile guard failed validation first, the play was isolated, and
the task that would have repaired it never ran on any later converge either.
"""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles/openbao/tasks"
VALIDATE = "Validate the full rsyslog configuration"


def _names(path):
    return [t.get("name", "") for t in yaml.safe_load(path.read_text(encoding="utf-8"))]


MAIN = TASKS / "main/configure_and_bootstrap.yml"
SECRET_AGE_RSYSLOG = "Ship the secret-age report over rsyslog"


def _task(path, name):
    for task in yaml.safe_load(path.read_text(encoding="utf-8")):
        if task.get("name") == name:
            return task
    raise AssertionError(f"{path.name} no longer has task {name!r}")


class RsyslogValidatedOnceAfterAllWriters(unittest.TestCase):
    def test_no_drop_in_writer_validates_the_whole_config_itself(self):
        for fragment in ("audit.yml", "secret_age.yml", "secret_age_rsyslog.yml"):
            self.assertFalse(
                [n for n in _names(TASKS / fragment) if n.startswith(VALIDATE)],
                f"{fragment} validates rsyslog before the other writer has run",
            )

    def test_validation_follows_the_last_drop_in_include(self):
        names = _names(MAIN)
        for writer in (
            "Enable the audit device and ship the audit log",
            SECRET_AGE_RSYSLOG,
        ):
            self.assertGreater(names.index(VALIDATE), names.index(writer))
        self.assertEqual(names.count(VALIDATE), 1)

    def test_the_secret_age_drop_in_is_not_behind_the_creds_gate(self):
        """The drop-in is the repair; a converge without the AppRole creds
        (the execution plane) must still be able to re-render it."""
        when = _task(MAIN, SECRET_AGE_RSYSLOG)["when"]
        self.assertNotIn("role_id", str(when))
        self.assertNotIn("secret_id", str(when))
        self.assertIn(
            "Deploy the secret-age-report rsyslog shipping ruleset",
            _names(TASKS / "secret_age_rsyslog.yml"),
        )


if __name__ == "__main__":
    unittest.main()
