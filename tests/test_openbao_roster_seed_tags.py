"""The roster leaf seed checks its owner under a seed-only tag filter and creates with cas=0."""

import os
import subprocess
from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "tests" / "openbao_roster_seed" / "verify_seed_tags.yml"
SEED_TASKS = ROOT / "roles" / "openbao" / "tasks" / "seed_generated_app_secret.yml"
FOREIGN_METADATA = '{"data": {"custom_metadata": {"managed-by": "example-other-owner"}}}'


def _render_write_body(**variables):
    tasks = yaml.safe_load(SEED_TASKS.read_text(encoding="utf-8"))
    task = next(t for t in tasks if t["name"] == "Write the generated app secret to OpenBao (merge-preserving)")
    templar = Templar(loader=DataLoader())
    templar.available_variables = {"openbao_seed_merged": {"field": "value"}, **variables}
    return templar.template(trust_as_template(task["ansible.builtin.uri"]["body"]))


def test_create_only_write_uses_check_and_set_zero():
    assert _render_write_body(openbao_seed_create_only=True) == {
        "data": {"field": "value"},
        "options": {"cas": 0},
    }
    assert _render_write_body(openbao_seed_create_only=False) == {"data": {"field": "value"}}
    assert _render_write_body() == {"data": {"field": "value"}}


def test_seed_tag_runs_the_owner_check(tmp_path):
    stub = tmp_path / "bao"
    stub.write_text(f"#!/bin/sh\necho '{FOREIGN_METADATA}'\n", encoding="utf-8")
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(
        ["ansible-playbook", "-i", "localhost,", "-c", "local", "--tags", "openbao_kv_seed", str(PLAYBOOK)],
        capture_output=True, text=True, check=False, cwd=ROOT, env=env,
    )
    output = result.stdout[-4000:] + result.stderr[-2000:]
    assert result.returncode == 0, output
    assert "Refuse a roster key leaf that another owner holds" in result.stdout, output
    assert "Assert the owner check refused the foreign leaf" in result.stdout, output
