"""The reconcile, converge and execution-plane policies render their environment and Terrakube reads."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "tests/template_render/verify/openbao_platform_env_reads.yml"


def test_platform_env_and_terrakube_reads_render_exactly_once(tmp_path):
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
