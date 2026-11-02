"""Render every declared policy and list who reaches the kill-test power token.

The leaf sits outside secret/apps/* so no standing AI reader covers it. This
matches each rendered `path` stanza against the leaf with OpenBao's own glob
rules (a trailing `*` is a prefix match, `+` is one path segment) and requires
that only the allowlisted policies hold any non-deny capability on it.
"""

import os
from pathlib import Path
import re
import unittest
from unittest import mock

from ansible.parsing.dataloader import DataLoader
from ansible.plugins.loader import init_plugin_loader
from ansible.template import Templar, trust_as_template
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/openbao"
STANZA = re.compile(r'path\s+"([^"]+)"\s*\{(.*?)\n\}', re.DOTALL)
CAPABILITIES = re.compile(r'capabilities\s*=\s*\[([^]]*)\]')
LEAVES = ("secret/data/killtest/hatchet", "secret/metadata/killtest/hatchet")
# The dedicated reader, its publisher, and the human-gated or reconcile identities.
ALLOWED = {
    "hatchet-killtest",
    "ansible-converge",
    "operator-human",
    "openbao-reconcile",
    "ai-admin",
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
    templar.available_variables = _trust(variables)
    return templar


def _matches(pattern, path):
    expression = re.escape(pattern).replace(r"\+", "[^/]+")
    if expression.endswith(r"\*"):
        return re.fullmatch(expression[:-2] + ".*", path) is not None
    return re.fullmatch(expression, path) is not None


def _reach(policy_text, path):
    caps = set()
    for pattern, body in STANZA.findall(policy_text):
        if _matches(pattern, path):
            found = CAPABILITIES.search(body)
            caps |= set(re.findall(r'"([^"]+)"', found.group(1))) if found else set()
    return caps - {"deny"} if "deny" not in caps else set()


class HatchetKillTestPolicyReach(unittest.TestCase):
    maxDiff = None

    @classmethod
    @mock.patch.dict(os.environ, REQUIRED_ENV)
    def setUpClass(cls):
        init_plugin_loader()
        variables = {"ansible_managed": "Ansible managed"}
        for path in sorted((ROLE / "defaults/main").glob("*.yml")):
            variables.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        variables["openbao_platform_env"] = _PlatformEnv()
        # A runtime fact; its entries render as apps/<name>, never killtest/.
        variables["llm_router_key_catalog_facts"] = {"openbao_router_key_catalog": {}}
        policies = _templar(variables).template(trust_as_template("{{ openbao_policies }}"))
        cls.rendered, cls.failed = {}, {}
        for policy in policies:
            source = (ROLE / "templates" / policy["template"]).read_text(encoding="utf-8")
            try:
                cls.rendered[policy["name"]] = _templar({**variables, "item": policy}).template(
                    trust_as_template(source))
            except Exception as error:  # noqa: BLE001 - every unrendered policy is reported
                cls.failed[policy["name"]] = str(error).splitlines()[0]

    def test_every_policy_renders(self):
        self.assertEqual(self.failed, {})
        self.assertGreater(len(self.rendered), 50)

    def test_only_allowlisted_policies_reach_the_killtest_leaf(self):
        holders = {name for name, text in self.rendered.items() if _reach(text, LEAVES[0])}
        self.assertEqual(holders - ALLOWED, set())
        # Metadata holds no value; a read/list auditor there is fine, a writer is not.
        metadata_writers = {
            name for name, text in self.rendered.items()
            if _reach(text, LEAVES[1]) - {"read", "list"}
        }
        self.assertEqual(metadata_writers - ALLOWED, set())
        self.assertIn("hatchet-killtest", holders)
        self.assertEqual(_reach(self.rendered["hatchet-killtest"], LEAVES[0]), {"read"})
        self.assertEqual(_reach(self.rendered["ansible-converge"], LEAVES[0]),
                         {"create", "update", "read"})

    def test_the_glob_rules_match_openbao(self):
        self.assertTrue(_matches("secret/*", LEAVES[0]))
        self.assertTrue(_matches("secret/data/+/hatchet", LEAVES[0]))
        self.assertTrue(_matches("*", LEAVES[0]))
        self.assertFalse(_matches("secret/data/apps/*", LEAVES[0]))
        self.assertFalse(_matches("secret/data/killtest", LEAVES[0]))
        self.assertEqual(_reach('path "secret/*" {\n  capabilities = ["deny"]\n}', LEAVES[0]), set())


if __name__ == "__main__":
    unittest.main()
