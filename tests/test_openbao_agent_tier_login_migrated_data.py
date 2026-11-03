"""The migrated agent-tier login data is set by its own task after the prepare task."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "tests/template_render/verify/openbao_agent_tier_login_migrated_data.yml"


def test_agent_tier_login_migrated_data(tmp_path):
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
