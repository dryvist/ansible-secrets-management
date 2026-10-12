"""The Azure IaC admin credential has its own AppRole, policy and source class.

The identity must stay narrow and have no standing secret: one exact read path,
a per-call single-use secret_id that approle-issuer mints, and the workstation
source class only. These read the declarations, never a restated copy of them.
"""

from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles" / "openbao" / "defaults" / "main"
TEMPLATE = ROOT / "roles" / "openbao" / "templates" / "azure-iac-admin-policy.hcl.j2"
APPROLE = "{{ openbao_azure_iac_admin_approle_name }}"
POLICY = "{{ openbao_azure_iac_admin_policy_name }}"


def _yaml(name):
    return yaml.safe_load((DEFAULTS / name).read_text(encoding="utf-8"))


class TestAzureIacAdminIdentity(unittest.TestCase):
    def test_names_are_declared_and_distinct_from_shared_identities(self):
        names = _yaml("02b-azure-engine.yml")
        self.assertEqual(names["openbao_azure_iac_admin_approle_name"], "azure-iac-admin")
        self.assertEqual(names["openbao_azure_iac_admin_policy_name"], "azure-iac-admin")

    def test_approle_mints_only_single_use_secret_ids_per_call(self):
        roles = _yaml("07f-workstation-approles.yml")["openbao_workstation_approles"]
        role = next(r for r in roles if r["name"] == APPROLE)
        self.assertEqual(role["policy"], POLICY)
        self.assertEqual(role["secret_id_issuance"], "per_call")
        self.assertEqual(role["secret_id_ttl"], "{{ openbao_approle_per_call_secret_id_ttl }}")
        self.assertEqual(role["secret_id_num_uses"], "{{ openbao_approle_per_call_secret_id_num_uses }}")
        self.assertEqual(role["token_ttl"], "15m")
        self.assertEqual(role["token_max_ttl"], "15m")
        self.assertNotIn("manage_secret_id", role)
        self.assertNotIn("token_policies", role)

    def test_policy_is_registered_from_its_own_template(self):
        rows = _yaml("07c-base-policies.yml")["openbao_base_policies_static"]
        row = next(r for r in rows if r["name"] == POLICY)
        self.assertEqual(row["template"], "azure-iac-admin-policy.hcl.j2")

    def test_policy_grants_one_read_on_one_exact_path(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        paths = re.findall(r'(?m)^path "([^"]+)"', text)
        self.assertEqual(
            paths,
            ["{{ openbao_azure_mount }}/creds/{{ openbao_azure_iac_admin_role_name }}"],
        )
        capabilities = re.findall(r"(?m)^\s*capabilities\s*=\s*(\[[^\]]*\])", text)
        self.assertEqual(capabilities, ['["read"]'])
        self.assertNotIn("*", "".join(paths))

    def test_no_other_policy_template_reads_the_azure_credentials(self):
        # ai-admin holds the whole mount for engine administration; every other
        # template stays out of it so the credential has one reader.
        allowed = {"azure-iac-admin-policy.hcl.j2", "ai-admin-policy.hcl.j2"}
        readers = [
            t.name
            for t in TEMPLATE.parent.glob("*.hcl.j2")
            if "openbao_azure_mount" in t.read_text(encoding="utf-8") and t.name not in allowed
        ]
        self.assertEqual(readers, [])

    def test_source_class_is_workstation_only(self):
        overrides = _yaml("08b-cidr-and-unlock.yml")["openbao_approle_cidr_class_overrides"]
        self.assertEqual(overrides["azure-iac-admin"], "workstation")


if __name__ == "__main__":
    unittest.main()
