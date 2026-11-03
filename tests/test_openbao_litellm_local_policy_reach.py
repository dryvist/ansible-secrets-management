"""Who reaches the Studio local proxy's router key, asked of a real OpenBao dev server.

llm-gate gains read on the data leaf only. Every other holder already reaches it
through the apps catalog, reconcile or break-glass policies; the set is exact.
"""

import unittest

from test_openbao_hatchet_killtest_policy_reach import holders, reach

DATA, METADATA = "secret/data/apps/litellm-local", "secret/metadata/apps/litellm-local"
DATA_HOLDERS = {
    "llm-gate": ["read"],
    "apps": ["read"],
    "read-apps": ["read"],
    "apps-rotate": ["read", "update"],
    "apps-seed": ["create", "read", "update"],
    "write-apps": ["create", "delete", "patch", "update"],
    "openbao-reconcile": ["create", "list", "read", "update"],
    "operator-human": ["read"],
    # Global read reaches every KV leaf except the actuating credentials it denies.
    "ai-global-read": ["read"],
    "ai-admin": ["create", "delete", "list", "patch", "read", "update"],
}


class LitellmLocalPolicyReach(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        found = reach([DATA, METADATA, "secret/data/apps/other", "secret/data/apps/litellm-local-workstation"])
        cls.failed, cls.rejected, cls.caps = found["failed"], found["rejected"], found["caps"]

    def test_every_policy_renders_and_loads(self):
        self.assertEqual(self.failed, {})
        self.assertEqual(self.rejected, {})

    def test_the_data_leaf_holders_are_exact(self):
        self.assertEqual(holders(self.caps, DATA), DATA_HOLDERS)

    def test_llm_gate_reads_only_the_data_leaf(self):
        gate = self.caps["llm-gate"]
        self.assertEqual(gate[DATA], ["read"])
        self.assertEqual(gate[METADATA], ["deny"])
        self.assertEqual(gate["secret/data/apps/other"], ["deny"])
        self.assertEqual(gate["secret/data/apps/litellm-local-workstation"], ["deny"])


if __name__ == "__main__":
    unittest.main()
