"""Sandbox policies render only the declared leaf and GitHub permission sets."""

from pathlib import Path
import re
import unittest

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "roles" / "openbao" / "templates"
POLICIES = (
    "sandbox-agent-read-policy.hcl.j2",
    "sandbox-agent-write-policy.hcl.j2",
)


def _render(policy):
    environment = Environment(loader=FileSystemLoader(TEMPLATES))
    environment.filters["comment"] = lambda value: "# " + str(value)
    return environment.get_template(policy).render(
        ansible_managed="managed",
        openbao_kv_mount="secret",
        openbao_github_agents_mount="github-agents",
    )


class SandboxAgentPolicies(unittest.TestCase):
    def test_policies_do_not_read_external_secrets_or_wildcard_secret_paths(self):
        for policy in POLICIES:
            with self.subTest(policy=policy):
                rendered = _render(policy)
                self.assertNotIn("secrets-external", rendered)
                self.assertIsNone(
                    re.search(r'path "secret/(?:data|metadata)/[^"*+]*[*+][^"]*"', rendered)
                )

    def test_read_policy_is_limited_to_the_sandbox_leaf_and_read_token_set(self):
        rendered = _render(POLICIES[0])
        self.assertIn('path "secret/data/apps/sandbox-agent"', rendered)
        self.assertIn('path "github-agents/token/public-read"', rendered)
        self.assertNotIn('path "github-agents/token/public-write"', rendered)

    def test_write_policy_reads_only_the_sandbox_leaf_and_mints_write_tokens(self):
        rendered = _render(POLICIES[1])
        self.assertCountEqual(
            re.findall(r'path "([^"]+)"', rendered),
            ["secret/data/apps/sandbox-agent", "github-agents/token/public-write"],
        )
        self.assertCountEqual(
            re.findall(
                r'path "([^"]+)" \{\s*capabilities = \[([^\]]+)\]\s*\}',
                rendered,
            ),
            [
                ("secret/data/apps/sandbox-agent", '"read"'),
                ("github-agents/token/public-write", '"create", "update"'),
            ],
        )
        self.assertNotIn("secrets-external", rendered)
        self.assertIsNone(
            re.search(r'path "secret/(?:data|metadata)/[^"*+]*[*+][^"]*"', rendered)
        )
        self.assertNotIn('path "secret/metadata', rendered)
        self.assertNotIn('path "github-agents/token/public-read"', rendered)


if __name__ == "__main__":
    unittest.main()
