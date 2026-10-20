"""The rotated env document drops credentials that are now minted per call."""

from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
ROTATE_TASKS = ROOT / "playbooks/tasks/openbao_rotate_one_domain.yml"


def test_rotation_replaces_domain_pair_prunes_per_call_pairs_and_keeps_siblings():
    tasks = yaml.safe_load(ROTATE_TASKS.read_text(encoding="utf-8"))
    block = next(task["block"] for task in tasks if "block" in task)
    builder = next(task for task in block if task["name"].startswith("Build the env document"))
    expression = builder["ansible.builtin.set_fact"]["rotate_env_new_data"]
    variables = {
        "rotate_env_current": {
            "json": {
                "data": {
                    "data": {
                        "OPENBAO_APPROLE_APPS_ROLE_ID": "old-role",
                        "OPENBAO_APPROLE_APPS_SECRET_ID": "old-secret",
                        "APPS_VAULT_ROLE_ID": "legacy-role",
                        "APPS_VAULT_SECRET_ID": "legacy-secret",
                        "OPENBAO_APPROLE_FLOW_LOCK_ROLE_ID": "stale-role",
                        "OPENBAO_APPROLE_FLOW_LOCK_SECRET_ID": "stale-secret",
                        "OPENBAO_APPROLE_OPENBAO_RECONCILE_ROLE_ID": "stale-role",
                        "OPENBAO_APPROLE_OPENBAO_RECONCILE_SECRET_ID": "stale-secret",
                        "OPENBAO_APPROLE_LOCAL_LLM_WORKSTATION_ROLE_ID": "host-role",
                        "OPENBAO_APPROLE_LOCAL_LLM_WORKSTATION_SECRET_ID": "host-secret",
                        "SLACK_CHANNEL": "test-channel",
                    }
                }
            }
        },
        "rotate_new_prefix": "OPENBAO_APPROLE_APPS",
        "rotate_legacy_prefix": "APPS_VAULT",
        "rotate_role_id_read": {"json": {"data": {"role_id": "new-role"}}},
        "rotate_new_secret_id": {"json": {"data": {"secret_id": "new-secret"}}},
    }
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables

    rotated = templar.template(trust_as_template(expression))

    assert rotated == {
        "OPENBAO_APPROLE_APPS_ROLE_ID": "new-role",
        "OPENBAO_APPROLE_APPS_SECRET_ID": "new-secret",
        "OPENBAO_APPROLE_LOCAL_LLM_WORKSTATION_ROLE_ID": "host-role",
        "OPENBAO_APPROLE_LOCAL_LLM_WORKSTATION_SECRET_ID": "host-secret",
        "SLACK_CHANNEL": "test-channel",
    }
