"""Authelia's service-secret reconcile holds its cases on real guest files, with the shared seed stubbed."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tests" / "authelia_service_secrets" / "verify.yml"


def test_reconcile_cases_hold_on_real_guest_files():
    result = subprocess.run(
        ["ansible-playbook", "-i", "localhost,", "-c", "local", str(VERIFY)],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
