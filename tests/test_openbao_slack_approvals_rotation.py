"""The slack-approvals AppRole is rotated into Doppler and mints nothing at converge."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
APPROVALS_NAME = "{{ openbao_slack_approvals_approle_name }}"


def _load(name):
    return yaml.safe_load((DEFAULTS / name).read_text())


def test_doppler_republish_lists_include_slack_approvals():
    doc = _load("08c-rotator-doppler-sync.yml")
    assert APPROVALS_NAME in doc["openbao_rotate_doppler_only_domains"]
    assert "openbao_slack_approvals_approle_name" in doc["openbao_rotate_doppler_sync_domains"]


def test_slack_approvals_is_a_rotated_domain():
    doc = _load("05c-terrakube-and-remaining-domain-names.yml")
    assert "openbao_slack_approvals_approle_name" in doc["openbao_secrets_domain_approle_names"]


def test_slack_approvals_mints_no_secret_id_at_converge():
    rows = _load("07f-elevated-approles.yml")["openbao_base_approles_elevated"]
    row = next(row for row in rows if row["name"] == APPROVALS_NAME)
    assert row["manage_secret_id"] is False
