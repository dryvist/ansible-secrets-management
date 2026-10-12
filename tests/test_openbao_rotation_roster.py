"""Fail-closed behavior for inventory resolution in AppRole rotation."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RotationRosterGuard(unittest.TestCase):
    def test_rotation_roster_guard_fixture_cases(self):
        env = os.environ.copy()
        env.pop("BAO_ADDR", None)
        env.pop("BAO_TOKEN", None)
        env.pop("TOFU_INVENTORY_PATH", None)

        for case in (
            "no_readers",
            "empty_roster",
            "one_agent",
            "forbidden_reader",
            "unresolvable_inventory",
        ):
            with self.subTest(case=case):
                result = subprocess.run(
                    [
                        "ansible-playbook",
                        "-i",
                        "localhost,",
                        "-c",
                        "local",
                        "-e",
                        f"rotation_roster_guard_case={case}",
                        "tests/template_render/verify/openbao_rotation_roster_guard.yml",
                    ],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    check=False,
                    text=True,
                )

                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, f"case {case}:\n{output}")

    def test_rotate_approles_check_mode_ends_before_credentials(self):
        auth_env = {
            "human": {
                "ROTATE_WRAPPING_TOKEN": "example-wrapping-token",
                "OPENBAO_APPROLE_APPROLE_SECRET_ID_ROTATE_ROLE_ID": "example-role-id",
            },
            "scheduled": {
                "OPENBAO_APPROLE_APPROLE_SECRET_ID_ROTATE_SCHEDULED_ROLE_ID": "example-role-id",
                "OPENBAO_APPROLE_APPROLE_SECRET_ID_ROTATE_SCHEDULED_SECRET_ID": "example-secret-id",
            },
            "preissued": {"OPENBAO_ROTATE_TOKEN": "example-token"},
        }
        auth_keys = {
            "ROTATE_WRAPPING_TOKEN",
            "OPENBAO_APPROLE_APPROLE_SECRET_ID_ROTATE_ROLE_ID",
            "OPENBAO_APPROLE_APPROLE_SECRET_ID_ROTATE_SCHEDULED_ROLE_ID",
            "OPENBAO_APPROLE_APPROLE_SECRET_ID_ROTATE_SCHEDULED_SECRET_ID",
            "OPENBAO_ROTATE_TOKEN",
        }

        for mode, credentials in auth_env.items():
            with self.subTest(mode=mode):
                env = os.environ.copy()
                for key in auth_keys | {"BAO_ADDR"}:
                    env.pop(key, None)
                env.update(credentials)
                env["BAO_ADDR"] = "https://example.com"
                result = subprocess.run(
                    [
                        "ansible-playbook",
                        "--check",
                        "-i",
                        "localhost,",
                        "-c",
                        "local",
                        "-e",
                        "bootstrap_seed_only=true",
                        "playbooks/openbao-rotate-approles.yml",
                    ],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    check=False,
                    text=True,
                )

                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, f"mode {mode}:\n{output}")
                self.assertIn(
                    "AppRole rotation has no dry run because it consumes single-use credentials.",
                    output,
                )

    def test_rotate_policy_render_omits_object_storage_access(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as render_tmp:
            result = subprocess.run(
                [
                    "ansible-playbook",
                    "-i",
                    "localhost,",
                    "-c",
                    "local",
                    "-e",
                    f"render_tmp={render_tmp}",
                    "tests/template_render/verify/openbao_approle_secret_id_rotate_policy.yml",
                ],
                cwd=ROOT,
                capture_output=True,
                check=False,
                text=True,
            )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)


if __name__ == "__main__":
    unittest.main()
