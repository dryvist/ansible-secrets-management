"""The pr-reconcile secret_id bind must be one guest, or absent entirely.

Renders the REAL assert expression out of init/10-approles.yml, never a
reimplementation: a single /32 passes; any wider range, a list, or a bare
address fails the converge before the role is written. The default reads the
platform environment document and stays empty until the guest's address is
supplied -- an empty bind also keeps pr-reconcile out of the rotated set.
"""

from pathlib import Path
import unittest

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "10-approles.yml"
TASK = "Assert the pr-reconcile bind, when supplied, is one address as a /32"
DEFAULTS = ROOT / "roles" / "openbao" / "defaults" / "main" / "05c-terrakube-and-remaining-domain-names.yml"


def _condition():
    for t in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if t.get("name") == TASK:
            (that,) = t["ansible.builtin.assert"]["that"]
            return that
    raise AssertionError(f"task {TASK!r} not found in {TASKS}")


def passes(cidr):
    templar = Templar(loader=DataLoader())
    templar.available_variables = {"openbao_pr_reconcile_secret_id_cidr": cidr}
    return templar.template(trust_as_template("{{ " + _condition() + " }}"))


class PrReconcileBindIsOneHost(unittest.TestCase):
    def test_single_host_passes(self):
        self.assertTrue(passes("192.0.2.30/32"))

    def test_wider_or_malformed_binds_fail(self):
        for bad in ("192.0.2.0/24", "192.0.2.30", "192.0.2.30/32,198.51.100.7/32",
                    "0.0.0.0/0", " 192.0.2.30/32"):
            with self.subTest(bad=bad):
                self.assertFalse(passes(bad))


def bind(platform_env):
    raw = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))["openbao_pr_reconcile_secret_id_cidr"]
    templar = Templar(loader=DataLoader())
    templar.available_variables = {"openbao_platform_env": platform_env}
    return templar.template(trust_as_template(raw)).strip()


class PrReconcileBindComesFromPlatformEnv(unittest.TestCase):
    def test_bind_reads_the_platform_environment_document(self):
        self.assertEqual(
            bind({"OPENBAO_PR_RECONCILE_SECRET_ID_CIDR": "192.0.2.30/32"}), "192.0.2.30/32"
        )

    def test_missing_key_falls_back_to_empty(self):
        self.assertEqual(bind({}), "")


if __name__ == "__main__":
    unittest.main()
