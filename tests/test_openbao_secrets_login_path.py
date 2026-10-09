#!/usr/bin/env python3
"""Run tests/openbao_secrets/verify_login_path.yml against the production decision.

An issuer domain takes the workstation issuer exchange only when the
approle-issuer pair is complete AND flow-lock resolves on the controller.
With the pair present but no flow-lock (the execution plane), it logs in with
its stored pair and says so.
"""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK = ROOT / "tests" / "openbao_secrets" / "verify_login_path.yml"


def _path_without_flow_lock():
    """PATH reduced to the dirs ansible and a POSIX shell need, minus flow-lock."""
    dirs = []
    for tool in ("ansible-playbook", "sh"):
        found = shutil.which(tool)
        if found:
            dirs.append(os.path.dirname(found))
    dirs += ["/usr/bin", "/bin"]
    kept = [d for d in dict.fromkeys(dirs) if not os.path.exists(os.path.join(d, "flow-lock"))]
    return os.pathsep.join(kept)


class OpenbaoSecretsLoginPath(unittest.TestCase):
    def _run(self, path, issuer_available, expect_use_issuer):
        env = dict(os.environ, PATH=path)
        return subprocess.run(
            [
                "ansible-playbook", "-i", "localhost,", "-c", "local", str(PLAYBOOK),
                "-e", f"issuer_available={issuer_available}",
                "-e", f"expect_use_issuer={expect_use_issuer}",
            ],
            capture_output=True, text=True, check=False, cwd=ROOT, env=env,
        )

    def test_issuer_pair_without_flow_lock_uses_the_stored_pair(self):
        path = _path_without_flow_lock()
        self.assertIsNone(shutil.which("flow-lock", path=path))
        result = self._run(path, "true", "false")
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn(
            "stored AppRole pair (approle-issuer pair present, flow-lock not found on the controller)",
            result.stdout,
        )

    def test_issuer_pair_with_flow_lock_uses_the_issuer(self):
        with tempfile.TemporaryDirectory() as stub_dir:
            stub = Path(stub_dir) / "flow-lock"
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
            result = self._run(stub_dir + os.pathsep + _path_without_flow_lock(), "true", "true")
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn("workstation issuer exchange (harness-workstation)", result.stdout)

    def test_no_issuer_pair_uses_the_stored_pair(self):
        result = self._run(_path_without_flow_lock(), "false", "false")
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn("harness: stored AppRole pair", result.stdout)


if __name__ == "__main__":
    unittest.main()
