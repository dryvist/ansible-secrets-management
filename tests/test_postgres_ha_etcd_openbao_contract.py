"""Static contract check for Patroni's per-cluster etcd/PKI credentials.

roles/postgres's patroni_etcd_credential.yml generates and reads back
Patroni's own etcd password at secret/etcd/<postgres_ha_scope>/rw, and
patroni_etcd_tls.yml / patroni_client_tls.yml issue this cluster's etcd
server/peer and Patroni-client certificates from OpenBao's PKI secrets
engine. All three log in as the shared ansible-converge identity -- that
token must resolve to an identity the ansible-converge policy actually
grants secret/etcd/* (KV) and pki-*-etcd/issue/* (PKI) to, or the first live
converge fails at that task -- this asserts both grants exist, the same
shape as test_donna_ai_domain_openbao_contract.py's check for ai/donna.
"""

from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DATA_PATH = 'path "{{ openbao_kv_mount }}/data/etcd/*"'
CANONICAL_METADATA_PATH = 'path "{{ openbao_kv_mount }}/metadata/etcd/*"'
DERIVE_TASK_NAME = "Derive this cluster's etcd PKI engine entry from its scope"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _render_engine_entry_for_scope(scope: str, suffix: str) -> dict:
    """Render the REAL derivation task for one loop iteration (one scope)."""
    tasks = yaml.safe_load(_read("roles/openbao/tasks/init/07b-etcd-pki-engine.yml"))
    task = next(t for t in tasks if t.get("name") == DERIVE_TASK_NAME)

    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "item": scope,
        "postgres_ha_pki_role_suffix": suffix,
        "openbao_pki_etcd_engines_max_ttl": "4320h0m0s",
        "tofu_data": {},
    }
    role = templar.template(trust_as_template(task["vars"]["_openbao_etcd_pki_role"]))

    templar.available_variables["_openbao_etcd_pki_role"] = role
    engines = templar.template(
        trust_as_template(task["ansible.builtin.set_fact"]["openbao_pki_etcd_engines"])
    )
    assert isinstance(engines, list) and len(engines) == 1, (scope, engines)
    return engines[0]


def _render_postgres_pki_names(scope: str, suffix: str) -> tuple:
    """Render the REAL postgres_ha_pki_role/_mount defaults for one scope."""
    defaults = yaml.safe_load(_read("roles/postgres/defaults/main/03-patroni.yml"))

    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "postgres_ha_scope": scope,
        "postgres_ha_pki_role_suffix": suffix,
    }
    role = templar.template(trust_as_template(defaults["postgres_ha_pki_role"]))

    templar.available_variables["postgres_ha_pki_role"] = role
    mount = templar.template(trust_as_template(defaults["postgres_ha_pki_mount"]))
    return role, mount


def test_derived_etcd_pki_engine_matches_what_postgres_computes():
    """Every declared scope renders exactly one engine entry whose mount and
    role equal what roles/postgres computes for that same scope.

    Renders the REAL expressions out of both task/defaults files, never a
    reimplementation of either formula -- catches drift the moment either
    side changes its naming scheme without the other (the exact defect the
    PR that added postgres_ha_patroni_scopes/postgres_ha_pki_role_suffix
    exists to prevent).
    """
    suffix = "-etcd"
    for scope in ("postgres-ai", "postgres-patroni-test"):
        entry = _render_engine_entry_for_scope(scope, suffix)
        postgres_role, postgres_mount = _render_postgres_pki_names(scope, suffix)

        assert entry["scope"] == scope
        assert entry["role"] == postgres_role == f"{scope}{suffix}"
        assert entry["mount"] == postgres_mount == f"pki-{scope}{suffix}"


def test_ansible_converge_owns_the_etcd_credential_wildcard():
    policy = _read("roles/openbao/templates/ansible-converge-policy.hcl.j2")

    data_grant = (
        f'{CANONICAL_DATA_PATH} {{\n'
        '  capabilities = ["create", "update", "read"]\n}'
    )
    metadata_grant = (
        f'{CANONICAL_METADATA_PATH} {{\n'
        '  capabilities = ["read", "list"]\n}'
    )

    assert data_grant in policy
    assert metadata_grant in policy


def test_patroni_etcd_credential_task_uses_the_documented_scope_path():
    task_file = _read("roles/postgres/tasks/main/patroni_etcd_credential.yml")

    assert "secret/data/etcd/{{ postgres_ha_scope }}/rw" in task_file


def test_ansible_converge_can_issue_from_each_cluster_pki_role():
    """Exact create/update on issue only -- no sign-verbatim, no root.

    Enumerated per openbao_pki_etcd_engines entry, never a Vault ACL glob:
    OpenBao's trailing '*' can't match a scope embedded inside one path
    segment (pki-<scope>-etcd), and '+' only ever replaces a whole segment,
    so there is no valid wildcard shorthand for a per-cluster mount name.
    """
    policy = _read("roles/openbao/templates/ansible-converge-policy.hcl.j2")

    etcd_pki_grant = (
        "{% for engine in openbao_pki_etcd_engines %}\n"
        'path "{{ engine.mount }}/issue/{{ engine.role }}" {\n'
        '  capabilities = ["create", "update"]\n}\n\n'
        'path "{{ engine.mount }}/issue/{{ engine.role }}-patroni" {\n'
        '  capabilities = ["create", "update"]\n}\n\n'
        "{% endfor %}"
    )

    assert etcd_pki_grant in policy
    # Checked as a granted capability (quoted, inside a capabilities = [...]
    # list), not a bare substring -- the surrounding comment names
    # "sign-verbatim" and "root/generate" in prose explaining what this grant
    # deliberately excludes, which a substring check would trip on.
    assert '"sign-verbatim"' not in policy
    assert '"root/generate"' not in policy
    assert "/root/generate/internal" not in policy


def test_postgres_ha_pki_placeholders_are_gone():
    """postgres_ha_pki_addr/_token never supplied an identity -- deleted.

    Every etcd/PKI task now logs in as the shared ansible-converge identity
    (postgres_ha_bao_addr/_role_id/_secret_id) instead.
    """
    for relative_path in (
        "roles/postgres/defaults/main/03-patroni.yml",
        "roles/postgres/tasks/main/patroni_prereqs.yml",
        "roles/postgres/tasks/main/patroni_etcd_tls.yml",
        "roles/postgres/tasks/main/patroni_client_tls.yml",
        "roles/postgres/tasks/main/patroni_etcd_credential.yml",
    ):
        contents = _read(relative_path)
        assert "postgres_ha_pki_addr" not in contents, relative_path
        assert "postgres_ha_pki_token" not in contents, relative_path


def test_patroni_pki_tls_tasks_log_in_and_revoke():
    """Each TLS/credential task file logs in once and revokes in an always:.

    "One login per play section, not per task" -- roles/object_storage's
    offsite/iam tasks and roles/openbao_secrets/tasks/publish.yml establish
    this shape (vault_login -> block of work -> always: vault_write revoke
    auth/token/revoke-self).
    """
    for relative_path in (
        "roles/postgres/tasks/main/patroni_etcd_tls.yml",
        "roles/postgres/tasks/main/patroni_client_tls.yml",
        "roles/postgres/tasks/main/patroni_etcd_credential.yml",
    ):
        contents = _read(relative_path)
        assert contents.count("community.hashi_vault.vault_login:") == 1, relative_path
        assert "auth/token/revoke-self" in contents, relative_path
        assert "always:" in contents, relative_path
        assert "postgres_ha_bao_addr" in contents, relative_path
