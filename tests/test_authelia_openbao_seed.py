"""Authelia's service secrets are seeded through the shared generate-if-absent contract, from the controller."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
AUTHELIA = ROOT / "roles" / "authelia"
SERVICE_SECRETS = AUTHELIA / "tasks" / "service_secrets.yml"
DEFAULTS = AUTHELIA / "defaults" / "main" / "00-core.yml"
REQUIREMENTS = ROOT / "requirements.yml"


def _seed_task():
    tasks = yaml.safe_load(SERVICE_SECRETS.read_text(encoding="utf-8"))
    return next(
        task for task in tasks if task.get("name") == "Seed the Authelia service secrets in OpenBao through the shared contract"
    )


def test_seed_runs_the_shared_contract_on_the_controller_with_the_converge_token():
    seed = _seed_task()
    assert seed["delegate_to"] == "localhost"
    assert seed["no_log"] is True
    [call] = seed["block"]
    assert call["ansible.builtin.include_role"] == {
        "name": "dryvist.homelab.openbao_secrets",
        "tasks_from": "seed_generated",
    }
    inputs = call["vars"]
    assert inputs["openbao_secrets_seed_mount"] == "secret"
    assert inputs["openbao_secrets_seed_path"] == "apps/authelia"
    assert inputs["openbao_secrets_seed_token"] == "{{ lookup('env', 'BAO_TOKEN') | default('', true) }}"
    assert inputs["openbao_secrets_seed_addr"] == "{{ lookup('env', 'BAO_ADDR') | default('', true) }}"
    assert inputs["openbao_secrets_seed_check_capabilities"] is True
    assert inputs["openbao_secrets_seed_register"] == "authelia_seed_result"
    # Fail closed: no local fallback values, and the token is never revoked (the converge run still uses it).
    assert "openbao_secrets_seed_local_values" not in inputs
    assert "openbao_secrets_seed_revoke_token" not in inputs


def test_field_names_are_the_ones_the_previous_publish_wrote():
    defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
    names = sorted(defaults["authelia_secret_files"]) + ["bootstrap_password", "oidc_jwks_private_key"]
    assert sorted(names) == [
        "bootstrap_password",
        "jwt_secret",
        "oidc_hmac_secret",
        "oidc_jwks_private_key",
        "session_secret",
        "storage_key",
    ]


def test_nothing_in_the_authelia_role_publishes_or_generates_with_the_old_path():
    for path in AUTHELIA.rglob("*.yml"):
        text = path.read_text(encoding="utf-8")
        assert "publish.yml" not in text, path
        assert "openbao_secrets_publish" not in text, path
        assert "random_string" not in text, path


def test_bootstrap_password_keeps_its_length_alphabet_and_root_only_file_format():
    read = (AUTHELIA / "tasks" / "service_secrets_read.yml").read_text(encoding="utf-8")
    reconcile = (AUTHELIA / "tasks" / "service_secrets_reconcile.yml").read_text(encoding="utf-8")
    persist = (AUTHELIA / "tasks" / "bootstrap_password_persist.yml").read_text(encoding="utf-8")
    main = (AUTHELIA / "tasks" / "main.yml").read_text(encoding="utf-8")
    assert "'length': (24 if item.key == 'bootstrap_password' else 64)" in read
    assert "'charset': 'alnum'" in read
    assert 'content: "{{ authelia_admin_user }}:{{ authelia_seed_result.bootstrap_password }}\\n"' in persist
    assert "when: not authelia_users_stat.stat.exists" in persist
    assert "authelia_bootstrap_password_file_owner | default('root')" in persist
    assert "authelia_bootstrap_password_file_group | default('root')" in persist
    assert 'mode: "0600"' in persist
    assert "include_tasks: bootstrap_password_persist.yml" in main
    assert "authelia_bootstrap_password_file" not in reconcile


def test_contracts_pin_is_the_latest_tag():
    requirements = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    contracts = next(
        item
        for item in requirements["collections"]
        if item["name"] == "https://github.com/dryvist/homelab-contracts.git#/ansible/"
    )
    assert contracts["version"] == "v5.36.0"
