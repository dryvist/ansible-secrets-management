from pathlib import Path
import re
import unittest

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "roles/openbao/templates/openbao-reconcile-policy.hcl.j2"


def grants(retired_roles, retired_policies, transit_mount="transit", state_key="tofu-state"):
    env = Environment()
    env.filters["comment"] = lambda value: ""
    rendered = env.from_string(TEMPLATE.read_text()).render(
        ansible_managed="", openbao_reconcile_excluded_policies=["ai-admin", "openbao-reconcile"],
        openbao_policies=[], openbao_approles=[], openbao_ssh_roles=[],
        openbao_ssh_mount="ssh-client-ca", openbao_kv_mounts=[],
        openbao_github_mount="github", openbao_github_app_mounts=[],
        openbao_retired_approles=retired_roles, openbao_retired_policies=retired_policies,
        openbao_retired_terrakube_prefix="terrakube-tofu-github-owner-",
        openbao_terrakube_jwt_auth_path="terrakube",
        openbao_transit_mount=transit_mount,
        openbao_tofu_state_transit_key=state_key,
    )
    return {
        path: set(re.findall(r'"([^"]+)"', body))
        for path, body in re.findall(
            r'path "([^"]+)"\s*{\s*capabilities\s*=\s*\[([^]]*)\]', rendered
        )
    }


class RetirementGrants(unittest.TestCase):
    def test_only_named_retirements_have_delete(self):
        policy = grants(["open-llm-workstation", "github-agents"], ["github-agents"])
        deleted = {path for path, caps in policy.items() if "delete" in caps}
        self.assertEqual(deleted, {
            "auth/approle/role/open-llm-workstation",
            "auth/approle/role/github-agents",
            "auth/terrakube/role/terrakube-tofu-github-owner-*",
            "sys/policies/acl/github-agents",
            "github-agents/permissionset/agents-write",
        })
        for path in deleted:
            self.assertEqual(policy[path], {"read", "delete"})
        self.assertEqual(policy["auth/terrakube/role"], {"list"})

    def test_protected_names_cannot_be_retired(self):
        policy = grants(["ai-admin", "openbao-reconcile"], ["ai-admin", "openbao-reconcile"])
        for name in ("ai-admin", "openbao-reconcile"):
            self.assertNotIn("auth/approle/role/" + name, policy)
            self.assertNotIn("sys/policies/acl/" + name, policy)

    def test_transit_grants_are_exact_and_keep_only_the_mount_inventory_read(self):
        policy = grants([], [], transit_mount="transit", state_key="tofu-state")
        self.assertEqual(policy["sys/mounts/transit"], {"read", "update"})
        self.assertEqual(policy["transit/keys/tofu-state"], {"read", "update"})
        self.assertEqual(
            {path for path in policy if path.startswith("sys/mounts/")},
            {"sys/mounts/transit"},
        )
        self.assertEqual(
            {path for path in policy if path.startswith("transit/")},
            {"transit/keys/tofu-state"},
        )
        self.assertEqual(policy["sys/mounts"], {"read", "list"})
