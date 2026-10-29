"""The Nautobot token publisher stays inert and scoped to its two KV entries."""

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "roles/openbao/templates/nautobot-token-publisher-policy.hcl.j2"
NAMES = ROOT / "roles/openbao/defaults/main/05b-domain-policy-approle-names.yml"
APPROLES = ROOT / "roles/openbao/defaults/main/07b-base-approles.yml"
POLICIES = ROOT / "roles/openbao/defaults/main/07c-base-policies.yml"
TTLS = ROOT / "roles/openbao/defaults/main/07a-derived-rollups-and-ttls.yml"
ISSUER = ROOT / "roles/openbao/templates/approle-issuer-policy.hcl.j2"
EXCLUSIONS = ROOT / "roles/openbao/defaults/main/05d-reconcile-exclusions.yml"
SEMAPHORE = ROOT / "roles/openbao/templates/semaphore-policy.hcl.j2"
ANSIBLE_CONVERGE = ROOT / "roles/openbao/templates/ansible-converge-policy.hcl.j2"

POLICY_NAME = "{{ openbao_nautobot_token_publisher_policy_name }}"
APPROLE_NAME = "{{ openbao_nautobot_token_publisher_approle_name }}"


def test_policy_has_only_the_four_exact_data_and_metadata_grants():
    template = TEMPLATE.read_text(encoding="utf-8")
    path_blocks = re.findall(
        r'^path "([^"]+)" \{\n  capabilities = \[([^]]+)\]\n\}',
        template,
        flags=re.MULTILINE,
    )

    assert path_blocks == [
        ("{{ openbao_kv_mount }}/data/apps/nautobot/pipeline", '"create", "read", "update"'),
        ("{{ openbao_kv_mount }}/data/apps/nautobot/sync-write", '"create", "read", "update"'),
        ("{{ openbao_kv_mount }}/metadata/apps/nautobot/pipeline", '"read"'),
        ("{{ openbao_kv_mount }}/metadata/apps/nautobot/sync-write", '"read"'),
    ]
    assert len(re.findall(r'^path "', template, flags=re.MULTILINE)) == 4


def test_policy_and_inert_approle_are_registered():
    names = yaml.safe_load(NAMES.read_text(encoding="utf-8"))
    approles = yaml.safe_load(APPROLES.read_text(encoding="utf-8"))[
        "openbao_base_approles_core"
    ]
    policies = yaml.safe_load(POLICIES.read_text(encoding="utf-8"))[
        "openbao_base_policies_static"
    ]

    role = next(item for item in approles if item.get("name") == APPROLE_NAME)
    policy = next(item for item in policies if item.get("name") == POLICY_NAME)

    assert names["openbao_nautobot_token_publisher_policy_name"] == "nautobot-token-publisher"
    assert names["openbao_nautobot_token_publisher_approle_name"] == "nautobot-token-publisher"
    assert role["policy"] == POLICY_NAME
    assert policy["template"] == TEMPLATE.name
    assert role["manage_secret_id"] is False
    assert role["secret_id_ttl"] == "{{ openbao_ai_elevated_secret_id_ttl }}"
    assert role["secret_id_num_uses"] == 1
    assert role["token_ttl"] == role["token_max_ttl"] == "{{ openbao_ai_admin_token_ttl }}"
    assert "secret_id_issuance" not in role


def test_secret_id_is_short_lived_and_not_minted_by_the_issuer():
    ttls = yaml.safe_load(TTLS.read_text(encoding="utf-8"))
    issuer = ISSUER.read_text(encoding="utf-8")

    assert ttls["openbao_ai_elevated_secret_id_ttl"] == "15m"
    assert "selectattr('secret_id_issuance', 'defined')" in issuer
    assert "rejectattr('manage_secret_id', 'defined')" in issuer
    assert "openbao_nautobot_token_publisher_approle_name" not in issuer

    reconcile_exclusions = yaml.safe_load(EXCLUSIONS.read_text(encoding="utf-8"))[
        "openbao_reconcile_excluded_policies"
    ]
    # The narrow inert role follows github-enterprise-read. The admin policy is
    # separately excluded because it is the full-grant human tier.
    assert APPROLE_NAME not in reconcile_exclusions


def test_execution_plane_policies_do_not_receive_sync_write_access():
    assert "apps/nautobot/sync-write" not in SEMAPHORE.read_text(encoding="utf-8")
    assert "apps/nautobot/sync-write" not in ANSIBLE_CONVERGE.read_text(encoding="utf-8")


def test_source_class_is_workstation_only():
    overrides = yaml.safe_load(
        (ROOT / "roles/openbao/defaults/main/08b-cidr-and-unlock.yml").read_text(encoding="utf-8")
    )["openbao_approle_cidr_class_overrides"]
    assert overrides["nautobot-token-publisher"] == "workstation"
