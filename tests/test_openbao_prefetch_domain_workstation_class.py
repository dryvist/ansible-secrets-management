"""Every credential identity used by openbao_secrets has a workstation CIDR class.

roles/openbao_secrets/tasks/fetch_domain.yml logs in with the credentials
named by each domain's `credential_domain`, defaulting to the data-domain name.
Several data domains may share one credential identity, but each identity
still needs an override that admits workstation use.

This pins each credential identity to an override whose class includes
`workstation` (bare `workstation` or `machine_or_workstation`), so a domain
added to the prefetch loop without a matching override fails this test
instead of silently 403ing the next workstation converge that reaches it.
"""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOMAINS_DIR = ROOT / "roles" / "openbao_secrets" / "defaults" / "main"
OVERRIDES_FILE = ROOT / "roles" / "openbao" / "defaults" / "main" / "08b-cidr-and-unlock.yml"


def _load_role_defaults(main_dir: Path) -> dict:
    """Merge defaults/main/*.yml like Ansible does for a directory-form role."""
    merged: dict = {}
    for path in sorted(main_dir.glob("*.yml")):
        merged.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return merged


class PrefetchDomainsHaveAWorkstationClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        domains_cfg = _load_role_defaults(DOMAINS_DIR)
        cls.credential_domains = sorted(
            {
                domain.get("credential_domain", domain["name"])
                for domain in domains_cfg["openbao_secrets_domains"]
            }
        )
        assert cls.credential_domains, f"no domains found in {DOMAINS_DIR}"

        cls.overrides = yaml.safe_load(OVERRIDES_FILE.read_text(encoding="utf-8"))[
            "openbao_approle_cidr_class_overrides"
        ]

    def test_every_prefetch_domain_has_an_override(self):
        missing = [d for d in self.credential_domains if d not in self.overrides]
        self.assertEqual(
            missing,
            [],
            "openbao_secrets_domains uses a credential identity with no CIDR class "
            "override, so it defaults to machine-only and rejects a "
            "workstation converge: " + ", ".join(missing),
        )

    def test_every_prefetch_domain_class_includes_workstation(self):
        wrong_class = {
            d: self.overrides[d]
            for d in self.credential_domains
            if d in self.overrides and "workstation" not in self.overrides[d]
        }
        self.assertEqual(
            wrong_class,
            {},
            "these prefetch-loop domains have an override, but its class "
            f"does not admit a workstation converge: {wrong_class}",
        )


if __name__ == "__main__":
    unittest.main()
