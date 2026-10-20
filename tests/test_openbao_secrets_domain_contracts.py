"""Run focused OpenBao secret-domain contract playbooks without live access."""

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(playbook, *, env=None):
    return subprocess.run(
        ["ansible-playbook", "-i", "localhost,", "-c", "local", str(playbook)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        env=env,
    )


class OpenbaoSecretsDomainContracts(unittest.TestCase):
    def test_optional_missing_path_is_skipped_and_resolves_empty(self):
        playbook = ROOT / "tests" / "openbao_secrets" / "verify_read_gate.yml"
        result = _run(playbook)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn("optional path returning 404 is skipped", result.stdout)
        self.assertIn("consumer of a field from this path will resolve empty", result.stdout)

    def test_denied_read_in_all_optional_domain_returns_empty_and_continues(self):
        playbook = ROOT / "tests" / "openbao_secrets" / "verify_optional_domain_failure.yml"
        result = _run(playbook)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])

    def test_explicit_and_default_credential_domains_resolve(self):
        env = dict(
            os.environ,
            OPENBAO_APPROLE_APPS_ROLE_ID="fixture-role-id",
            OPENBAO_APPROLE_APPS_SECRET_ID="fixture-secret-id",
            OPENBAO_APPROLE_HARNESS_ROLE_ID="harness-role-id",
            OPENBAO_APPROLE_HARNESS_SECRET_ID="harness-secret-id",
            OPENBAO_APPROLE_POSTGRES_BACKUP_S3_ROLE_ID="",
            OPENBAO_APPROLE_POSTGRES_BACKUP_S3_SECRET_ID="",
            POSTGRES_BACKUP_S3_VAULT_ROLE_ID="",
            POSTGRES_BACKUP_S3_VAULT_SECRET_ID="",
        )
        playbook = ROOT / "tests" / "openbao_secrets" / "verify_credential_domain.yml"
        result = _run(playbook, env=env)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
