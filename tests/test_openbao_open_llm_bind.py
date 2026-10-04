"""The open-llm secret_id bind must be one host.

Renders the REAL assert expression out of init/10-approles.yml, never a
reimplementation: a single /32 passes; any wider range, a list, or a bare
address fails the converge before the role is written.
"""

from pathlib import Path
import unittest

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "10-approles.yml"
TASK = "Assert the open-llm bind, when supplied, is one address as a /32"


def _condition():
    for t in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if t.get("name") == TASK:
            (that,) = t["ansible.builtin.assert"]["that"]
            return that
    raise AssertionError(f"task {TASK!r} not found in {TASKS}")


def passes(cidr):
    templar = Templar(loader=DataLoader())
    templar.available_variables = {"openbao_open_llm_secret_id_cidr": cidr}
    return templar.template(trust_as_template("{{ " + _condition() + " }}"))


class OpenLlmBindIsOneHost(unittest.TestCase):
    def test_single_host_passes(self):
        self.assertTrue(passes("192.0.2.10/32"))

    def test_wider_or_malformed_binds_fail(self):
        for bad in ("192.0.2.0/24", "192.0.2.10", "192.0.2.10/32,198.51.100.7/32",
                    "0.0.0.0/0", " 192.0.2.10/32"):
            with self.subTest(bad=bad):
                self.assertFalse(passes(bad))


if __name__ == "__main__":
    unittest.main()
