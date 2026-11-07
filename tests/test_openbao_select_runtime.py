"""Run the collection's selector with local, credential-free fixtures."""

import json
import os
import shutil
import subprocess

import pytest
import yaml

from test_openbao_select import ROOT


@pytest.mark.parametrize(("selection", "cap", "expected", "failure"), [
    ({"policies": ["apps"]}, 25, {"policies": [{"name": "apps"}], "approles": []}, ""),
    ({"policies": ["read-*"], "approles": ["backup"]}, 25,
     {"policies": [{"name": "read-apps"}], "approles": [{"name": "backup"}]}, ""),
    ({"policies": ["unknown-*"]}, 25, {}, "unknown-*"),
    ({"policies": ["*"], "approles": ["backup"]}, 2, {}, "exceeding openbao_select_max=2"),
    ({}, 1, {"policies": [{"name": "apps"}, {"name": "read-apps"}], "approles": [{"name": "backup"}]}, ""),
])
def test_native_collection_selection(tmp_path, selection, cap, expected, failure):
    collection_root = tmp_path / "collections"
    namespace = collection_root / "ansible_collections/dryvist"
    namespace.mkdir(parents=True)
    (namespace / "secrets_management").symlink_to(ROOT, target_is_directory=True)
    playbook = tmp_path / "select.yml"
    playbook.write_text(yaml.safe_dump([{
        "name": "Verify object selection",
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "tasks": [
            {"name": "Resolve selection through the collection role",
             "ansible.builtin.include_role": {
                 "name": "dryvist.secrets_management.openbao",
                 "tasks_from": "init/selection-preflight.yml",
                 "apply": {"tags": ["always"]}},
             "tags": ["always"]},
            {"name": "Assert the selected targets", "ansible.builtin.assert": {
                "that": ["openbao_selected_objects == expected"]}, "tags": ["always"]},
        ],
    }]))
    variables = {
        "openbao_select": selection, "openbao_select_max": cap, "expected": expected,
        "openbao_select_profiles": {
            "policies": {"candidates": [{"name": "apps"}, {"name": "read-apps"}]},
            "approles": {"candidates": [{"name": "backup"}]},
        },
    }
    result = subprocess.run(
        [shutil.which("ansible-playbook"), "-i", "localhost,", str(playbook),
         "--tags", "openbao_rbac", "-e", json.dumps(variables)],
        cwd=ROOT, env={**os.environ, "ANSIBLE_COLLECTIONS_PATH": str(collection_root)},
        text=True, capture_output=True, timeout=60, check=False,
    )
    output = result.stdout + result.stderr
    if failure:
        assert result.returncode != 0 and failure in output, output
        assert "TASK [Assert the selected targets]" not in output
    else:
        assert result.returncode == 0, output
