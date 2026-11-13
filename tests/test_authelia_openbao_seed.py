"""Authelia's service secrets use the dedicated signing writer and shared seed contract."""

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
        task
        for task in tasks
        if task.get("name")
        == "Seed the Authelia service secrets in OpenBao through the shared contract"
    )


def test_seed_logs_in_as_the_signing_writer_and_uses_the_shared_contract():
    seed = _seed_task()
    assert seed["delegate_to"] == "localhost"
    assert seed["no_log"] is True
    login = next(task for task in seed["block"] if "ansible.builtin.uri" in task)
    assert login["ansible.builtin.uri"] == {
        "url": (
            "{{ lookup('env', 'BAO_ADDR') | default('', true)\n"
            "   | regex_replace('/+$', '') }}/v1/auth/approle/login"
        ),
        "method": "POST",
        "body_format": "json",
        "body": {
            "role_id": (
                "{{ lookup('env', 'OPENBAO_APPROLE_AUTHELIA_SIGNING_WRITER_ROLE_ID')\n"
                "   | default('', true) }}"
            ),
            "secret_id": (
                "{{ lookup('env', 'OPENBAO_APPROLE_AUTHELIA_SIGNING_WRITER_SECRET_ID')\n"
                "   | default('', true) }}"
            ),
        },
        "status_code": 200,
        "follow_redirects": "none",
        "use_proxy": False,
        "timeout": 10,
    }
    assert login["register"] == "authelia_signing_writer_login"
    assert login["no_log"] is True
    call = next(task for task in seed["block"] if "ansible.builtin.include_role" in task)
    assert call["ansible.builtin.include_role"] == {
        "name": "dryvist.homelab.openbao_secrets",
        "tasks_from": "seed_generated",
    }
    inputs = call["vars"]
    assert inputs["openbao_secrets_seed_mount"] == "secret"
    assert inputs["openbao_secrets_seed_path"] == "{{ authelia_service_secrets_kv_path }}"
    assert inputs["openbao_secrets_seed_token"] == "{{ authelia_signing_writer_login.json.auth.client_token }}"
    assert inputs["openbao_secrets_seed_expected_writer_policy"] == "authelia-signing-writer"
    assert inputs["openbao_secrets_seed_addr"] == "{{ lookup('env', 'BAO_ADDR') | default('', true) }}"
    assert inputs["openbao_secrets_seed_check_capabilities"] is True
    assert inputs["openbao_secrets_seed_register"] == "authelia_seed_result"
    # Fail closed: no local fallback values and no use of the ambient converge token.
    assert "openbao_secrets_seed_local_values" not in inputs
    assert "openbao_secrets_seed_revoke_token" not in inputs
    assert "BAO_TOKEN" not in inputs["openbao_secrets_seed_token"]


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
        if item["name"] == "https://github.com/jpe-ansible/homelab-contracts.git#/ansible/"
    )
    assert contracts["version"] == "v5.46.0"


def test_service_secrets_live_apart_from_the_client_secret_leaf():
    """The signing and session material never shares a leaf with the OIDC client secrets."""
    defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
    path = defaults["authelia_service_secrets_kv_path"]
    assert path == "apps/authelia-signing"
    assert path != "apps/authelia"
