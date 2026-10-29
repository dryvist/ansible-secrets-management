"""The roster leaf seed checks its owner under a seed-only tag filter and creates with cas=0."""

import os
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "tests" / "openbao_roster_seed" / "verify_seed_tags.yml"
SEED_TASKS = ROOT / "roles" / "openbao" / "tasks" / "seed_generated_app_secret.yml"
OWNER_TASKS = ROOT / "roles" / "openbao" / "tasks" / "seed_roster_agent_leaf_owner.yml"
RECONCILE_POLICY = ROOT / "roles" / "openbao" / "templates" / "openbao-reconcile-policy.hcl.j2"
REQUIREMENTS = ROOT / "requirements.yml"
FOREIGN_METADATA = '{"data": {"custom_metadata": {"managed-by": "example-other-owner"}}}'


def _shared_call():
    tasks = yaml.safe_load(SEED_TASKS.read_text(encoding="utf-8"))
    block = next(
        task for task in tasks
        if task.get("name") == "Seed the generated app secret through the shared contract"
    )
    return block, next(
        task for task in block["block"] if "ansible.builtin.include_role" in task
    )


def test_generated_seed_uses_the_pinned_shared_create_if_absent_contract():
    block, call = _shared_call()
    include = call["ansible.builtin.include_role"]
    requirements = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    contracts = next(
        item for item in requirements["collections"]
        if item["name"] == "https://github.com/dryvist/homelab-contracts.git#/ansible/"
    )

    assert contracts["version"] == "v5.34.0"
    assert include["name"] == "dryvist.homelab.openbao_secrets"
    assert include["tasks_from"] == "seed_generated"
    assert block["delegate_to"] == "{{ openbao_cli_host }}"
    assert block["become"] == "{{ openbao_cli_become }}"
    assert call["vars"]["openbao_secrets_seed_addr"] == "{{ openbao_cli_addr }}"
    assert call["vars"]["openbao_secrets_seed_token"] == "{{ openbao_bootstrap_token }}"
    assert "openbao_seed_create_only" not in call["vars"]


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


def test_owner_marker_is_a_metadata_merge_patch_the_reconcile_policy_grants():
    """Reconcile holds `patch` (not create/update) on metadata/*; a POST would 403."""
    tasks = yaml.safe_load(OWNER_TASKS.read_text(encoding="utf-8"))
    task = next(t for t in tasks if t["name"] == "Mark the absent roster key leaf with its owner")
    uri = task["ansible.builtin.uri"]
    assert "/metadata/apps/" in uri["url"]
    assert uri["method"] == "PATCH"
    assert uri["headers"]["Content-Type"] == "application/merge-patch+json"
    assert list(uri["body"]) == ["custom_metadata"]

    stanza = re.search(
        r'path "\{\{ mount\.path \| default\(mount\) \}\}/metadata/\*" \{(.*?)\n\}',
        RECONCILE_POLICY.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert stanza, "reconcile policy has no metadata/* stanza"
    capabilities = re.search(r"capabilities\s*=\s*\[(.*?)\]", stanza.group(1)).group(1)
    assert "patch" in capabilities
    assert "update" not in capabilities and "create" not in capabilities
