"""The open-llm raw mint grant is enforced by a real OpenBao ACL, not only rendered.

The rendered policy is loaded into `bao server -dev` with a plain kv mount at the
agents mount path. The ACL decides before any backend runs, so an allowed request
reaches the stub and returns 204 while a refused one returns 403. This pins the
facts the policy comments rely on: a permissions map matches as a whole, a string
installation_id matches, and an omitted or wider map is refused.

Run with a bao binary on PATH, for example:
    nix shell --inputs-from . nixpkgs#openbao --command python3 -m pytest <this file>
"""

import json
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest

from test_openbao_router_key_catalog import _render_open_llm_policy

INSTALLATION = "4242"
WRITE = {"contents": "write", "pull_requests": "write"}
READ = {"contents": "read"}


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _call(base, token, method, path, body=None):
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


@pytest.fixture(scope="module")
def minter():
    binary = shutil.which("bao")
    assert binary, "the bao binary must be on PATH: this test runs a real OpenBao dev server"
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [binary, "server", "-dev", "-dev-root-token-id=root", f"-dev-listen-address=127.0.0.1:{port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                if _call(base, "root", "GET", "sys/health")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(0.5)
        else:
            pytest.fail("the bao dev server did not become healthy")
        _call(base, "root", "POST", "sys/mounts/github", {"type": "kv", "options": {"version": "1"}})
        policy = _render_open_llm_policy(INSTALLATION)
        status, _ = _call(base, "root", "PUT", "sys/policies/acl/open-llm", {"policy": policy})
        assert status == 204
        status, body = _call(base, "root", "POST", "auth/token/create", {"policies": ["open-llm"]})
        assert status == 200
        token = json.loads(body)["auth"]["client_token"]
        yield lambda payload: _call(base, token, "POST", "github/token", payload)[0]
    finally:
        server.terminate()
        server.wait(timeout=30)


def _request(**overrides):
    payload = {"installation_id": INSTALLATION, "repositories": "repo", "permissions": WRITE}
    payload.update(overrides)
    return {key: value for key, value in payload.items() if value is not None}


@pytest.mark.parametrize(
    "payload",
    [_request(), _request(permissions=READ)],
    ids=["write-map", "read-map"],
)
def test_the_two_dispatcher_permission_maps_are_allowed(minter, payload):
    assert minter(payload) == 204


@pytest.mark.parametrize(
    "payload",
    [
        _request(permissions={**WRITE, "administration": "write"}),
        _request(permissions={"contents": "write"}),
        _request(permissions={"contents": "admin"}),
        _request(permissions={**READ, "pull_requests": "write"}),
        _request(permissions={}),
        _request(permissions=None),
        _request(installation_id="9999"),
        _request(repositories=None),
        _request(extra="value"),
    ],
    ids=[
        "wider-than-write",
        "contents-write-only",
        "contents-admin",
        "read-plus-pull-requests",
        "empty-permissions",
        "permissions-omitted",
        "other-installation",
        "repositories-omitted",
        "unlisted-parameter",
    ],
)
def test_every_other_request_is_refused(minter, payload):
    assert minter(payload) == 403
