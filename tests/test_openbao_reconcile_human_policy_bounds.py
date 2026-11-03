"""Human-gated reconcile policies preserve exact bodies and attachments."""

from openbao_reconcile_bounds_helpers import (
    POLICY_WRITE_TASKS,
    RECONCILE,
    TEMPLATES,
    _allowed_parameters,
    _render,
    _stanzas,
    rendered_defaults,
)
import json
import re
import yaml

def test_reconcile_pins_the_two_human_gated_policy_bodies_and_attachments(rendered_defaults):
    values, approles, policies = rendered_defaults
    reconcile = _render(RECONCILE, values)
    policy_entries = {
        entry["name"]: entry for entry in policies
        if entry["name"] in {
            values["openbao_tofu_state_admin_policy_name"],
            values["openbao_github_mount_config_policy_name"],
        }
    }
    assert policy_entries == {
        values["openbao_tofu_state_admin_policy_name"]: {
            "name": values["openbao_tofu_state_admin_policy_name"],
            "template": "tofu-state-admin-policy.hcl.j2",
        },
        values["openbao_github_mount_config_policy_name"]: {
            "name": values["openbao_github_mount_config_policy_name"],
            "template": "github-mount-config-policy.hcl.j2",
        },
    }

    for policy_name, template_name in (
        (values["openbao_tofu_state_admin_policy_name"], "tofu-state-admin-policy.hcl.j2"),
        (values["openbao_github_mount_config_policy_name"], "github-mount-config-policy.hcl.j2"),
    ):
        path = f"sys/policies/acl/{policy_name}"
        body = next(body for candidate, body in _stanzas(reconcile) if candidate == path)
        # lookup('template') | trim removes the template terminator; the
        # command module's explicit stdin_add_newline appends one byte before
        # bao receives the policy body.
        policy_text = _render(TEMPLATES / template_name, values).strip() + "\n"
        assert _allowed_parameters(body) == {
            "policy": [policy_text]
        }
        capabilities = re.search(r"capabilities\s*=\s*(\[[^\]]*\])", body)
        assert capabilities and "read" in json.loads(capabilities.group(1))
        # A required parameter also applies to read, which carries no body.
        assert "required_parameters" not in body

    policy_write_tasks = yaml.safe_load(POLICY_WRITE_TASKS.read_text(encoding="utf-8"))
    policy_write = next(
        task for task in policy_write_tasks
        if task.get("name") == "Write the RBAC policies that are missing or changed"
    )
    assert policy_write["ansible.builtin.command"]["stdin_add_newline"] is True

    expected_roles = {
        values["openbao_ai_admin_session_approle_name"]: values[
            "openbao_approle_cli_parameters"
        ][values["openbao_ai_admin_session_approle_name"]]["token_policies"].split(","),
        values["openbao_policy_sync_approle_name"]: values[
            "openbao_approle_cli_parameters"
        ][values["openbao_policy_sync_approle_name"]]["token_policies"].split(","),
    }
    assert values["openbao_tofu_state_admin_policy_name"] in expected_roles[
        values["openbao_ai_admin_session_approle_name"]
    ]
    assert values["openbao_github_mount_config_policy_name"] in expected_roles[
        values["openbao_policy_sync_approle_name"]
    ]
    role_declarations = {role["name"]: role for role in approles}
    assert values["openbao_ai_admin_session_approle_name"] in (
        values["openbao_reconcile_excluded_policies"]
    )
    assert values["openbao_policy_sync_policy_name"] in (
        values["openbao_reconcile_excluded_policies"]
    )
    managed_approle_names = {
        role["name"] for role in approles
        if "manage_secret_id" not in role
        and role["name"] not in values["openbao_reconcile_excluded_policies"]
    }
    for role_name, expected_policies in expected_roles.items():
        assert role_declarations[role_name]["manage_secret_id"] is False
        assert role_name not in managed_approle_names
        role_path = f"auth/approle/role/{role_name}"
        role_body = next(body for path, body in _stanzas(reconcile) if path == role_path)
        role_caps = re.search(r"capabilities\s*=\s*(\[[^\]]*\])", role_body)
        assert role_caps and json.loads(role_caps.group(1)) == ["read"]

        policies_path = f"{role_path}/policies"
        policies_body = next(
            body for path, body in _stanzas(reconcile) if path == policies_path
        )
        policy_caps = re.search(r"capabilities\s*=\s*(\[[^\]]*\])", policies_body)
        assert policy_caps and json.loads(policy_caps.group(1)) == ["update"]
        assert _allowed_parameters(policies_body) == {
            "token_policies": [",".join(expected_policies)]
        }
        required = re.search(
            r"(?m)^\s*required_parameters\s*=\s*(\[[^\n]*\])\s*$",
            policies_body,
        )
        assert required and json.loads(required.group(1)) == ["token_policies"]


def test_reconcile_policy_paths_it_reads_carry_no_required_parameters(rendered_defaults):
    values, _approles, _policies = rendered_defaults
    reconcile = _render(RECONCILE, values)
    readable = [
        path for path, body in _stanzas(reconcile)
        if path.startswith("sys/policies/acl/")
        and (caps := re.search(r"capabilities\s*=\s*(\[[^\]]*\])", body))
        and "read" in json.loads(caps.group(1))
        and "required_parameters" in body
    ]
    assert readable == []
