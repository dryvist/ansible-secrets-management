"""Render every declared policy and ask OpenBao who reaches the kill-test power token.

The leaf sits outside secret/apps/* so no standing AI reader covers it. Each
rendered policy is written to a real OpenBao dev server, and sys/capabilities
answers for a token holding only that policy, so the server's own ACL
evaluator decides reach. The holder sets on the data and metadata leaves are
exact, as is the set of AppRoles that inherit a data holder.
"""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import unittest
from unittest import mock
import urllib.error
import urllib.request

from ansible.parsing.dataloader import DataLoader
from ansible.plugins.loader import init_plugin_loader
from ansible.template import Templar, trust_as_template
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/openbao"
DATA, METADATA = "secret/data/killtest/hatchet", "secret/metadata/killtest/hatchet"
# The dedicated reader, its publisher, and the human-gated or reconcile identities.
DATA_HOLDERS = {
    "hatchet-killtest": ["read"],
    "ansible-converge": ["create", "read", "update"],
    "operator-human": ["list", "read"],
    "openbao-reconcile": ["create", "list", "read", "update"],
    "ai-admin": ["create", "delete", "list", "patch", "read", "update"],
}
# Metadata holds no value; secret-age-audit reads only its timestamps.
METADATA_HOLDERS = {
    "ansible-converge": ["read"],
    "operator-human": ["list", "read"],
    "openbao-reconcile": ["list", "patch", "read"],
    "ai-admin": ["create", "delete", "list", "patch", "read", "update"],
    "secret-age-audit": ["list", "read"],
}
# ai-admin-session and admin carry ai-admin (07f) as accepted break-glass; semaphore,
# ansible-converge-writer and openbao-policy-sync carry ansible-converge or
# openbao-reconcile.
DATA_HOLDER_APPROLES = {
    "hatchet-killtest", "ansible-converge", "openbao-reconcile", "ai-admin",
    "ai-admin-session", "admin", "semaphore", "ansible-converge-writer",
    "openbao-policy-sync",
}

# Values the role reads from the process environment and refuses when empty.
REQUIRED_ENV = {name: "fixture" for name in (
    "OPENBAO_AI_API_KEY_MOUNT", "OPENBAO_AI_API_KEY_PATH_PREFIX",
    "OPENBAO_APPROLE_SNAPSHOT_ROLE_ID", "OPENBAO_APPROLE_SNAPSHOT_SECRET_ID",
    "OPENBAO_TERRAKUBE_AWS_WORKSPACE", "OPENBAO_TERRAKUBE_NETWORK_WORKSPACE")}


class _PlatformEnv(dict):
    """Inventory env values: a placeholder for every key, so every policy renders."""

    def __missing__(self, key):
        return "192.0.2.10/32" if "CIDR" in key else "1"

    def get(self, key, _default=None):
        return self[key]


def _trust(value):
    if isinstance(value, _PlatformEnv):
        return value
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, list):
        return [_trust(item) for item in value]
    if isinstance(value, dict):
        return {key: _trust(item) for key, item in value.items()}
    return value


def _templar(variables):
    loader = DataLoader()
    # Templates resolve {% include %} from templates/, as the role's lookup does.
    loader.set_basedir(str(ROLE / "templates"))
    templar = Templar(loader=loader)
    templar.available_variables = _trust(variables)
    return templar


def role_defaults():
    """Every role default plus the placeholder inventory a full render needs."""
    init_plugin_loader()
    variables = {"ansible_managed": "Ansible managed"}
    for path in sorted((ROLE / "defaults/main").glob("*.yml")):
        variables.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    variables["openbao_platform_env"] = _PlatformEnv()
    # A runtime fact; its entries render as apps/<name>, never killtest/.
    variables["llm_router_key_catalog_facts"] = {"openbao_router_key_catalog": {}}
    return variables


def render(variables, expression):
    return _templar(variables).template(trust_as_template(expression))


def _call(base, token, method, path, body=None):
    request = urllib.request.Request(
        f"{base}/v1/{path}", method=method, headers={"X-Vault-Token": token},
        data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def _dev_server():
    binary = shutil.which("bao")
    assert binary, "the bao binary must be on PATH: this test runs a real OpenBao dev server"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [binary, "server", "-dev", "-dev-root-token-id=root", f"-dev-listen-address=127.0.0.1:{port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            if _call(base, "root", "GET", "sys/health")[0] == 200:
                return server, base
        except OSError:
            pass
        time.sleep(0.5)
    server.terminate()
    raise AssertionError("the bao dev server did not become healthy")


class HatchetKillTestPolicyReach(unittest.TestCase):
    maxDiff = None

    @classmethod
    @mock.patch.dict(os.environ, REQUIRED_ENV)
    def setUpClass(cls):
        cls.variables = role_defaults()
        cls.approles = render(cls.variables, "{{ openbao_approles }}")
        policies = render(cls.variables, "{{ openbao_policies }}")
        cls.rendered, cls.failed = {}, {}
        for policy in policies:
            source = (ROLE / "templates" / policy["template"]).read_text(encoding="utf-8")
            try:
                cls.rendered[policy["name"]] = render({**cls.variables, "item": policy}, source)
            except Exception as error:  # noqa: BLE001 - every unrendered policy is reported
                cls.failed[policy["name"]] = str(error).splitlines()[0]
        server, base = _dev_server()
        try:
            cls.caps, cls.rejected = {}, {}
            for name, text in cls.rendered.items():
                status, body = _call(base, "root", "PUT", f"sys/policies/acl/{name}", {"policy": text})
                if status != 204:
                    cls.rejected[name] = body
                    continue
                status, body = _call(base, "root", "POST", "auth/token/create",
                                     {"policies": [name], "no_default_policy": True})
                assert status == 200, (name, body)
                status, body = _call(base, "root", "POST", "sys/capabilities", {
                    "token": body["auth"]["client_token"], "paths": [DATA, METADATA]})
                assert status == 200, (name, body)
                cls.caps[name] = {path: sorted(body[path]) for path in (DATA, METADATA)}
        finally:
            server.terminate()
            server.wait(timeout=30)

    def _holders(self, path):
        return {name: caps[path] for name, caps in self.caps.items() if caps[path] != ["deny"]}

    def test_every_policy_renders_and_loads(self):
        self.assertEqual(self.failed, {})
        self.assertEqual(self.rejected, {})
        self.assertGreater(len(self.caps), 50)

    def test_the_data_leaf_holders_are_exact(self):
        self.assertEqual(self._holders(DATA), DATA_HOLDERS)

    def test_the_metadata_leaf_holders_are_exact(self):
        self.assertEqual(self._holders(METADATA), METADATA_HOLDERS)

    def test_the_approles_inheriting_a_data_holder_are_exact(self):
        inheriting = {
            role["name"] for role in self.approles
            if set(role.get("token_policies") or [role.get("policy")]) & set(DATA_HOLDERS)
        }
        self.assertEqual(inheriting, DATA_HOLDER_APPROLES)


if __name__ == "__main__":
    unittest.main()
