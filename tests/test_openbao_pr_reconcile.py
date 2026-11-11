"""The pr-reconcile identity mints only its two installation-wide write sets."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "tests/template_render/verify/openbao_pr_reconcile.yml"


def test_pr_reconcile_identity(tmp_path):
    result = subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            "-c",
            "local",
            "-e",
            f"render_tmp={tmp_path}",
            str(PLAYBOOK),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
