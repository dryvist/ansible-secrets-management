"""Selected GitHub permission sets use the shared selector and scoped writers."""

import pytest
import yaml

from test_openbao_select import ROLE, condition, render, resolve, task


KIND = "github_permission_sets"
SELECTED_NAME = "jacobpevans-ai-org-secrets"
SELECTION = {KIND: [SELECTED_NAME]}
PERMISSION_SETS = ROLE / "tasks/init/05-github-permission-sets.yml"


def changes(results):
    node = task("Resolve GitHub permission sets that are missing or changed", PERMISSION_SETS)
    return render(node["ansible.builtin.set_fact"]["openbao_github_permission_set_changes"], {
        "openbao_github_permission_set_checks": {"results": results},
    })


def test_permission_set_profile_uses_the_declared_admin_mount_sets():
    defaults = yaml.safe_load((ROLE / "defaults/main/03-github-engine.yml").read_text())
    assert "jacobpevans-ai" in {
        org["name"] for org in defaults["openbao_github_org_secrets_installations"]
    }
    candidates = render(defaults["openbao_github_org_secrets_permission_sets"], {
        "openbao_github_org_secrets_installations": [
            {"name": "jacobpevans-ai", "installation_id": 101},
            {"name": "another", "installation_id": 102},
        ],
        "openbao_github_org_secrets_permissions": {"organization_secrets": "write"},
    })
    profile = yaml.safe_load((ROLE / "defaults/main/00-selection.yml").read_text())[
        "openbao_select_profiles"][KIND]
    assert render(profile["candidates"], {
        "openbao_github_admin_permission_sets": candidates,
    }) == candidates
    assert resolve(SELECTION, KIND, tuple(item["name"] for item in candidates))[1] == [
        {"name": SELECTED_NAME},
    ]
    assert resolve({}, KIND, tuple(item["name"] for item in candidates))[1] == [
        {"name": item["name"]} for item in candidates
    ]


def test_selected_permission_set_capability_probe_names_one_exact_endpoint():
    profile = yaml.safe_load((ROLE / "defaults/main/00-selection.yml").read_text())[
        "openbao_select_profiles"][KIND]
    profile["prefix"] = render(profile["prefix"], {"openbao_github_mount": "github-configured"})
    expression = task(
        "Resolve the API paths addressed by selected OpenBao objects",
        ROLE / "tasks/init/selection-capabilities.yml",
    )["ansible.builtin.set_fact"]["openbao_selected_paths"]
    assert render(expression, {
        "openbao_select_profiles": {KIND: profile},
        "openbao_selected_objects": {KIND: [{"name": SELECTED_NAME}]},
    }) == [{
        "name": f"{KIND}: {SELECTED_NAME}",
        "path": f"github-configured/permissionset/{SELECTED_NAME}",
        "capability": "update",
    }]


def test_org_secrets_selection_checks_its_map_and_full_runs_check_every_map():
    assertions = {
        "repo-create": "Assert the repo-create permission map is exactly administration:write",
        "ci-resolver": "Assert the CI resolver permission map is exactly its four write permissions",
        "openhands": "Assert the OpenHands permission map is exactly its four permissions",
        "org-admin": "Assert the org-admin permission map is exactly organization_administration:write",
        "org-secrets": "Assert the org-secrets permission map is exactly organization_secrets:write",
    }
    cases = [
        (SELECTION, [{"name": SELECTED_NAME, "tier": "org-secrets"}], {"org-secrets"}),
        ({}, [], set(assertions)),
    ]
    for selection, targets, expected in cases:
        variables = {
            "openbao_select": selection,
            "openbao_github_permission_set_targets": targets,
            "openbao_bootstrap_token": True,
            "openbao_github_engine_enabled": True,
        }
        active = {
            tier for tier, name in assertions.items()
            if all(condition(gate, variables) for gate in task(name, PERMISSION_SETS)["when"])
        }
        assert active == expected


def test_shared_permission_set_reconcile_is_available_through_the_rbac_tag():
    selected = task("Reconcile selected GitHub permission sets", ROLE / "tasks/init.yml")
    assert selected["ansible.builtin.import_tasks"] == "init/05-github-permission-sets.yml"
    assert "openbao_rbac" in selected["tags"]
    assert all(condition(gate, {"openbao_select": SELECTION}) for gate in selected["when"])
    for selection in ({}, {"policies": ["apps"]}):
        assert not all(condition(gate, {"openbao_select": selection}) for gate in selected["when"])
    site_play = yaml.safe_load((ROLE.parents[1] / "playbooks/site/04a-openbao.yml").read_text())[0]
    assert "openbao" in site_play["tags"]
    full_tasks = yaml.safe_load((ROLE / "tasks/init/05-github-engine.yml").read_text())
    assert any(
        node.get("ansible.builtin.import_tasks") == "05-github-permission-sets.yml"
        for node in full_tasks
    )


def test_permission_set_reads_and_writes_use_only_selected_objects_and_the_run_token():
    desired = {"name": SELECTED_NAME, "installation_id": 101, "permissions": {"organization_secrets": "write"}}
    unselected = {"name": "another-org-secrets", "installation_id": 102}
    selector = task("Select GitHub permission set objects", PERMISSION_SETS)
    assert selector["ansible.builtin.import_tasks"] == "select-objects.yml"
    assert selector["vars"]["openbao_select_kind"] == KIND
    assert render(selector["vars"]["openbao_select_candidates"], {
        "openbao_github_admin_permission_sets": [desired, unselected],
    }) == [desired, unselected]
    keep = task("Keep the selected GitHub permission set objects", PERMISSION_SETS)
    targets = render(keep["ansible.builtin.set_fact"]["openbao_github_permission_set_targets"], {
        "openbao_object_targets": [desired],
    })
    read = task("Read the GitHub token permission sets", PERMISSION_SETS)
    assert render(read["loop"], {"openbao_github_permission_set_targets": targets}) == [desired]
    assert read["check_mode"] is False
    assert read["changed_when"] is False
    assert read["ansible.builtin.uri"]["status_code"] == [200, 404]
    assert read.get("failed_when") is not False
    pending = changes([{"status": 404, "item": desired}])
    assert pending == [desired]
    write = task("Reconcile the GitHub token permission sets", PERMISSION_SETS)
    assert render(write["loop"], {"openbao_github_permission_set_changes": pending}) == [desired]
    for node in (read, write):
        assert node["ansible.builtin.uri"]["headers"]["X-Vault-Token"] == "{{ openbao_bootstrap_token }}"
        assert node["ansible.builtin.uri"]["follow_redirects"] == "none"
        assert node["ansible.builtin.uri"]["use_proxy"] is False
        assert node["no_log"] is True
    initialization = task(
        "Use the per-call reconcile token when it authenticated", ROLE / "tasks/init/02-initialize-cluster.yml",
    )
    assert initialization["ansible.builtin.set_fact"]["openbao_bootstrap_token"] == (
        "{{ openbao_reconcile_login.login.auth.client_token }}"
    )


@pytest.mark.parametrize("optional_fields", [
    {},
    {"permissions": {"organization_secrets": "write"}},
    {"permissions": {"contents": "write"}, "repositories": ["selected-repository"]},
])
def test_permission_set_write_preserves_the_declared_request_shape(optional_fields):
    write = task("Reconcile the GitHub token permission sets", PERMISSION_SETS)
    assert render(write["ansible.builtin.uri"]["body"], {
        "item": {"name": SELECTED_NAME, "installation_id": "101", **optional_fields},
    }) == {"installation_id": 101, **optional_fields}


@pytest.mark.parametrize("live_change", [
    {"installation_id": 102},
    {"permissions": {"contents": "read"}},
    {"repositories": ["another-repository"]},
])
def test_permission_set_drift_in_each_stored_field_is_reported(live_change):
    desired = {
        "name": "selected-set", "installation_id": 101,
        "permissions": {"contents": "write"}, "repositories": ["selected-repository"],
    }
    live = {key: value for key, value in desired.items() if key != "name"}
    assert changes([{"status": 200, "item": desired, "json": {"data": {**live, **live_change}}}]) == [desired]


def test_unchanged_permission_sets_are_absent_from_the_would_change_list():
    desired = {"name": SELECTED_NAME, "installation_id": "101"}
    assert changes([{
        "status": 200, "item": desired,
        "json": {"data": {"installation_id": 101, "permissions": None, "repositories": None}},
    }]) == []
    report = task("Report GitHub permission sets that would be written in check mode", PERMISSION_SETS)
    assert render(report["ansible.builtin.debug"]["msg"], {
        "openbao_github_permission_set_changes": [],
    }) == "No GitHub permission set writes are needed."


def test_check_mode_reports_the_single_missing_set_and_never_posts():
    desired = {"name": SELECTED_NAME, "installation_id": 101}
    pending = changes([{"status": 404, "item": desired}])
    report = task("Report GitHub permission sets that would be written in check mode", PERMISSION_SETS)
    assert render(report["ansible.builtin.debug"]["msg"], {
        "openbao_github_permission_set_changes": pending,
    }) == f"Would write GitHub permission sets: {SELECTED_NAME}"
    write = task("Reconcile the GitHub token permission sets", PERMISSION_SETS)
    check_guard = next(gate for gate in write["when"] if "ansible_check_mode" in gate)
    report_guard = next(gate for gate in report["when"] if "ansible_check_mode" in gate)
    assert not condition(check_guard, {"ansible_check_mode": True})
    assert condition(check_guard, {"ansible_check_mode": False})
    assert condition(report_guard, {"ansible_check_mode": True})
    assert not condition(report_guard, {"ansible_check_mode": False})


def test_github_only_selection_leaves_every_other_object_writer_empty():
    selected = {
        kind: resolve(SELECTION, kind)[1]
        for kind in ("policies", "approles", "ssh_roles", "rotation_exempt")
    }
    assert selected == {kind: [] for kind in selected}

    policy_write = task(
        "Write the RBAC policies that are missing or changed",
        ROLE / "tasks/init/08b-rbac-policy-writes.yml",
    )
    assert render(policy_write["loop"], {"openbao_rbac_policy_targets": selected["policies"]}) == []

    approle_writers = [
        ("10-approles.yml", "Create the missing AppRoles bound to their policy"),
        ("10-approles.yml", "Reconcile token_policies on existing AppRoles"),
        ("10c-approle-ttl-bounds.yml", "Reconcile AppRole TTL and token bounds on existing AppRoles"),
    ]
    for filename, name in approle_writers:
        assert render(task(name, ROLE / "tasks/init" / filename)["loop"], {
            "openbao_approle_config_targets": selected["approles"],
            "openbao_manageable_approles": [{"name": "unselected"}],
            "openbao_approle_checks": {"results": [{"item": {"name": "unselected"}, "rc": 1}]},
        }) == []

    ssh_write = task("Reconcile the SSH signing roles", ROLE / "tasks/init/07-ssh-ca-engine.yml")
    assert render(ssh_write["loop"], {
        "openbao_selected_objects": selected,
        "openbao_ssh_role_checks": {"results": []},
    }) == []
    rotation_write = task(
        "Tag operator-declared rotation-exempt paths (write-if-changed)", ROLE / "tasks/init.yml",
    )
    assert render(rotation_write["loop"], {"openbao_selected_objects": selected}) == []
