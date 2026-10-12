"""Fail-closed behavior for inventory resolution in AppRole rotation."""

import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RotationInventoryResolution(unittest.TestCase):
    def test_rotation_play_fails_when_explicit_inventory_path_is_missing(self):
        missing_inventory = ROOT / "tests" / "openbao_rotate" / "missing-roster-inventory.json"
        self.assertFalse(missing_inventory.exists())

        env = os.environ.copy()
        env["TOFU_INVENTORY_PATH"] = str(missing_inventory)
        env.pop("BAO_ADDR", None)
        env.pop("BAO_TOKEN", None)

        result = subprocess.run(
            [
                "ansible-playbook",
                "-i",
                "localhost,",
                "playbooks/openbao-rotate-approles.yml",
                "--start-at-task",
                "Load the agent roster",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            check=False,
            text=True,
        )

        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("OpenTofu inventory could not be resolved", output)
        self.assertIn("Load the agent roster", output)


if __name__ == "__main__":
    unittest.main()
