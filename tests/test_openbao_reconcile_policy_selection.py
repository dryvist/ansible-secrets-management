"""The singleton reconcile policy is selectable and previews only its own write."""

import yaml

from test_openbao_select import ROLE, condition, render, resolve, task


KIND = "reconcile_policy"
POLICY_NAME = "openbao-reconcile"
SELECTION = {KIND: [POLICY_NAME]}
SELECTION_DEFAULTS = ROLE / "defaults/main/00-selection.yml"
POLICY_SYNC = ROLE / "tasks/init/02b-policy-sync.yml"
POLICY_PREVIEW = ROLE / "tasks/init/02c-policy-sync-preview.yml"


def selection_for_sync(selection):
    expression = task(
        "Resolve whether the reconcile policy is selected for sync", POLICY_SYNC
    )["ansible.builtin.set_fact"]["openbao_reconcile_policy_selected_for_sync"]
    expression = expression.replace(
        "dryvist.secrets_management.openbao_glob", "openbao_glob"
    )
    return render(expression, {
        "openbao_select": selection,
        "openbao_reconcile_policy_name": POLICY_NAME,
    })


def test_reconcile_policy_profile_selects_one_exact_update_endpoint():
    profile = yaml.safe_load(SELECTION_DEFAULTS.read_text())["openbao_select_profiles"][KIND]
    candidates = [
        {"name": render(item["name"], {"openbao_reconcile_policy_name": POLICY_NAME})}
        for item in profile["candidates"]
    ]
    assert candidates == [{"name": POLICY_NAME}]
    assert profile["prefix"] == "sys/policies/acl/"
    assert profile["suffixes"] == [""]
    assert profile["capability"] == "update"

    paths_expression = task(
        "Resolve the API paths addressed by selected OpenBao objects",
        ROLE / "tasks/init/selection-capabilities.yml",
    )["ansible.builtin.set_fact"]["openbao_selected_paths"]
    assert render(paths_expression, {
        "openbao_select_profiles": {KIND: profile},
        "openbao_selected_objects": {KIND: candidates},
        "openbao_reconcile_policy_name": POLICY_NAME,
    }) == [{
        "name": f"{KIND}: {POLICY_NAME}",
        "path": f"sys/policies/acl/{POLICY_NAME}",
        "capability": "update",
    }]
    grant = task(
        "Require a live write grant on every selected OpenBao object",
        ROLE / "tasks/init/selection-capabilities.yml",
    )["ansible.builtin.assert"]
    assert not condition(grant["that"][0], {
        "item": {"name": f"{KIND}: {POLICY_NAME}", "capability": "update"},
        "_capabilities": [],
    })


def test_unknown_reconcile_policy_name_is_rejected_and_never_sync_selected():
    matches, _ = resolve({KIND: ["unknown-policy"]}, KIND, names=(POLICY_NAME,))
    unmatched = task("Require every OpenBao selector to match a declared object")[
        "ansible.builtin.assert"
    ]
    assert not condition(unmatched["that"][0], {"item": matches[0]})
    assert selection_for_sync({KIND: ["unknown-policy"]}) is False
    assert selection_for_sync({KIND: [POLICY_NAME, "unknown-policy"]}) is False


def test_policy_sync_runs_for_empty_or_selected_reconcile_policy_only():
    sync = task("Sync the reconcile policy from the declared set (policy-sync)", POLICY_SYNC)
    variables = {
        "openbao_bootstrap_token": True,
        "openbao_reconcile_mode": True,
        "openbao_bounded_rbac_mode": True,
        "openbao_reconcile_policy_name": POLICY_NAME,
        "openbao_policy_sync_caps": {
            "rc": 0,
            "stdout": f'{{"data":{{"sys/policies/acl/{POLICY_NAME}":["update"]}}}}',
        },
    }
    for selection in ({}, SELECTION, {KIND: ["openbao-*"]}):
        assert selection_for_sync(selection) is True
        assert all(condition(gate, {
            **variables,
            "openbao_select": selection,
            "openbao_reconcile_policy_selected_for_sync": selection_for_sync(selection),
        }) for gate in sync["when"])

    for selection in ({"policies": ["apps"]}, {"approles": ["apps"]}):
        selected = selection_for_sync(selection)
        assert selected is False
        assert not all(condition(gate, {
            **variables,
            "openbao_select": selection,
            "openbao_reconcile_policy_selected_for_sync": selected,
        }) for gate in sync["when"])

    missing_update = {
        **variables,
        "openbao_select": SELECTION,
        "openbao_reconcile_policy_selected_for_sync": True,
        "openbao_policy_sync_caps": {
            "rc": 0,
            "stdout": f'{{"data":{{"sys/policies/acl/{POLICY_NAME}":["read"]}}}}',
        },
    }
    assert not all(condition(gate, missing_update) for gate in sync["when"])


def test_check_mode_preview_reads_live_policy_and_only_prints_real_diffs():
    read = task("Read the live policy for check-mode diff", POLICY_PREVIEW)
    assert read["ansible.builtin.command"]["argv"][-1] == "{{ openbao_policy_preview_name }}"
    assert read["check_mode"] is False
    assert read["changed_when"] is False
    assert read["environment"] == {
        "BAO_ADDR": "{{ openbao_cli_addr }}",
        "BAO_TOKEN": "{{ openbao_bootstrap_token }}",
    }
    assert read["delegate_to"] == "{{ openbao_cli_host }}"
    assert read["become"] == "{{ openbao_cli_become }}"
    assert read["failed_when"] is not False

    assert condition(read["failed_when"], {
        "openbao_policy_preview_live_read": {
            "rc": 2,
            "stderr": "Error reading policy: No policy named: new-policy",
        },
    }) is False
    assert condition(read["failed_when"], {
        "openbao_policy_preview_live_read": {
            "rc": 2,
            "stderr": "permission denied",
        },
    }) is True

    diff = task("Compute a unified line diff for the policy", POLICY_PREVIEW)
    assert diff["check_mode"] is False
    assert diff["changed_when"] is False
    assert diff["ansible.utils.fact_diff"] == {
        "before": "{{ openbao_policy_preview_live_text }}",
        "after": "{{ openbao_policy_preview_rendered_text }}",
    }
    assert diff["no_log"] is True
    assert "ansible.builtin.shell" not in diff
    assert diff["when"] == "openbao_policy_preview_live_text != openbao_policy_preview_rendered_text"
    report = task("Show the reconcile policy diff in check mode", POLICY_PREVIEW)
    assert report["ansible.builtin.debug"]["msg"] == "{{ openbao_policy_preview_diff.diff_lines }}"
    assert report["when"][0] == "not (openbao_policy_preview_paths_only | default(false) | bool)"

    path_changes = task("Resolve added and removed policy path stanzas", POLICY_PREVIEW)
    expression = path_changes["ansible.builtin.set_fact"]["openbao_policy_preview_path_changes"]
    before = '''path "secret/data/kept" {\n  capabilities = ["read"]\n}\npath "secret/data/removed" {\n  capabilities = ["update"]\n}'''
    after = '''path "secret/data/kept" {\n  capabilities = ["update"]\n}\npath "secret/data/added" {\n  capabilities = ["read"]\n}'''
    assert render(expression, {
        "openbao_policy_preview_live_text": before,
        "openbao_policy_preview_rendered_text": after,
    }) == [
        '- path "secret/data/kept" {\n  capabilities = ["read"]\n}',
        '- path "secret/data/removed" {\n  capabilities = ["update"]\n}',
        '+ path "secret/data/added" {\n  capabilities = ["read"]\n}',
        '+ path "secret/data/kept" {\n  capabilities = ["update"]\n}',
    ]

    before = '''path "auth/token/create" {
  capabilities = ["create", "update", "sudo"]
  required_parameters = ["policies", "type"]
  allowed_parameters = {
    "policies" = [["window-service"]]
    "type" = ["service"]
  }
}'''
    after = '''path "auth/token/create" {
  capabilities = ["create", "update", "sudo"]
  required_parameters = ["policies", "type", "ttl"]
  allowed_parameters = {
    "policies" = [["window-service"]]
    "type" = ["batch"]
  }
}'''
    assert render(expression, {
        "openbao_policy_preview_live_text": before,
        "openbao_policy_preview_rendered_text": after,
    }) == [
        '- path "auth/token/create" {\n'
        '  capabilities = ["create", "update", "sudo"]\n'
        '  required_parameters = ["policies", "type"]\n'
        '  allowed_parameters = {\n'
        '    "policies" = [["window-service"]]\n'
        '    "type" = ["service"]\n'
        '  }\n'
        '}',
        '+ path "auth/token/create" {\n'
        '  capabilities = ["create", "update", "sudo"]\n'
        '  required_parameters = ["policies", "type", "ttl"]\n'
        '  allowed_parameters = {\n'
        '    "policies" = [["window-service"]]\n'
        '    "type" = ["batch"]\n'
        '  }\n'
        '}',
    ]


def test_rbac_check_mode_includes_shared_path_preview_for_changed_policies():
    writes = ROLE / "tasks/init/08b-rbac-policy-writes.yml"
    preview = task("Preview changed RBAC policy paths in check mode", writes)
    assert preview["ansible.builtin.include_tasks"] == "02c-policy-sync-preview.yml"
    assert preview["loop"] == "{{ openbao_changed_policy_names }}"
    assert preview["vars"] == {
        "openbao_policy_preview_name": "{{ item }}",
        "openbao_policy_preview_after_text": "{{ openbao_rendered_policy_map[item] }}",
        "openbao_policy_preview_paths_only": True,
    }
    assert "ansible_check_mode" in preview["when"]
    assert "openbao_bootstrap_token is defined" in preview["when"]


def test_rbac_tag_reaches_the_policy_sync_import():
    site_play = yaml.safe_load((ROLE.parents[1] / "playbooks/site/04a-openbao.yml").read_text())[0]
    role_include = next(
        node for node in site_play["tasks"][0]["block"]
        if node.get("name") == "Include openbao role"
    )
    assert "openbao_rbac" in role_include["tags"]

    init_import = task("Initialize the cluster and resolve the provisioning token", ROLE / "tasks/init.yml")
    assert "always" in init_import["tags"]
    leader_import = task(
        "Resolve the Raft leader and sync the reconcile policy before any grant consumer runs",
        ROLE / "tasks/init/02-initialize-cluster.yml",
    )
    assert leader_import["ansible.builtin.import_tasks"] == "02b-policy-sync.yml"


def test_reconcile_policy_selection_leaves_other_rbac_writers_empty():
    init = ROLE / "tasks/init.yml"
    github = task("Reconcile selected GitHub permission sets", init)
    assert not all(condition(gate, {"openbao_select": SELECTION}) for gate in github["when"])

    human_gated = task("Reconcile the two human-gated AppRole policy attachments", init)
    assert not condition(human_gated["when"][0], {"openbao_select": SELECTION})

    policy_writes = ROLE / "tasks/init/08b-rbac-policy-writes.yml"
    write = task("Write the RBAC policies that are missing or changed", policy_writes)
    assert render(write["loop"], {"openbao_rbac_policy_targets": []}) == []

    approles = task("Declare AppRoles and reconcile their policy and TTL bounds", init)
    assert "openbao_rbac" not in approles["tags"]
