"""Run the roster-owned MCP fetch-path fixture against the production task."""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK = ROOT / "tests" / "openbao_secrets" / "verify_roster_fetch_paths.yml"


class OpenbaoSecretsRosterFetchPaths(unittest.TestCase):
    def test_roster_owned_mcp_paths_are_removed(self):
        result = subprocess.run(
            ["ansible-playbook", "-i", "localhost,", "-c", "local", str(PLAYBOOK)],
            capture_output=True, text=True, check=False, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn("Assert an empty roster preserves every declared fetch domain", result.stdout)
        self.assertIn("Assert no fetch domain contains the owned Splunk MCP path", result.stdout)
        self.assertIn("Assert the owner domain keeps its Splunk MCP path", result.stdout)


if __name__ == "__main__":
    unittest.main()
