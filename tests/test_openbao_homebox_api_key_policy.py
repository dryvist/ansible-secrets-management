"""The Homebox API key publisher has one exact KV v2 write grant."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "roles/openbao/templates/ansible-converge-policy.hcl.j2"
PATH_BLOCK = re.compile(r'path "([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]+)\]\s*\}', re.MULTILINE)


def _grants() -> list[tuple[str, tuple[str, ...]]]:
    return [
        (path, tuple(re.findall(r'"([^"]+)"', capabilities)))
        for path, capabilities in PATH_BLOCK.findall(POLICY.read_text(encoding="utf-8"))
    ]


def test_homebox_api_key_has_exact_data_and_metadata_grants() -> None:
    grants = _grants()
    assert grants.count(("{{ openbao_kv_mount }}/data/homebox/main/rw", ("create", "update", "read"))) == 1
    assert grants.count(("{{ openbao_kv_mount }}/metadata/homebox/main/rw", ("read",))) == 1
