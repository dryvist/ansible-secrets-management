"""Render the Authelia configuration and assert its role contracts."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYBOOKS = {
    "elevation": ROOT / "tests/template_render/verify/authelia_elevation.yml",
    "access_control": ROOT / "tests/template_render/verify/authelia_access_control.yml",
}


def _run_playbook(playbook, render_tmp):
    result = subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            "-c",
            "local",
            "-e",
            f"render_tmp={render_tmp}",
            str(playbook),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    return result


def test_authelia_elevation_clients_render(tmp_path):
    result = _run_playbook(PLAYBOOKS["elevation"], tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_authelia_access_control_rules_render(tmp_path):
    result = _run_playbook(PLAYBOOKS["access_control"], tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
