"""The declared MCP credential owners match the policy template grants."""

from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main/05k-roster-agents.yml"
TEMPLATES = ROOT / "roles/openbao/templates"
DEFAULTS_DATA = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))


def _grants_slug(template, slug):
    for path, capabilities in re.findall(
        r'path\s+"([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]*)\]',
        template.read_text(encoding="utf-8"),
        re.DOTALL,
    ):
        if "deny" in capabilities:
            continue
        match = re.search(r"/(?:data|metadata|undelete)/ai/(.+)$", path)
        if match and match.group(1) in ("*", "mcp/*", f"mcp/{slug}"):
            return True
    return False


def test_mcp_credential_owners_match_template_grants():
    ownable_slugs = DEFAULTS_DATA["openbao_roster_agent_ownable_slugs"]
    declared_owners = DEFAULTS_DATA["openbao_mcp_credential_owners"]
    policy_templates = sorted(TEMPLATES.glob("*.hcl.j2"))
    expected_owners = {
        slug: sorted(
            template.name.removesuffix(".hcl.j2").removesuffix("-policy")
            for template in policy_templates
            if _grants_slug(template, slug)
        )
        for slug in ownable_slugs
    }

    assert {slug: sorted(declared_owners.get(slug, [])) for slug in ownable_slugs} == (
        expected_owners
    )
    assert set(declared_owners) == set(ownable_slugs)
