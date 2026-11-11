"""pr-reconcile binds to one /32 and fails closed while that /32 is empty.

The /32 shape assert renders the REAL expression out of init/10-approles.yml.
The env read renders the REAL expression out of 05c. The rotated-set, CLI-bind
and fallback checks run the verify playbook against the real defaults.
"""

from pathlib import Path
import subprocess
import unittest

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "10-approles.yml"
DEFAULTS = ROOT / "roles" / "openbao" / "defaults" / "main" / "05c-terrakube-and-remaining-domain-names.yml"
PLAYBOOK = ROOT / "tests" / "template_render" / "verify" / "openbao_pr_reconcile_bind.yml"
TASK = "Assert the pr-reconcile bind, when supplied, is one address as a /32"


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


def pr_reconcile_bind(platform_env):
    raw = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))["openbao_pr_reconcile_secret_id_cidr"]
    templar = Templar(loader=DataLoader())
    templar.available_variables = {"openbao_platform_env": platform_env}
    return templar.template(trust_as_template(raw)).strip()


class PrReconcileBindIsOneHost(unittest.TestCase):
    def test_documentation_host_passes(self):
        self.assertTrue(passes("192.0.2.30/32"))

    def test_wider_or_malformed_binds_fail(self):
        for bad in ("192.0.2.0/24", "192.0.2.30", "192.0.2.30/32,192.0.2.31/32",
                    "0.0.0.0/0", " 192.0.2.30/32"):
            with self.subTest(bad=bad):
                self.assertFalse(passes(bad))


class PrReconcileBindComesFromPlatformEnv(unittest.TestCase):
    def test_bind_reads_the_platform_environment_document(self):
        self.assertEqual(
            pr_reconcile_bind({"OPENBAO_PR_RECONCILE_SECRET_ID_CIDR": "192.0.2.30/32"}),
            "192.0.2.30/32",
        )

    def test_missing_key_falls_back_to_empty(self):
        self.assertEqual(pr_reconcile_bind({}), "")


class PrReconcileFailsClosedAndBinds(unittest.TestCase):
    def test_empty_is_unbound_and_unrotated_and_supplied_binds_both_fields(self):
        result = subprocess.run(
            [
                "ansible-playbook",
                "-i",
                "localhost,",
                "-c",
                "local",
                str(PLAYBOOK),
            ],
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
