#!/usr/bin/env python3
"""Run tests/openbao_secrets/verify_login_gate.yml against the production gate.

An all-optional domain's failed AppRole login is isolated (warned, recorded,
paged); a domain with a required path still fails the run.
"""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK = ROOT / "tests" / "openbao_secrets" / "verify_login_gate.yml"


class OpenbaoSecretsLoginGate(unittest.TestCase):
    def test_login_gate_verdicts(self):
        result = subprocess.run(
            ["ansible-playbook", "-i", "localhost,", "-c", "local", str(PLAYBOOK)],
            capture_output=True, text=True, check=False, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        for name in (
            "successful login passes",
            "failed login in an all-optional domain is isolated",
            "failed login in a domain with a required path fails",
            "login without a client token is not a success",
        ):
            self.assertIn(f"Assert the gate reached the expected verdict | {name}", result.stdout)


if __name__ == "__main__":
    unittest.main()
