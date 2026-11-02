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


class HatchetKillTestReaderContract(unittest.TestCase):
    def setUp(self):
        self.names = _yaml("05h-cribl-edge-readers.yml")
        self.policy_rows = _yaml("07c-base-policies.yml")["openbao_base_policies_static"]
        self.roles = _yaml("07f-elevated-approles.yml")["openbao_base_approles_elevated"]
        self.reader = next(role for role in self.roles if role.get("name") == APPROLE_NAME)
        self.policy_row = next(row for row in self.policy_rows if row.get("name") == POLICY_NAME)

    def test_policy_renders_read_on_the_single_killtest_data_leaf(self):
        template = (TEMPLATES / "cribl-edge-reader-policy.hcl.j2").read_text(encoding="utf-8")
        bucket = self.policy_row["bucket"]
        policy = _render(
            template,
            {"ansible_managed": "Ansible managed", "openbao_kv_mount": "secret",
             "item": {"bucket": bucket}},
        )

        self.assertEqual(_grants(policy), [("secret/data/apps/hatchet-killtest", ("read",))])
        self.assertNotIn("*", policy)
        self.assertEqual(self.policy_row["template"], "cribl-edge-reader-policy.hcl.j2")
        self.assertEqual(bucket, "hatchet-killtest")

    def test_publisher_gets_only_the_declared_create_read_update_leaf(self):
        publisher_defaults = _yaml("07c-policy-composition.yml")
        self.assertIn("hatchet-killtest", publisher_defaults["openbao_credential_publish_apps"])

        source = (TEMPLATES / "ansible-converge-policy.hcl.j2").read_text(encoding="utf-8")
        block = re.search(
            r"{% for app in openbao_credential_publish_apps %}(.*?){% endfor %}",
            source,
            flags=re.DOTALL,
        ).group(1)
        rendered = _render(
            block,
            {"openbao_kv_mount": "secret", "app": "hatchet-killtest"},
        )
        self.assertEqual(
            _grants(rendered),
            [("secret/data/apps/hatchet-killtest", ("create", "update", "read")),
             ("secret/metadata/apps/hatchet-killtest", ("read",))],
        )

    def test_dedicated_reader_is_per_call_bounded_and_not_attached_to_agents(self):
        self.assertEqual(self.names["openbao_hatchet_killtest_policy_name"], "hatchet-killtest")
        self.assertEqual(self.names["openbao_hatchet_killtest_approle_name"], "hatchet-killtest")
        self.assertEqual(self.reader["policy"], POLICY_NAME)
        attached_roles = [role for role in self.roles if role.get("policy") == POLICY_NAME]
        self.assertEqual(len(attached_roles), 1)
        self.assertEqual(attached_roles[0]["name"], APPROLE_NAME)
        self.assertEqual(self.reader["secret_id_issuance"], "per_call")
        self.assertNotIn("manage_secret_id", self.reader)
        self.assertNotIn("role_id", self.reader)
        self.assertNotIn("secret_id", self.reader)

        excluded = [
            _render(value, self.names)
            for value in self.names["openbao_apps_read_excluded_generated_apps"]
        ]
        self.assertIn("hatchet-killtest", excluded)

        self.assertEqual(self.reader["secret_id_num_uses"], "{{ openbao_approle_per_call_secret_id_num_uses }}")
        self.assertEqual(self.reader["secret_id_ttl"], "{{ openbao_approle_per_call_secret_id_ttl }}")
        self.assertEqual(self.reader["token_max_ttl"], "15m")

        # Minted only for Semaphore runs, so it keeps the default machine CIDR class.
        cidr = _yaml("08b-cidr-and-unlock.yml")
        self.assertEqual(cidr["openbao_approle_default_cidr_class"], "machine")
        self.assertNotIn("hatchet-killtest", cidr["openbao_approle_cidr_class_overrides"])
        taxonomy = (DEFAULTS / "08d-approle-taxonomy.yml").read_text(encoding="utf-8")
        self.assertIn("'hatchet-killtest': 'converge-automation'", taxonomy)

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
