"""The PBS API token publisher and PVE reader use one exact KV v2 path."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "roles/openbao/templates/ansible-converge-policy.hcl.j2"
PATH_BLOCK = re.compile(r'path "([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]+)\]\s*\}', re.MULTILINE)
PBS_DATA = "{{ openbao_kv_mount }}/data/platform/pbs/pve-nodes"
PBS_METADATA = "{{ openbao_kv_mount }}/metadata/platform/pbs/pve-nodes"


def _grants() -> list[tuple[str, tuple[str, ...]]]:
    return [
        (path, tuple(re.findall(r'"([^"]+)"', capabilities)))
        for path, capabilities in PATH_BLOCK.findall(POLICY.read_text(encoding="utf-8"))
    ]


def _wildcard_covers(pattern: str, target: str) -> bool:
    if pattern.endswith("*"):
        return target.startswith(pattern[:-1])
    if "+" in pattern:
        pattern_parts = pattern.split("/")
        target_parts = target.split("/")
        return len(pattern_parts) == len(target_parts) and all(
            part == "+" or part == target_part
            for part, target_part in zip(pattern_parts, target_parts)
        )
    return False


def test_pbs_api_token_has_exact_data_and_metadata_grants() -> None:
    grants = _grants()
    assert grants.count((PBS_DATA, ("create", "read", "update"))) == 1
    assert grants.count((PBS_METADATA, ("read",))) == 1


def test_no_wildcard_grant_covers_pbs_token_path() -> None:
    grants = _grants()
    assert not any(_wildcard_covers(path, PBS_DATA) for path, _ in grants)
    assert not any(_wildcard_covers(path, PBS_METADATA) for path, _ in grants)
