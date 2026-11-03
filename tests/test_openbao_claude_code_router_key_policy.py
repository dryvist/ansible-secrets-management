"""The claude-code-router-key policy grants read on exactly the Claude Code leaf."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "tests/template_render/verify/openbao_claude_code_router_key_policy.yml"


def test_claude_code_router_key_policy(tmp_path):
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
