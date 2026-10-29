#!/usr/bin/env python3
"""Contract checks for the repository's shared Ansible runner shim."""

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-ansible.sh"
RUNNER_REF = "github:dryvist/homelab-contracts/v5.34.0#run-ansible"
PLAYBOOK = "playbooks/openbao-rotate-approles.yml"
DEFAULT_ENV_NAMES = (
    "RUN_ANSIBLE_NO_SSH",
    "BAO_ADDR",
    "SECRET_STORE_ADDR",
    "ANSIBLE_INVENTORY",
    "RUN_ANSIBLE_CHECKOUT_GUARD",
    "RUN_ANSIBLE_LOG_DIR",
    "RUN_ANSIBLE_RECAP_CHECK",
    "RUN_ANSIBLE_REQUIRE_RECAP",
)


class RunAnsibleShim(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.bin_path = self.temp_path / "bin"
        self.bin_path.mkdir()
        self.argv_log = self.temp_path / "nix-argv.log"
        self.env_log = self.temp_path / "runner-env.log"
        self._write_executable(
            "nix",
            """
            #!/usr/bin/env bash
            set -euo pipefail
            printf '%s\n' "$@" > "$FAKE_NIX_ARGV_LOG"
            printf '%s\n' \
              "$RUN_ANSIBLE_NO_SSH" \
              "$BAO_ADDR" \
              "$ANSIBLE_INVENTORY" \
              "$RUN_ANSIBLE_CHECKOUT_GUARD" \
              "$RUN_ANSIBLE_LOG_DIR" \
              "$RUN_ANSIBLE_RECAP_CHECK" \
              "$RUN_ANSIBLE_REQUIRE_RECAP" > "$FAKE_NIX_ENV_LOG"
            """,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_executable(self, name: str, body: str):
        path = self.bin_path / name
        path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(0o700)

    def _run(self, extra_env=None):
        env = os.environ.copy()
        for name in DEFAULT_ENV_NAMES:
            env.pop(name, None)
        env.update(
            {
                "PATH": f"{self.bin_path}{os.pathsep}{env['PATH']}",
                "FAKE_NIX_ARGV_LOG": str(self.argv_log),
                "FAKE_NIX_ENV_LOG": str(self.env_log),
            }
        )
        env.update(extra_env or {})
        return subprocess.run(
            [str(SCRIPT), PLAYBOOK, "--check"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_runner_pin_and_exact_defaults(self):
        result = self._run()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            self.argv_log.read_text(encoding="utf-8").splitlines(),
            ["run", RUNNER_REF, "--", PLAYBOOK, "--check"],
        )
        self.assertEqual(
            self.env_log.read_text(encoding="utf-8").splitlines(),
            ["1", "", "localhost,", "1", ".ansible-run-logs", "1", "1"],
        )

    def test_defaults_preserve_explicit_overrides_and_address_preference(self):
        result = self._run(
            {
                "RUN_ANSIBLE_NO_SSH": "0",
                "SECRET_STORE_ADDR": "https://secret-store.invalid",
                "BAO_ADDR": "https://fallback.invalid",
                "ANSIBLE_INVENTORY": "inventory.yml",
                "RUN_ANSIBLE_CHECKOUT_GUARD": "0",
                "RUN_ANSIBLE_LOG_DIR": "custom-run-logs",
                "RUN_ANSIBLE_RECAP_CHECK": "0",
                "RUN_ANSIBLE_REQUIRE_RECAP": "0",
            }
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            self.env_log.read_text(encoding="utf-8").splitlines(),
            [
                "0",
                "https://secret-store.invalid",
                "inventory.yml",
                "0",
                "custom-run-logs",
                "0",
                "0",
            ],
        )


if __name__ == "__main__":
    unittest.main()
