# Copyright (c) 2026 JacobPEvans
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
"""init/09b must find the existing TOTP method by the field OpenBao returns.

`bao read identity/mfa/method/totp/<id>` reports the method's name as
`data.name` (verified live). Filtering on any other key never matches, so the
role "creates" the method again on every provisioning run — an update on the
same name, which returns no id — and the enforcement assert fails with an
empty id while the human login stays single-factor.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
INIT_09B = ROOT / "roles/openbao/tasks/init/09b-human-unlock.yml"

# The shape of one `bao read -format=json identity/mfa/method/totp/<id>`.
LIVE_READ = '{"data": {"id": "654a17d5-0000-4000-8000-000000000000", "name": "human-unlock-totp", "issuer": "OpenBao", "type": "totp"}}'


def _task(name):
    for task in yaml.safe_load(INIT_09B.read_text(encoding="utf-8")):
        if task.get("name") == name:
            return task
    raise AssertionError(f"init/09b no longer has task {name!r}")


def _render(expr, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    return templar.template(trust_as_template(expr))


class TotpMethodResolution(unittest.TestCase):
    def test_an_existing_method_is_found_by_the_name_the_api_returns(self):
        expr = _task("Resolve the TOTP method id for this method_name")[
            "ansible.builtin.set_fact"
        ]["openbao_mfa_totp_method_id"]
        resolved = _render(
            expr,
            {
                "openbao_mfa_totp_reads": {"results": [{"stdout": LIVE_READ, "rc": 0}]},
                "openbao_human_unlock_mfa_method_name": "human-unlock-totp",
            },
        )
        self.assertEqual(resolved, "654a17d5-0000-4000-8000-000000000000")

    def test_a_different_name_does_not_match(self):
        expr = _task("Resolve the TOTP method id for this method_name")[
            "ansible.builtin.set_fact"
        ]["openbao_mfa_totp_method_id"]
        resolved = _render(
            expr,
            {
                "openbao_mfa_totp_reads": {"results": [{"stdout": LIVE_READ, "rc": 0}]},
                "openbao_human_unlock_mfa_method_name": "something-else",
            },
        )
        self.assertEqual(resolved, "")

    def test_a_freshly_created_id_is_used_when_the_create_ran(self):
        """A registered result has no `skipped` key when the task ran; the
        guard's default must therefore be false, or the new id is discarded."""
        when = _task("Use the newly created TOTP method id")["when"]
        guard = next(w for w in when if "skipped" in w)
        self.assertTrue(
            _render("{{ " + guard + " }}", {"openbao_mfa_totp_created": {"rc": 0, "stdout": "{}"}})
        )
        self.assertFalse(
            _render("{{ " + guard + " }}", {"openbao_mfa_totp_created": {"skipped": True}})
        )


if __name__ == "__main__":
    unittest.main()
