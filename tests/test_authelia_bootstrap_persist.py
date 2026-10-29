"""The bootstrap password copy is written only on the first-run path and is never recreated after the passkey cleanup."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tests" / "authelia_bootstrap_persist" / "verify.yml"


def test_bootstrap_copy_is_written_on_the_first_run_and_never_recreated_after_enrolment():
    result = subprocess.run(
        ["ansible-playbook", "-i", "localhost,", "-c", "local", str(VERIFY)],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
