"""The Hatchet eval identity can mint only its exact repository status set."""

from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"


def _defaults(name):
    return yaml.safe_load((DEFAULTS / name).read_text(encoding="utf-8"))


def _trust(value):
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, list):
        return [_trust(item) for item in value]
    if isinstance(value, dict):
        return {key: _trust(item) for key, item in value.items()}
    return value


def _render(expression, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = _trust(variables)
    return templar.template(_trust(expression))


def test_permission_set_is_exactly_one_repository_status_writer():
    github = _defaults("03-github-engine.yml")
    set_name = github["openbao_github_role_eval_status_set_name"]
    permissions = github["openbao_github_role_eval_status_permissions"]
    declaration = github["openbao_github_role_eval_status_permission_sets"][0]
    permission_sets = _render(
        github["openbao_github_role_eval_status_permission_sets"],
        {
            "openbao_github_role_eval_status_set_name": set_name,
            "openbao_github_role_eval_status_permissions": permissions,
            "openbao_github_dryvist_installation_id": "4242",
        },
    )

    assert declaration["tier"] == "agents"
    assert declaration["repositories"] == ["ansible-proxmox-ai"]
    assert permissions == {"statuses": "write", "metadata": "read"}
    assert permission_sets == [
        {
            "name": set_name,
            "tier": "agents",
            "installation_id": "4242",
            "repositories": declaration["repositories"],
            "permissions": permissions,
        }
    ]
    assert "openbao_github_role_eval_status_permission_sets" in github[
        "openbao_github_admin_permission_sets"
    ]


def test_app_role_policy_machine_class_and_secret_id_lifecycle_are_registered():
    names = _defaults("05b-domain-policy-approle-names.yml")
    approles = _defaults("07b-base-approles.yml")["openbao_base_approles_core"]
    policies = _defaults("07c-base-policies.yml")["openbao_base_policies_static"]
    role_name = names["openbao_hatchet_eval_status_approle_name"]
    policy_name = names["openbao_hatchet_eval_status_policy_name"]
    role = next(
        item for item in approles
        if item.get("name") == "{{ openbao_hatchet_eval_status_approle_name }}"
    )
    policy = next(
        item for item in policies
        if item.get("name") == "{{ openbao_hatchet_eval_status_policy_name }}"
    )
    ttl_defaults = _defaults("08a-admin-and-ttls.yml")
    host_secret_zero = _defaults("05c-terrakube-and-remaining-domain-names.yml")[
        "openbao_host_secret_zero_approle_names"
    ]

    assert role_name == policy_name
    assert role["policy"] == "{{ openbao_hatchet_eval_status_policy_name }}"
    assert role["token_ttl"] == "15m"
    assert policy["template"] == "hatchet-eval-status-policy.hcl.j2"
    assert (
        _defaults("08b-cidr-and-unlock.yml")["openbao_approle_cidr_class_overrides"][role_name]
        == "machine"
    )
    assert ttl_defaults["openbao_approle_secret_id_ttl_overrides_base"][role_name] == "0s"
    assert ttl_defaults["openbao_approle_secret_id_num_uses_overrides"][role_name] == 0
    assert "{{ openbao_hatchet_eval_status_approle_name }}" in host_secret_zero
