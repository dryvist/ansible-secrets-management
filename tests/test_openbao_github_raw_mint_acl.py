"""Owner-neutral raw token grants are constrained by real OpenBao ACLs."""

import json
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "roles" / "openbao" / "templates"
DEFAULTS = yaml.safe_load(
    (ROOT / "roles" / "openbao" / "defaults" / "main" / "03-github-engine.yml")
    .read_text(encoding="utf-8")
)
READ = DEFAULTS["openbao_github_read_permissions"]
REPO_CREATE = DEFAULTS["openbao_github_repo_create_permissions"]
WRITE = {"contents": "write", "pull_requests": "write"}
POLICIES = {
    "github-read": "github-read-policy.hcl.j2",
    "github-mint": "github-mint-policy.hcl.j2",
    "github-write": "github-write-policy.hcl.j2",
    "github-repo-create": "github-repo-create-policy.hcl.j2",
    "github-admin": "github-admin-policy.hcl.j2",
}
LEGACY_SETS = [
    {"mount": "github", "name": "read-legacy-a-all", "tier": "read"},
    {"mount": "github", "name": "read-legacy-b-all", "tier": "read"},
    {"mount": "github-admin", "name": "repo-create-legacy", "tier": "repo-create"},
    {"mount": "github-admin", "name": "full-automation-legacy", "tier": "admin"},
]


def _render_policies():
    environment = Environment(loader=FileSystemLoader(TEMPLATES))
    environment.filters["comment"] = lambda value: "# " + str(value)
    values = {
        "ansible_managed": "managed",
        "openbao_github_mount": "github-admin",
        "openbao_github_everyday_mount": "github",
        "openbao_kv_mount": "secret",
        "openbao_github_permission_sets": LEGACY_SETS,
        "openbao_github_read_permissions": READ,
        "openbao_github_repo_create_permissions": REPO_CREATE,
    }
    return {
        policy: environment.get_template(template).render(**values)
        for policy, template in POLICIES.items()
    }


def _stanzas(policy):
    return {
        path: body
        for path, body in re.findall(r'(?ms)^path "([^"]+)" \{\n(.*?)^\}', policy)
    }


def _raw(policy, path):
    return _stanzas(policy)[path]


def _hcl_map(values):
    fields = ", ".join(f'"{key}" = "{value}"' for key, value in sorted(values.items()))
    return f'"permissions" = [{{ {fields} }}]'


def _assert_installation_id_denied(stanza):
    assert re.search(
        r'denied_parameters\s*=\s*\{\s*"installation_id"\s*=\s*\[\s*\]\s*\}',
        stanza,
    )
    assert '"installation_id"' not in stanza.split("denied_parameters", 1)[0]


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

        for mount in ("github", "github-admin"):
            status, body = _call(
                base,
                "root",
                "POST",
                f"sys/mounts/{mount}",
                {"type": "kv", "options": {"version": "1"}},
            )
            assert status == 204, body

        policies = _render_policies()
        tokens = {}
        for name, policy in policies.items():
            status, body = _call(
                base,
                "root",
                "PUT",
                f"sys/policies/acl/{name}",
                {"policy": policy},
            )
            assert status == 204, (name, body)
            status, body = _call(
                base,
                "root",
                "POST",
                "auth/token/create",
                {"policies": [name]},
            )
            assert status == 200, (name, body)
            tokens[name] = json.loads(body)["auth"]["client_token"]

        yield lambda policy, method, path, body=None: _call(
            base, tokens[policy], method, path, body
        )
    finally:
        server.terminate()
        server.wait(timeout=30)


def test_rendered_raw_grants_are_owner_neutral_and_parameter_pinned():
    policies = _render_policies()
    for name in ("github-read", "github-mint"):
        stanza = _raw(policies[name], "github/token")
        _assert_installation_id_denied(stanza)
        assert _hcl_map(READ) in stanza
        assert '"org_name" = []' in stanza
        assert '"repositories" = []' in stanza

    repo_create = _raw(policies["github-repo-create"], "github-admin/token")
    _assert_installation_id_denied(repo_create)
    assert _hcl_map(REPO_CREATE) in repo_create
    assert '"org_name" = []' in repo_create
    assert '"repositories" = []' in repo_create

    full_automation = _raw(policies["github-admin"], "github-admin/token")
    _assert_installation_id_denied(full_automation)
    assert 'required_parameters = ["org_name"]' in full_automation
    assert '"org_name" = []' in full_automation
    assert '"repositories" = []' in full_automation
    assert '"permissions"' not in full_automation

    # The write grant keeps installation_id until the legacy helper is removed.
    write = _raw(policies["github-write"], "github/token")
    assert 'required_parameters = ["repositories"]' in write
    assert '"installation_id" = []' in write
    assert '"org_name" = []' in write
    assert 'denied_parameters' not in write

    for policy, raw_path in (
        ("github-read", "github/token"),
        ("github-mint", "github/token"),
        ("github-write", "github/token"),
        ("github-repo-create", "github-admin/token"),
        ("github-admin", "github-admin/token"),
    ):
        stanza = _raw(policies[policy], raw_path)
        assert not any(item["name"] in stanza for item in LEGACY_SETS)


@pytest.mark.parametrize("policy", ["github-read", "github-mint"])
def test_read_grants_allow_only_the_fixed_map_with_any_owner(minter, policy):
    for payload in (
        {"org_name": "org-a", "permissions": READ},
        {"org_name": "org-b", "repositories": "repo", "permissions": READ},
    ):
        assert minter(policy, "POST", "github/token", payload)[0] == 204

    denied = (
        {"org_name": "org-c", "permissions": {**READ, "contents": "write"}},
        {"org_name": "org-c"},
        {"org_name": "org-c", "permissions": READ, "installation_id": "4242"},
    )
    for payload in denied:
        assert minter(policy, "POST", "github/token", payload)[0] == 403


def test_write_grant_preserves_legacy_and_owner_neutral_requests(minter):
    assert minter(
        "github-write",
        "POST",
        "github/token",
        {"installation_id": "4242", "repositories": "repo", "permissions": WRITE},
    )[0] == 204
    assert minter(
        "github-write",
        "POST",
        "github/token",
        {"org_name": "org-a", "repositories": "repo"},
    )[0] == 204
    assert minter(
        "github-write",
        "POST",
        "github/token",
        {"org_name": "org-b", "repositories": "repo", "permissions": WRITE},
    )[0] == 204
    assert minter(
        "github-write",
        "POST",
        "github/token",
        {"org_name": "org-a", "repositories": "repo", "extra": "value"},
    )[0] == 403


def test_repo_create_grant_pins_administration_map(minter):
    for payload in (
        {"org_name": "org-a", "permissions": REPO_CREATE},
        {"org_name": "org-b", "repositories": "repo", "permissions": REPO_CREATE},
    ):
        assert minter("github-repo-create", "POST", "github-admin/token", payload)[0] == 204
    denied = (
        {"org_name": "org-a", "permissions": {"administration": "read"}},
        {"org_name": "org-a"},
        {"org_name": "org-a", "permissions": REPO_CREATE, "installation_id": "4242"},
    )
    for payload in denied:
        assert minter("github-repo-create", "POST", "github-admin/token", payload)[0] == 403


def test_full_automation_uses_app_ceiling_and_rejects_permissions(minter):
    for payload in (
        {"org_name": "org-a"},
        {"org_name": "org-b", "repositories": "repo"},
    ):
        assert minter("github-admin", "POST", "github-admin/token", payload)[0] == 204
    assert minter(
        "github-admin",
        "POST",
        "github-admin/token",
        {"org_name": "org-a", "permissions": {"contents": "read"}},
    )[0] == 403
    assert minter(
        "github-admin",
        "POST",
        "github-admin/token",
        {"org_name": "org-a", "installation_id": "4242"},
    )[0] == 403
