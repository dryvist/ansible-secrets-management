"""Human-gated AppRole reconciliation changes only policy attachments."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "roles/openbao/tasks/init.yml"
TASK_FILE = ROOT / "roles/openbao/tasks/init/08c-human-gated-approle-policies.yml"


def _task(tasks, name):
    return next(task for task in tasks if task.get("name") == name)


def test_attachment_reconcile_is_tagged_and_only_runs_in_reconcile_mode():
    tasks = yaml.safe_load(INIT.read_text(encoding="utf-8"))
    imported = _task(tasks, "Reconcile the two human-gated AppRole policy attachments")

    assert imported["ansible.builtin.import_tasks"] == (
        "init/08c-human-gated-approle-policies.yml"
    )
    assert "openbao_rbac" in imported["tags"]
    assert any("openbao_reconcile_mode" in condition for condition in imported["when"])


def test_attachment_write_uses_only_the_pinned_token_policies_parameter():
    tasks = yaml.safe_load(TASK_FILE.read_text(encoding="utf-8"))
    update = _task(tasks, "Reconcile token_policies on the human-gated AppRoles")
    read = _task(tasks, "Read each human-gated AppRole before reconciling token_policies")
    probe = _task(tasks, "Ask whether this identity may reconcile the human-gated AppRole policies")

    command = update["ansible.builtin.command"]["cmd"]
    assert "bao write {{ item.0.policies_path }}" in command
    assert "token_policies={{ item.0.token_policies | join(',') }}" in command
    assert "secret_id" not in command
    assert "bound_cidrs" not in command
    assert "token_ttl" not in command
    assert update["no_log"] is True
    assert update["changed_when"] is True
    assert any("'update' in" in condition for condition in update["when"])
    assert any("token_policies" in condition and "!=" in condition for condition in update["when"])

    assert read["ansible.builtin.command"]["cmd"] == (
        "bao read -format=json {{ item.role_path }}"
    )
    assert read["changed_when"] is False
    assert read["no_log"] is True
    assert "role_path" in probe["ansible.builtin.command"]["cmd"]
    assert "policies_path" in probe["ansible.builtin.command"]["cmd"]


def test_reconcile_mount_include_keeps_policy_sync_and_mount_capability_gate():
    tasks = yaml.safe_load(INIT.read_text(encoding="utf-8"))
    mount_include = _task(tasks, "Configure the per-App GitHub mounts")
    when_text = " ".join(str(condition) for condition in mount_include["when"])

    assert "openbao_reconcile_mode" in when_text
    assert "openbao_policy_sync_caps.rc" in when_text
    assert "sys/policies/acl/" in when_text
    assert "openbao_reconcile_policy_name" in when_text
    assert "openbao_policy_sync_capability_map" in str(mount_include["vars"])
    assert "sys/mounts/" in str(mount_include["vars"])
