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
from _ports import loopback_port
from test_openbao_global_read_all_policy import _environment as policy_environment

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/openbao"
DATA, METADATA = "secret/data/killtest/hatchet", "secret/metadata/killtest/hatchet"
PARENT_METADATA = "secret/metadata/killtest/"
RUSTFS_DATA, RUSTFS_METADATA = "secret/data/infra/rustfs", "secret/metadata/infra/rustfs"
FAN_CONTROL_DATA = "secret/data/apps/fan-control-write"
FAN_CONTROL_METADATA = "secret/metadata/apps/fan-control-write"
APPS_PARENT_METADATA = "secret/metadata/apps/"
# The dedicated reader, its publisher (converge), and the human-gated identities.
# openbao-reconcile is absent: no reconcile task seeds this leaf, so it holds no grant.
DATA_HOLDERS = {
    "hatchet-killtest": ["read"],
    "ansible-converge": ["create", "read", "update"],
    "operator-human": ["read"],
    "ai-admin": ["create", "delete", "list", "patch", "read", "update"],
}
# Metadata holds no value; secret-age-audit reads only its timestamps.
METADATA_HOLDERS = {
    "ansible-converge": ["read"],
    "operator-human": ["list", "read"],
    "ai-admin": ["create", "delete", "list", "patch", "read", "update"],
    "secret-age-audit": ["list", "read"],
}
# ai-admin-session and admin carry ai-admin (07f) as accepted break-glass; semaphore and
# ansible-converge-writer carry ansible-converge.
DATA_HOLDER_APPROLES = {
    "hatchet-killtest", "ansible-converge", "ai-admin",
    "ai-admin-session", "admin", "semaphore", "ansible-converge-writer",
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
    loader.set_basedir(str(ROLE))
    templar = Templar(loader=loader)
    templar.environment.loader = policy_environment().loader
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


def _read_with_policies(base, policies, path):
    status, body = _call(
        base,
        "root",
        "POST",
        "auth/token/create",
        {"policies": policies, "no_default_policy": True},
    )
    assert status == 200, (policies, body)
    return _call(base, body["auth"]["client_token"], "GET", path)


def _dev_server():
    binary = shutil.which("bao")
    assert binary, "the bao binary must be on PATH: this test runs a real OpenBao dev server"
    port = loopback_port()
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


@mock.patch.dict(os.environ, REQUIRED_ENV)
def reach(paths, approle_names=()):
    """Render every policy and ask OpenBao's dev server about `paths`."""
    variables = role_defaults()
    result = {"approles": render(variables, "{{ openbao_approles }}"), "failed": {}, "rejected": {}, "caps": {}}
    rendered = {}
    for policy in render(variables, "{{ openbao_policies }}"):
        source = (ROLE / "templates" / policy["template"]).read_text(encoding="utf-8")
        try:
            rendered[policy["name"]] = render({**variables, "item": policy}, source)
        except Exception as error:  # noqa: BLE001 - every unrendered policy is reported
            result["failed"][policy["name"]] = str(error).splitlines()[0]
    server, base = _dev_server()
    try:
        status, body = _call(
            base,
            "root",
            "PUT",
            DATA,
            {"data": {"value": "dev-server fixture"}},
        )
        assert status == 200, body
        if FAN_CONTROL_DATA in paths:
            status, body = _call(
                base,
                "root",
                "PUT",
                FAN_CONTROL_DATA,
                {"data": {"value": "fan-control fixture"}},
            )
            assert status == 200, body
        for name, text in rendered.items():
            status, body = _call(base, "root", "PUT", f"sys/policies/acl/{name}", {"policy": text})
            if status != 204:
                result["rejected"][name] = body
                continue
            status, body = _call(base, "root", "POST", "auth/token/create",
                                 {"policies": [name], "no_default_policy": True})
            assert status == 200, (name, body)
            status, body = _call(base, "root", "POST", "sys/capabilities", {
                "token": body["auth"]["client_token"], "paths": list(paths)})
            assert status == 200, (name, body)
            result["caps"][name] = {path: sorted(body[path]) for path in paths}
        ai_read_policies = render(variables, "{{ openbao_ai_trusted_read_all_policies }}")
        result["reads"] = {
            "ai_global_read_plus_read_all": _read_with_policies(
                base, ai_read_policies, DATA
            ),
            "operator_human": _read_with_policies(
                base, [variables["openbao_operator_human_policy_name"]], DATA
            ),
        }
        role_by_name = {role["name"]: role for role in result["approles"]}
        result["approle_reads"] = {}
        for name in approle_names:
            role = role_by_name[name]
            policies = role.get("token_policies") or [role["policy"]]
            if isinstance(policies, str):
                policies = [policies]
            result["approle_reads"][name] = _read_with_policies(
                base, policies, FAN_CONTROL_DATA
            )
    finally:
        server.terminate()
        server.wait(timeout=30)
    return result


def holders(caps, path):
    return {name: held[path] for name, held in caps.items() if held[path] != ["deny"]}


def carriers(approles, policies):
    return {role["name"] for role in approles
            if set(role.get("token_policies") or [role.get("policy")]) & set(policies)}


class HatchetKillTestPolicyReach(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        found = reach(
            [
                DATA,
                METADATA,
                PARENT_METADATA,
                RUSTFS_DATA,
                RUSTFS_METADATA,
                FAN_CONTROL_DATA,
                FAN_CONTROL_METADATA,
                APPS_PARENT_METADATA,
            ],
            approle_names=("ai-readonly", "ai-elevated"),
        )
        cls.approles, cls.failed, cls.rejected, cls.caps = (
            found["approles"], found["failed"], found["rejected"], found["caps"])
        cls.reads = found["reads"]
        cls.approle_reads = found["approle_reads"]

    def _holders(self, path):
        return holders(self.caps, path)

    def test_every_policy_renders_and_loads(self):
        self.assertEqual(self.failed, {})
        self.assertEqual(self.rejected, {})
        self.assertGreater(len(self.caps), 50)

    def test_the_data_leaf_holders_are_exact(self):
        self.assertEqual(self._holders(DATA), DATA_HOLDERS)

    def test_the_metadata_leaf_holders_are_exact(self):
        self.assertEqual(self._holders(METADATA), METADATA_HOLDERS)

    def test_the_approles_inheriting_a_data_holder_are_exact(self):
        self.assertEqual(carriers(self.approles, DATA_HOLDERS), DATA_HOLDER_APPROLES)

    def test_ai_global_read_plus_read_all_cannot_read_the_killtest_leaf(self):
        status, body = self.reads["ai_global_read_plus_read_all"]
        self.assertEqual(status, 403)
        self.assertIn(b"permission denied", body.lower())

    def test_operator_human_can_read_the_killtest_leaf(self):
        status, body = self.reads["operator_human"]
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["data"]["value"], "dev-server fixture")

    def test_ai_global_read_cannot_list_parent_but_operator_human_can(self):
        self.assertEqual(self.caps["ai-global-read"][PARENT_METADATA], ["deny"])
        self.assertIn("list", self.caps["operator-human"][PARENT_METADATA])

    def test_actuating_leaves_are_denied_to_ai_global_read_and_readable_by_operator(self):
        for data_path, metadata_path in (
            (DATA, METADATA),
            (RUSTFS_DATA, RUSTFS_METADATA),
            (FAN_CONTROL_DATA, FAN_CONTROL_METADATA),
        ):
            with self.subTest(data_path=data_path):
                for path in (data_path, metadata_path):
                    self.assertEqual(self.caps["ai-global-read"][path], ["deny"])
                    self.assertIn("read", self.caps["operator-human"][path])

    def test_ai_read_roles_cannot_read_fan_control(self):
        for name in ("ai-readonly", "ai-elevated"):
            with self.subTest(approle=name):
                status, body = self.approle_reads[name]
                self.assertEqual(status, 403)
                self.assertIn(b"permission denied", body.lower())

    def test_ai_sessions_backup_still_cannot_read_the_rustfs_admin_leaf(self):
        self.assertEqual(self.caps["ai-sessions-backup"][RUSTFS_DATA], ["deny"])
        self.assertEqual(self.caps["ai-sessions-backup"][RUSTFS_METADATA], ["deny"])

    def test_ai_global_read_can_still_list_the_shared_apps_parent(self):
        self.assertNotEqual(
            self.caps["ai-global-read"][APPS_PARENT_METADATA], ["deny"]
        )
        self.assertIn("list", self.caps["ai-global-read"][APPS_PARENT_METADATA])


if __name__ == "__main__":
    unittest.main()
