"""The Hatchet power-token reader stays path-exact and issuer-minted."""

from pathlib import Path
import re
import unittest

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
TEMPLATES = ROOT / "roles/openbao/templates"
POLICY_NAME = "{{ openbao_hatchet_killtest_policy_name }}"
APPROLE_NAME = "{{ openbao_hatchet_killtest_approle_name }}"
POLICY_GRANT = re.compile(
    r'path\s+"([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]*)\]\s*\}',
    re.DOTALL,
)


def _yaml(name):
    return yaml.safe_load((DEFAULTS / name).read_text(encoding="utf-8"))


def _render(source, values):
    templar = Templar(loader=DataLoader())
    templar.available_variables = values
    return templar.template(trust_as_template(source))


def _grants(source):
    return [
        (match.group(1), tuple(re.findall(r'"([^"]+)"', match.group(2))))
        for match in POLICY_GRANT.finditer(source)
    ]


def _duration_seconds(value):
    match = re.fullmatch(r"([1-9][0-9]*)([smhd])", str(value))
    if match is None:
        return 0
    return int(match.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]


class HatchetKillTestReaderContract(unittest.TestCase):
    def setUp(self):
        self.names = _yaml("05h-cribl-edge-readers.yml")
        self.policy_rows = _yaml("07c-base-policies.yml")["openbao_base_policies_static"]
        self.roles = _yaml("07f-elevated-approles.yml")["openbao_base_approles_elevated"]
        self.reader = next(role for role in self.roles if role.get("name") == APPROLE_NAME)
        self.policy_row = next(row for row in self.policy_rows if row.get("name") == POLICY_NAME)

    def test_policy_renders_read_on_the_single_killtest_data_leaf(self):
        template = (TEMPLATES / "cribl-edge-reader-policy.hcl.j2").read_text(encoding="utf-8")
        path = _render(self.policy_row["path"], self.names)
        policy = _render(
            template,
            {"ansible_managed": "Ansible managed", "openbao_kv_mount": "secret",
             "item": {"path": path}},
        )

        self.assertEqual(_grants(policy), [("secret/data/killtest/hatchet", ("read",))])
        self.assertNotIn("*", policy)
        self.assertEqual(self.policy_row["template"], "cribl-edge-reader-policy.hcl.j2")
        self.assertNotIn("bucket", self.policy_row)
        # Existing rows keep their apps/<bucket> leaf.
        legacy = _render(template, {"ansible_managed": "", "openbao_kv_mount": "secret",
                                    "item": {"bucket": "cribl-edge-macbook"}})
        self.assertEqual(_grants(legacy), [("secret/data/apps/cribl-edge-macbook", ("read",))])

    def test_publisher_gets_only_the_declared_create_read_update_leaf(self):
        # The rendered grant itself is pinned in test_openbao_hatchet_killtest_policy_reach.py.
        publisher_defaults = _yaml("07c-policy-composition.yml")
        self.assertNotIn("hatchet-killtest", publisher_defaults["openbao_credential_publish_apps"])
        self.assertEqual(
            [_render(path, self.names) for path in publisher_defaults["openbao_credential_publish_paths"]],
            ["killtest/hatchet"],
        )

    def test_dedicated_reader_is_per_call_bounded_and_not_attached_to_agents(self):
        self.assertEqual(self.names["openbao_hatchet_killtest_policy_name"], "hatchet-killtest")
        self.assertEqual(self.names["openbao_hatchet_killtest_approle_name"], "hatchet-killtest")
        self.assertEqual(self.reader["policy"], POLICY_NAME)
        self.assertNotIn("token_policies", self.reader)
        attached_roles = [role for role in self.roles if role.get("policy") == POLICY_NAME]
        self.assertEqual(len(attached_roles), 1)
        self.assertEqual(attached_roles[0]["name"], APPROLE_NAME)
        self.assertEqual(self.reader["secret_id_issuance"], "per_call")
        self.assertNotIn("manage_secret_id", self.reader)
        self.assertNotIn("role_id", self.reader)
        self.assertNotIn("secret_id", self.reader)

        ttl_defaults = _yaml("08a-admin-and-ttls.yml")
        rendered_reader = {
            **self.reader,
            "name": _render(self.reader["name"], self.names),
            "policy": _render(self.reader["policy"], self.names),
            "secret_id_ttl": _render(self.reader["secret_id_ttl"], ttl_defaults),
            "secret_id_num_uses": _render(self.reader["secret_id_num_uses"], ttl_defaults),
            "token_ttl": _render(self.reader["token_ttl"], self.names),
            "token_max_ttl": _render(self.reader["token_max_ttl"], self.names),
        }
        rendered_parameters = _render(
            _yaml("08b-cidr-and-unlock.yml")["openbao_approle_cli_parameters"],
            {
                "openbao_approles": [rendered_reader],
                "openbao_approle_cidr_class_map": {"hatchet-killtest": "machine"},
                "openbao_approle_cidr_classes": {"machine": "192.0.2.0/24"},
                "openbao_loopback_client_approles": [],
                "openbao_approle_bind_secret_id": True,
                "openbao_approle_token_ttl": "1h",
                "openbao_approle_token_max_ttl": "4h",
                "openbao_approle_secret_id_ttl_overrides": {},
                "openbao_approle_secret_id_ttl": "24h",
                "openbao_approle_secret_id_num_uses_overrides": {},
                "openbao_approle_secret_id_num_uses": 30,
            },
        )["hatchet-killtest"]
        self.assertEqual(rendered_parameters["token_policies"].split(","), ["hatchet-killtest"])
        rendered_secret_id_ttl = _duration_seconds(rendered_parameters["secret_id_ttl"])
        documented_secret_id_ttl = _duration_seconds(
            ttl_defaults["openbao_approle_per_call_secret_id_ttl"]
        )
        self.assertGreater(rendered_secret_id_ttl, 0)
        self.assertGreater(documented_secret_id_ttl, 0)
        self.assertLessEqual(rendered_secret_id_ttl, documented_secret_id_ttl)
        self.assertEqual(
            int(rendered_parameters["secret_id_num_uses"]),
            ttl_defaults["openbao_approle_per_call_secret_id_num_uses"],
        )
        self.assertEqual(rendered_parameters["token_ttl"], "15m")
        self.assertEqual(rendered_parameters["token_max_ttl"], "15m")
        self.assertNotIn("token_num_uses", rendered_parameters)

        # Minted only for Semaphore runs, so it keeps the default machine CIDR class.
        cidr = _yaml("08b-cidr-and-unlock.yml")
        self.assertEqual(cidr["openbao_approle_default_cidr_class"], "machine")
        self.assertNotIn("hatchet-killtest", cidr["openbao_approle_cidr_class_overrides"])
        rendered_class = _render(cidr["openbao_approle_cidr_class_map"], {
            "openbao_approles": [{"name": "hatchet-killtest"}],
            "openbao_approle_default_cidr_class": cidr["openbao_approle_default_cidr_class"],
            "openbao_approle_cidr_class_overrides": {},
            "openbao_github_write_scope_cidr_classes": {},
            "openbao_roster_agent_cidr_classes": {},
            "openbao_roster_key_reader_cidr_classes": {},
            "openbao_ai_apply_cidr_classes": {},
            "openbao_app_agent_tier_cidr_classes": {},
            "openbao_window_service_cidr_classes": {},
        })["hatchet-killtest"]
        self.assertEqual(rendered_class, "machine")
        self.assertNotEqual(rendered_class, "unbound")
        taxonomy =(DEFAULTS / "08d-approle-taxonomy.yml").read_text(encoding="utf-8")
        self.assertIn("openbao_hatchet_killtest_approle_name: 'converge-automation'", taxonomy)

        agent_sources = [
            path for path in DEFAULTS.glob("*.yml")
            if path.name not in {
                "05h-cribl-edge-readers.yml",
                "07c-base-policies.yml",
                "07f-elevated-approles.yml",
                "08d-approle-taxonomy.yml",
            }
        ]
        for path in agent_sources:
            with self.subTest(source=path.name):
                self.assertNotIn("openbao_hatchet_killtest_policy_name", path.read_text(encoding="utf-8"))

        issuer_source = (TEMPLATES / "approle-issuer-policy.hcl.j2").read_text(encoding="utf-8")
        issuer = _render(
            issuer_source,
            {
                "ansible_managed": "Ansible managed",
                "openbao_approles": [{**self.reader, "name": "hatchet-killtest"}],
                "openbao_reconcile_excluded_policies": [],
                "openbao_reconcile_policy_name": "openbao-reconcile",
                "openbao_approle_issuer_approle_name": "approle-issuer",
            },
        )
        issuable = re.findall(
            r'^path "auth/approle/role/([^/]+)/secret-id" \{', issuer, flags=re.MULTILINE
        )
        self.assertIn("hatchet-killtest", issuable)


if __name__ == "__main__":
    unittest.main()
