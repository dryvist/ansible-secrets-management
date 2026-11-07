"""The development server enforces KV config and metadata bounds."""

from openbao_reconcile_bounds_helpers import (
    _render, _templar, _trust, rendered_defaults, RECONCILE
)
from _ports import loopback_port
import json
import os
import pytest
import shutil
import subprocess
import time
import urllib.error
import urllib.request

def _request(base, token, method, path, body=None):
    headers = {"X-Vault-Token": token}
    if body is not None:
        headers["Content-Type"] = (
            "application/merge-patch+json" if method == "PATCH" else "application/json"
        )
    request = urllib.request.Request(
        f"{base}/v1/{path}",
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()

@pytest.mark.parametrize(
    "rendered_defaults", [{"agents": {"docs-updater": {}}}], indirect=True,
)
def test_dev_server_enforces_config_and_metadata_parameter_bounds(
    rendered_defaults,
):
    binary = shutil.which("bao")
    assert binary, "the bao binary must be on PATH for the local dev-server ACL check"
    values, _approles, _policies = rendered_defaults
    mount = values["openbao_config_mount"]
    declared_max_versions = str(values["openbao_config_mount_max_versions"])
    port = loopback_port()
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [
            binary,
            "server",
            "-dev",
            "-dev-root-token-id=root",
            "-dev-no-store-token",
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

        status, body = _request(
            base, "root", "POST", "sys/auth/approle", {"type": "approle"},
        )
        assert status == 204, body
        role_path = "auth/approle/role/docs-updater"
        status, body = _request(
            base, "root", "POST", role_path,
            {"token_policies": ["docs-updater", "other"]},
        )
        assert status == 204, body
        # Both the root and field write rules retain their required parameters.
        assert _request(base, token, "GET", role_path)[0] == 403
        assert _request(base, token, "GET", f"{role_path}/policies")[0] == 403
        read = subprocess.run(
            [binary, "read", "-format=json", f"{role_path}/policies",
             "token_policies=docs-updater"],
            env={**os.environ, "BAO_ADDR": base, "BAO_TOKEN": token},
            capture_output=True, text=True, check=False,
        )
        assert read.returncode == 0, read.stderr
        assert json.loads(read.stdout)["data"]["token_policies"] == ["docs-updater", "other"]
        for forbidden in ("other", "docs-updater,other"):
            assert _request(
                base, token, "POST", f"{role_path}/policies",
                {"token_policies": forbidden},
            )[0] == 403
        assert _request(
            base, token, "POST", f"{role_path}/policies",
            {"token_policies": "docs-updater"},
        )[0] == 204

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

        rotation_exempt = _templar(_trust(values)).template(
            _trust(values["openbao_rotation_exempt"])
        )
        metadata_mount, metadata_key = rotation_exempt[0].split(":", 1)
        metadata_path = f"{metadata_mount}/metadata/{metadata_key}"
        status, body = _request(
            base,
            "root",
            "POST",
            f"{metadata_mount}/data/{metadata_key}",
            {"data": {"fixture": "value"}},
        )
        assert status in (200, 204), body

        for forbidden in (
            {"max_versions": 3},
            {"delete_version_after": "24h"},
        ):
            status, body = _request(
                base, token, "PATCH", metadata_path, forbidden
            )
            assert status == 403, (forbidden, status, body)

        status, body = _request(
            base,
            token,
            "PATCH",
            metadata_path,
            {"custom_metadata": {"fixture": "allowed"}},
        )
        assert status in (200, 204), body
    finally:
        server.terminate()
        server.wait(timeout=30)
