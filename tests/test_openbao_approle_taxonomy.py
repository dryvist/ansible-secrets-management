"""Every declared OpenBao AppRole has one explicit trust class."""

from pathlib import Path
import re
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
CLASSES = {
    "operator-admin",
    "trusted-agent-read",
    "trusted-agent-write",
    "converge-automation",
    "service-runtime",
    "untrusted-sandbox",
}
ONE_USE_DIFY_APPROLES = {
    "agent-pr-keeper",
    "agent-github-clerk",
    "agent-merge-steward",
}


def _trust(value):
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, list):
        return [_trust(item) for item in value]
    if isinstance(value, dict):
        return {key: _trust(item) for key, item in value.items()}
    return value


def _render(expression, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = _trust(variables)
    return templar.template(trust_as_template(expression))


def _seconds(value):
    match = re.fullmatch(r"(\d+)(s|m|h|d)", str(value))
    if not match:
        raise AssertionError(f"not a finite duration: {value}")
    amount, unit = match.groups()
    return int(amount) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _dify_agent_names(defaults, suffix):
    return [
        value
        for name, value in defaults.items()
        if name.startswith("openbao_dify_agent_") and name.endswith(suffix)
    ]


class TestAppRoleTaxonomy(unittest.TestCase):
    def setUp(self):
        self.variables = {}
        for path in sorted((ROOT / "roles/openbao/defaults/main").glob("*.yml")):
            self.variables.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})

    def test_sessions_backup_has_a_standing_workstation_credential(self):
        variables = self.variables
        name = variables["openbao_ai_sessions_backup_approle_name"]
        roles = _render("{{ openbao_approles }}", variables)
        role = next(role for role in roles if role["name"] == name)
        ttls = _render("{{ openbao_approle_secret_id_ttl_overrides }}", variables)
        uses = variables["openbao_approle_secret_id_num_uses_overrides"]
        cidr_classes = _render("{{ openbao_approle_cidr_class_map }}", variables)

        self.assertEqual(role.get("secret_id_ttl", ttls.get(name)), "0s")
        self.assertEqual(role.get("secret_id_num_uses", uses.get(name)), 0)
        self.assertEqual(cidr_classes[name], "workstation")
        self.assertNotIn(name, _render("{{ openbao_secrets_domain_approle_names }}", variables))

    def test_every_declared_approle_has_one_identity_class(self):
        variables = self.variables
        variables["openbao_platform_env"] = {
            "OPENBAO_DIFY_AGENT_CIDR": "192.0.2.10/32",
        }
        variables["openbao_dify_secret_id_issuer_secret_id_cidr"] = "192.0.2.11/32"

        roles = _render("{{ openbao_approles }}", variables)
        class_map = _render("{{ openbao_approle_class_map }}", variables)
        cidr_class_map = _render("{{ openbao_approle_cidr_class_map }}", variables)
        secret_id_ttls = _render("{{ openbao_approle_secret_id_ttl_overrides }}", variables)
        unclassified = sorted({role["name"] for role in roles} - set(class_map))
        invalid_classes = {
            name: identity_class
            for name, identity_class in class_map.items()
            if identity_class not in CLASSES
        }

        self.assertEqual(unclassified, [])
        self.assertEqual(invalid_classes, {})
        for tool in ("agent", "zcode", "opencode", "cursor"):
            for tier in ("read", "write"):
                name = f"sandbox-{tool}-{tier}"
                self.assertEqual(class_map[name], "untrusted-sandbox")
                role = next(role for role in roles if role["name"] == name)
                self.assertEqual(role["policy"], name)
                self.assertEqual(role["secret_id_ttl"], "15m")
                self.assertEqual(role["secret_id_num_uses"], 1)
                self.assertEqual(role["token_ttl"], "15m")
                self.assertEqual(role["token_max_ttl"], "75m")
                self.assertFalse(role["manage_secret_id"])
        approle_names = _dify_agent_names(variables, "_approle_name")
        self.assertEqual(approle_names, _dify_agent_names(variables, "_policy_name"))
        self.assertEqual(
            [role["name"] for role in roles if role["name"] in approle_names],
            approle_names,
        )
        for name in approle_names:
            self.assertEqual(class_map[name], "service-runtime")
            role = next(role for role in roles if role["name"] == name)
            self.assertEqual(role["policy"], name)
            self.assertEqual(role["secret_id_bound_cidrs"], "192.0.2.10/32")
            self.assertEqual(role["secret_id_ttl"], "720h")
            self.assertEqual(
                role["secret_id_num_uses"],
                1 if name in ONE_USE_DIFY_APPROLES else 0,
            )
            self.assertEqual(role["token_ttl"], "15m")
            self.assertEqual(role["token_max_ttl"], "15m")
            self.assertFalse(role["manage_secret_id"])
        for reader in variables["openbao_app_agent_tier_readers"]:
            name = f"app-agent-{reader['tier']}"
            self.assertEqual(class_map[name], reader["trust_class"])
            role = next(role for role in roles if role["name"] == name)
            self.assertEqual(role["policy"], name)
            self.assertEqual(role["token_ttl"], "15m")
            self.assertEqual(role["token_max_ttl"], "15m")
            self.assertEqual(
                secret_id_ttls[name],
                variables["openbao_rotated_domain_secret_id_ttl"],
            )
        self.assertEqual(class_map["ai-orchestrator"], "trusted-agent-write")
        self.assertEqual(class_map["agent-workstation"], "trusted-agent-read")
        self.assertEqual(class_map["hatchet-eval-status"], "service-runtime")
        self.assertEqual(cidr_class_map["hatchet-eval-status"], "machine")
        for prefix, token_ttl, token_max_ttl in (
            ("openbao_github_ci_resolver", "15m", "60m"),
            ("openbao_openhands", "1h", "1h"),
        ):
            name = variables[f"{prefix}_approle_name"]
            role = next(role for role in roles if role["name"] == name)
            self.assertEqual(class_map[name], "service-runtime")
            self.assertEqual(role["policy"], variables[f"{prefix}_policy_name"])
            self.assertEqual(role["token_ttl"], token_ttl)
            self.assertEqual(role["token_max_ttl"], token_max_ttl)
            self.assertNotIn("secret_id_ttl", role)
            self.assertEqual(
                secret_id_ttls[name],
                variables["openbao_rotated_domain_secret_id_ttl"],
            )
            self.assertEqual(
                variables["openbao_approle_secret_id_num_uses_overrides"][name], 0
            )
            self.assertIn(
                name, _render("{{ openbao_secrets_domain_approle_names }}", variables)
            )
        router_key_name = variables["openbao_claude_code_router_key_approle_name"]
        router_key_role = next(role for role in roles if role["name"] == router_key_name)
        self.assertEqual(class_map[router_key_name], "service-runtime")
        self.assertEqual(cidr_class_map[router_key_name], "workstation")
        self.assertEqual(
            router_key_role["policy"],
            variables["openbao_claude_code_router_key_policy_name"],
        )
        self.assertEqual(router_key_role["secret_id_num_uses"], 100)
        self.assertEqual(
            secret_id_ttls[router_key_name],
            variables["openbao_rotated_domain_secret_id_ttl"],
        )
        for reader in variables["openbao_app_agent_tier_readers"]:
            self.assertEqual(
                cidr_class_map[f"app-agent-{reader['tier']}"], reader["cidr_class"]
            )

    def test_sandbox_approles_outlive_the_job_guard(self):
        variables = self.variables
        roles = _render("{{ openbao_sandbox_agent_approles }}", variables)
        minimum = _seconds("75m")

        self.assertGreater(len(roles), 0)
        for role in roles:
            self.assertGreaterEqual(_seconds(role["token_max_ttl"]), minimum)
            self.assertEqual(role["secret_id_num_uses"], 1)
            self.assertFalse(role["manage_secret_id"])


if __name__ == "__main__":
    unittest.main()
