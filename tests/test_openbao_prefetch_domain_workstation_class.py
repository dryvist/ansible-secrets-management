"""Every credential identity in the repo-owned catalog has a workstation CIDR class.

The domain catalog remains repo data for policy and contract checks. Several
data domains may share one credential identity, but each identity still needs
an override that admits workstation use.
"""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
DOMAINS_FILE = ROOT / "playbooks" / "group_vars" / "all" / "openbao_secrets.yml"
OVERRIDES_FILE = ROOT / "roles" / "openbao" / "defaults" / "main" / "08b-cidr-and-unlock.yml"


class PrefetchDomainsHaveAWorkstationClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        domains_cfg = yaml.safe_load(DOMAINS_FILE.read_text(encoding="utf-8"))
        cls.credential_domains = sorted(
            {
                domain.get("credential_domain", domain["name"])
                for domain in domains_cfg["openbao_secrets_domains"]
            }
        )
        assert cls.credential_domains, f"no domains found in {DOMAINS_FILE}"

        cls.overrides = yaml.safe_load(OVERRIDES_FILE.read_text(encoding="utf-8"))[
            "openbao_approle_cidr_class_overrides"
        ]

    def test_every_catalog_domain_has_an_override(self):
        missing = [domain for domain in self.credential_domains if domain not in self.overrides]
        self.assertEqual(
            missing,
            [],
            "openbao_secrets_domains uses a credential identity with no CIDR class "
            "override: " + ", ".join(missing),
        )

    def test_every_catalog_domain_class_includes_workstation(self):
        wrong_class = {
            domain: self.overrides[domain]
            for domain in self.credential_domains
            if domain in self.overrides and "workstation" not in self.overrides[domain]
        }
        self.assertEqual(
            wrong_class,
            {},
            "these catalog domains have an override, but its class does not admit "
            f"a workstation converge: {wrong_class}",
        )


if __name__ == "__main__":
    unittest.main()
