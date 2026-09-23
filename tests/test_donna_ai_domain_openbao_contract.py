"""Static contract checks for Donna's Vikunja bridge token living at ai/donna."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DATA_PATH = 'path "{{ openbao_kv_mount }}/data/ai/donna"'
CANONICAL_METADATA_PATH = 'path "{{ openbao_kv_mount }}/metadata/ai/donna"'


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _read_role_defaults(role: str) -> dict:
    """Load role defaults, merging defaults/main/*.yml like Ansible does."""
    single = ROOT / "roles" / role / "defaults" / "main.yml"
    if single.exists():
        return yaml.safe_load(single.read_text(encoding="utf-8"))

    merged: dict = {}
    main_dir = ROOT / "roles" / role / "defaults" / "main"
    for path in sorted(main_dir.glob("*.yml")):
        merged.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return merged


def test_ansible_converge_owns_the_exact_donna_publisher_path():
    policy = _read("roles/openbao/templates/ansible-converge-policy.hcl.j2")

    data_grant: str = (
        f'{CANONICAL_DATA_PATH} {{\n'
        '  capabilities = ["create", "update", "read"]\n}'
    )
    metadata_grant: str = f'{CANONICAL_METADATA_PATH} {{\n  capabilities = ["read"]\n}}'

    assert data_grant in policy
    assert metadata_grant in policy


def test_donna_bridge_identity_publishes_to_its_own_domain():
    defaults = _read_role_defaults("vikunja")
    identity = next(
        item
        for item in defaults["vikunja_hermes_bridge_identities"]
        if item["username"] == "donna"
    )

    assert identity["openbao_path"] == "ai/donna"
    assert identity["kv_field"] == "DONNA_VIKUNJA_API_TOKEN"


def test_ai_donna_reader_policy_cannot_read_ai_hermes():
    # ai-donna is donna's OWN read-only AppRole (secret/ai/donna) — it must
    # never also see the hermes agent's shared credential bundle.
    policy = _read("roles/openbao/templates/ai-donna-policy.hcl.j2")

    assert 'path "{{ openbao_kv_mount }}/data/ai/donna"' in policy
    assert "ai/hermes" not in policy
    assert "/data/ai/*" not in policy
