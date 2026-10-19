"""The Semaphore policy grants only the router's declared app reads."""

from pathlib import Path

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "roles" / "openbao" / "templates" / "semaphore-policy.hcl.j2"


def _render(kv_mount: str) -> str:
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "ansible_managed": "Ansible managed",
        "openbao_kv_mount": kv_mount,
        "openbao_github_everyday_mount": "github-everyday",
        "openbao_semaphore_github_raw_read_permissions": {"contents": "read"},
        "openbao_semaphore_github_read_permission_sets": [],
    }
    return templar.template(trust_as_template(POLICY.read_text(encoding="utf-8")))


def test_router_app_entries_render_as_exact_read_only_kv_v2_grants():
    kv_mount = "secrets-store"
    policy = _render(kv_mount)

    for app in ("benchmark", "sandbox-agent"):
        assert (
            f'path "{kv_mount}/data/apps/{app}" {{\n'
            '  capabilities = ["read"]\n'
            "}"
        ) in policy
        assert (
            f'path "{kv_mount}/metadata/apps/{app}" {{\n'
            '  capabilities = ["read", "list"]\n'
            "}"
        ) in policy

    assert f'path "{kv_mount}/data/apps/*"' not in policy
    assert f'path "{kv_mount}/metadata/apps/*"' not in policy
