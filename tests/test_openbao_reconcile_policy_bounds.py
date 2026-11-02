"""Rendered and enforced bounds for the OpenBao reconcile KV ACL."""

import json
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml
from ansible.template import trust_as_template

from test_openbao_reconcile_grant_bounds import (
    RECONCILE,
    _allowed_parameters,
    _render,
    _stanzas,
    _templar,
    _trust,
    rendered_defaults,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_SYNC = ROOT / "roles/openbao/tasks/init/02b-policy-sync.yml"
PATH_COMPONENTS = "^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$"


def _request(base, token, method, path, body=None):
    request = urllib.request.Request(
        f"{base}/v1/{path}",
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"X-Vault-Token": token},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def test_rendered_kv_config_grants_pin_each_mount_to_its_declared_retention(
    rendered_defaults,
):
    values, _approles, _policies = rendered_defaults
    mounts = [
        {
            "path": values["openbao_config_mount"],
            "max_versions": values["openbao_config_mount_max_versions"],
        },
        {"path": values["openbao_kv_mount"], "max_versions": 7},
    ]
    context = dict(values, openbao_kv_tuned_mounts=mounts)
    stanzas = dict(_stanzas(_render(RECONCILE, context)))

    for mount in mounts:
        body = stanzas[f"{mount['path']}/config"]
        assert _allowed_parameters(body) == {
            "max_versions": [str(mount["max_versions"])]
        }


@pytest.mark.parametrize(
    ("key", "valid"),
    [
        ("apps/open-llm/nested_key.v1", True),
        ("apps/bad*key", False),
        ("apps/bad+key", False),
        ('apps/bad"key', False),
        ("apps/foo..bar", False),
        ("/apps/open-llm", False),
        ("apps/open-llm/", False),
        ("apps/bad key", False),
    ],
)
def test_kv_path_assert_accepts_only_literal_nested_components(key, valid):
    tasks = yaml.safe_load(POLICY_SYNC.read_text(encoding="utf-8"))
    guard = next(
        task for task in tasks
        if task.get("name") == "Assert reconcile KV grant keys are literal path components"
    )
    conditions = guard["ansible.builtin.assert"]["that"]
    templar = _templar(_trust({"item": key}))

    results = [
        templar.template(trust_as_template("{{ " + condition + " }}"))
        for condition in conditions
    ]
    assert all(result is True or result == "True" for result in results) is valid


def test_path_guard_covers_template_sources_and_precedes_policy_write():
    tasks = yaml.safe_load(POLICY_SYNC.read_text(encoding="utf-8"))
    names = [task.get("name") for task in tasks]
    collect = next(
        task for task in tasks
        if task.get("name") == "Collect the KV keys used by the reconcile policy"
    )
    seed_paths = next(
        task for task in tasks
        if task.get("name") == "Add the generated seed paths used by the reconcile policy"
    )
    rotation_paths = next(
        task for task in tasks
        if task.get("name")
        == "Add the rotation-exempt mount and path components used by the reconcile policy"
    )
    guard_name = "Assert reconcile KV grant keys are literal path components"
    write_name = "Sync the reconcile policy from the declared set (policy-sync)"

    collection = collect["ansible.builtin.set_fact"]["openbao_reconcile_kv_policy_keys"]
    for variable in (
        "openbao_promoted_app_secrets",
        "openbao_promoted_external_secrets",
        "openbao_promoted_config_values",
        "openbao_seeded_generated_app_secrets",
        "openbao_roster_agent_generated_app_secrets",
        "openbao_caller_gateway_generated_app_secrets",
    ):
        assert variable in collection
    assert "openbao_generated_app_secret_paths" in str(
        seed_paths["ansible.builtin.set_fact"]
    )
    assert "openbao_rotation_exempt" in str(rotation_paths)
    assert names.index(guard_name) < names.index(write_name)


def test_dev_server_denies_unlisted_retention_value_and_allows_declared_value(
    rendered_defaults,
):
    binary = shutil.which("bao")
    assert binary, "the bao binary must be on PATH for the local dev-server ACL check"
    values, _approles, _policies = rendered_defaults
    mount = values["openbao_config_mount"]
    declared_max_versions = str(values["openbao_config_mount_max_versions"])
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [
            binary,
            "server",
            "-dev",
            "-dev-root-token-id=root",
            f"-dev-listen-address=127.0.0.1:{port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                if _request(base, "root", "GET", "sys/health")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(0.5)
        else:
            pytest.fail("the bao dev server did not become healthy")

        status, body = _request(
            base,
            "root",
            "POST",
            f"sys/mounts/{mount}",
            {"type": "kv", "options": {"version": "2"}},
        )
        assert status == 204, body

        policy = _render(RECONCILE, values)
        policy_name = values["openbao_reconcile_policy_name"]
        status, body = _request(
            base,
            "root",
            "PUT",
            f"sys/policies/acl/{policy_name}",
            {"policy": policy},
        )
        assert status == 204, body
        status, body = _request(
            base,
            "root",
            "POST",
            "auth/token/create",
            {"policies": [policy_name]},
        )
        assert status == 200, body
        token = json.loads(body)["auth"]["client_token"]

        path = f"{mount}/config"
        assert _request(base, token, "POST", path, {"max_versions": "1"})[0] == 403
        assert (
            _request(
                base,
                token,
                "POST",
                path,
                {"max_versions": declared_max_versions},
            )[0]
            == 204
        )
    finally:
        server.terminate()
        server.wait(timeout=30)
