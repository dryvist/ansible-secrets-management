#!/usr/bin/env python3
"""scripts/run-ansible.sh is the entry point the execution plane calls. It
must pass a localhost inventory, and its verdict must come from the play
recap, not only the exit code. A stub ansible-playbook stands in for the real
one so no play runs.
"""

import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "run-ansible.sh"

STUB = """#!/usr/bin/env bash
echo "ARGS: $*"
printf '%s\\n' "$STUB_OUTPUT"
exit "${STUB_EXIT:-0}"
"""


class RunAnsibleWrapper(unittest.TestCase):
    def run_wrapper(self, output, exit_code=0):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = pathlib.Path(tmp, "bin")
            bindir.mkdir()
            stub = bindir / "ansible-playbook"
            stub.write_text(STUB, encoding="utf-8")
            stub.chmod(0o755)
            work = pathlib.Path(tmp, "repo")
            work.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=work, check=True)
            env = dict(
                os.environ,
                PATH=f"{bindir}:{os.environ['PATH']}",
                ALLOW_STALE_CHECKOUT="1",
                STUB_OUTPUT=output,
                STUB_EXIT=str(exit_code),
            )
            return subprocess.run(
                ["bash", str(SCRIPT), "playbooks/openbao-rotate-approles.yml", "--diff"],
                cwd=work, env=env, capture_output=True, text=True, check=False,
            )

    def test_passes_localhost_inventory(self):
        r = self.run_wrapper("PLAY RECAP\nlocalhost : ok=3 changed=1 failed=0 unreachable=0")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ARGS: -i localhost, playbooks/openbao-rotate-approles.yml --diff", r.stdout)

    def test_recap_failure_fails_a_zero_exit(self):
        r = self.run_wrapper("PLAY RECAP\nlocalhost : ok=3 changed=0 failed=1 unreachable=0")
        self.assertEqual(r.returncode, 1)

    def test_missing_recap_fails(self):
        r = self.run_wrapper("interrupted")
        self.assertEqual(r.returncode, 1)

    def test_nonzero_exit_kept(self):
        r = self.run_wrapper("PLAY RECAP\nlocalhost : ok=1 failed=0 unreachable=0", exit_code=2)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
