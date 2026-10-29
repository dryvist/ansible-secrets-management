"""Authelia's publisher uses the shared role with the repository's prior defaults."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
AUTHELIA_MAIN = ROOT / "roles/authelia/tasks/main.yml"
REQUIREMENTS = ROOT / "requirements.yml"


def test_publish_uses_the_pinned_shared_role_with_the_same_inputs():
    tasks = yaml.safe_load(AUTHELIA_MAIN.read_text(encoding="utf-8"))
    publish = next(
        task for task in tasks if task.get("name") == "Publish the generated Authelia secrets to OpenBao"
    )
    requirements = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    contracts = next(
        item
        for item in requirements["collections"]
        if item["name"] == "https://github.com/dryvist/homelab-contracts.git#/ansible/"
    )

    assert publish["ansible.builtin.include_role"] == {
        "name": "dryvist.homelab.openbao_secrets",
        "tasks_from": "publish.yml",
    }
    # Jinja ignores whitespace, so a folded (>-) and a single-line spelling of one expression are the same input.
    inputs = {name: " ".join(str(value).split()) for name, value in publish["vars"].items()}
    assert inputs == {
        "openbao_secrets_bao_addr": "{{ lookup('env', 'BAO_ADDR') | default('', true) }}",
        "openbao_secrets_kv_mount": "secret",
        "openbao_secrets_publish_app": "authelia",
        "openbao_secrets_publish_reason": "(service secrets; storage key is unrecoverable if lost)",
        "openbao_secrets_publish_data": "{{ authelia_publish_data | default({}, true) }}",
        "openbao_secrets_publish_role_id": (
            "{{ lookup('env', 'CONVERGE_ROLE_ID') | "
            "default(lookup('env', 'OPENBAO_APPROLE_ANSIBLE_ROLE_ID'), true) }}"
        ),
        "openbao_secrets_publish_secret_id": (
            "{{ lookup('env', 'CONVERGE_SECRET_ID') | "
            "default(lookup('env', 'OPENBAO_APPROLE_ANSIBLE_SECRET_ID'), true) }}"
        ),
    }
    assert contracts["version"] == "v5.34.0"
