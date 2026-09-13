"""Every openbao_secrets prefetch-loop domain needs a workstation CIDR class.

roles/openbao_secrets/tasks/fetch_domain.yml logs into one AppRole per
`openbao_secrets_domains` entry (roles/openbao_secrets/defaults/main.yml) --
observability, local-cloud, monitoring, media, apps, ntfy, local-llm -- for
every workstation-run converge (`scripts/run-ansible.sh` from a dev shell).
None of them had a CIDR class override, so all seven defaulted to `machine`
and rejected the workstation exactly like slack-ops did: observability is
first in the loop, so every workstation converge died on the very first
domain, regardless of which app the converge was actually for.

This pins each declared domain to an override whose class includes
`workstation` (bare `workstation` or `machine_or_workstation`), so a domain
added to the prefetch loop without a matching override fails this test
instead of silently 403ing the next workstation converge that reaches it.
"""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOMAINS_FILE = ROOT / "roles" / "openbao_secrets" / "defaults" / "main.yml"
OVERRIDES_FILE = ROOT / "roles" / "openbao" / "defaults" / "main" / "08b-cidr-and-unlock.yml"


class PrefetchDomainsHaveAWorkstationClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        domains_cfg = yaml.safe_load(DOMAINS_FILE.read_text(encoding="utf-8"))
        cls.domain_names = [d["name"] for d in domains_cfg["openbao_secrets_domains"]]
        assert cls.domain_names, f"no domains found in {DOMAINS_FILE}"

        cls.overrides = yaml.safe_load(OVERRIDES_FILE.read_text(encoding="utf-8"))[
            "openbao_approle_cidr_class_overrides"
        ]

    def test_every_prefetch_domain_has_an_override(self):
        missing = [d for d in self.domain_names if d not in self.overrides]
        self.assertEqual(
            missing,
            [],
            "openbao_secrets_domains names an AppRole with no CIDR class "
            "override, so it defaults to machine-only and rejects a "
            "workstation converge: " + ", ".join(missing),
        )

    def test_every_prefetch_domain_class_includes_workstation(self):
        wrong_class = {
            d: self.overrides[d]
            for d in self.domain_names
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
