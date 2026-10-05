"""The workstation's per-call issuer path replaces static domain logins."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
FETCH_DOMAIN = ROOT / "roles/openbao_secrets/tasks/fetch_domain.yml"
DOMAINS = ROOT / "roles/openbao_secrets/defaults/main/01-domains.yml"


def _tasks(node):
    if isinstance(node, list):
        for entry in node:
            yield from _tasks(entry)
    elif isinstance(node, dict):
        if "name" in node:
            yield node
        for key in ("block", "rescue", "always"):
            if key in node:
                yield from _tasks(node[key])


def test_workstation_domains_are_declared_at_the_domain_source():
    domains = yaml.safe_load(DOMAINS.read_text())["openbao_secrets_domains"]
    workstation_roles = {
        domain["name"]: domain["workstation_issuer_role"]
        for domain in domains
        if domain.get("workstation_issuer_role")
    }

    assert workstation_roles == {
        "apps": "apps-workstation",
        "media": "media-workstation",
        "monitoring": "monitoring-workstation",
        "local-cloud": "local-cloud-workstation",
        "observability": "observability-workstation",
    }


def test_domain_login_uses_the_parameterized_issuer_command_and_keeps_tokens_secret():
    tasks = list(_tasks(yaml.safe_load(FETCH_DOMAIN.read_text())))
    mint = next(task for task in tasks if task["name"].startswith("Mint a per-call"))
    stored_login = next(
        task for task in tasks if task["name"].startswith("Log in with the stored AppRole")
    )
    kv_read = next(task for task in tasks if task["name"].startswith("Read each KV path"))
    revoke = next(task for task in tasks if task["name"].startswith("Revoke the per-call"))

    assert mint["ansible.builtin.command"]["argv"] == [
        "flow-lock",
        "approle-token",
        "{{ openbao_domain.workstation_issuer_role }}",
    ]
    assert mint["when"] == "openbao_secrets_domain_use_issuer | bool"
    assert mint["no_log"] is True
    assert mint["check_mode"] is False
    assert stored_login["when"] == "not (openbao_secrets_domain_use_issuer | bool)"
    assert kv_read["community.hashi_vault.vault_kv2_get"]["token"] == (
        "{{ openbao_secrets_domain_token }}"
    )
    assert revoke["no_log"] is True
    assert revoke["when"] == [
        "openbao_secrets_domain_use_issuer | bool",
        "openbao_secrets_domain_token is defined",
        "openbao_secrets_domain_token | length > 0",
    ]


def test_issuer_failure_cannot_fall_back_to_a_stored_domain_pair():
    tasks = list(_tasks(yaml.safe_load(FETCH_DOMAIN.read_text())))
    incomplete_pair = next(
        task for task in tasks if task["name"].startswith("Fail on an incomplete workstation issuer pair")
    )

    assert incomplete_pair["ansible.builtin.fail"]["msg"].find(
        "refusing to fall back"
    ) >= 0
    assert incomplete_pair["when"] == [
        "openbao_domain.workstation_issuer_role | default('') | length > 0",
        "openbao_secrets_domain_issuer_inputs_present | bool",
        "not (openbao_secrets_domain_issuer_available | bool)",
    ]
