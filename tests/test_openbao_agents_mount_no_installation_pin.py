"""Agents mount policies do not allow installation IDs or owner-specific token sets."""

from pathlib import Path
import re

from jinja2 import Environment
import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "roles/openbao/templates"
GITHUB_MOUNT_DEFAULTS = ROOT / "roles/openbao/defaults/main/03b-github-app-mounts.yml"
AGENTS_MOUNT = "github-agents"
ALLOWED_NAMED_SETS = {"public-read", "public-write"}
RAW_MINT_PERMISSIONS = yaml.safe_load(GITHUB_MOUNT_DEFAULTS.read_text(encoding="utf-8"))[
    "openbao_github_agents_raw_mint_permissions"
]


def _agents_policy_templates():
    return sorted(
        path
        for path in TEMPLATE_DIR.rglob("*.j2")
        if "openbao_github_agents_mount" in path.read_text(encoding="utf-8")
    )


def _render_policy(path):
    environment = Environment()
    environment.filters["comment"] = str
    return environment.from_string(path.read_text(encoding="utf-8")).render(
        ansible_managed="",
        openbao_kv_mount="secret",
        openbao_github_agents_mount=AGENTS_MOUNT,
        openbao_github_agents_installation_id="4242",
        openbao_github_agents_raw_mint_permissions=RAW_MINT_PERMISSIONS,
        openbao_sandbox_agent_read_approle_name="sandbox-agent-read",
        openbao_sandbox_agent_write_approle_name="sandbox-agent-write",
    )


def test_agents_mount_policies_have_no_installation_pin_or_owner_token_sets():
    templates = _agents_policy_templates()
    assert templates, "no policy templates reference openbao_github_agents_mount"
    failures = []

    for template in templates:
        rendered = _render_policy(template)
        stanzas = []
        for match in re.finditer(
            r'(?ms)^path "([^"]+)"\s*\{\n(.*?)^\}', rendered
        ):
            path = match.group(1)
            if path == AGENTS_MOUNT or path.startswith(AGENTS_MOUNT + "/"):
                stanzas.append((path, match.group(2)))
        assert stanzas, f"{template.name}: no rendered stanza on {AGENTS_MOUNT}"

        for path, body in stanzas:
            allowed_parameters = re.search(
                r"(?ms)^[ \t]*allowed_parameters[ \t]*=\s*\{(.*?)^  \}", body
            )
            if allowed_parameters and re.search(
                r'(?m)^[ \t]*"installation_id"[ \t]*=', allowed_parameters.group(1)
            ):
                failures.append(
                    f"{template.name}: stanza {path!r} allows installation_id"
                )

            named_set = re.fullmatch(
                re.escape(AGENTS_MOUNT) + r"/token/([^/]+)", path
            )
            if named_set and named_set.group(1) not in ALLOWED_NAMED_SETS:
                failures.append(
                    f"{template.name}: stanza {path!r} names an unapproved token set"
                )

    assert not failures, "\n".join(failures)
