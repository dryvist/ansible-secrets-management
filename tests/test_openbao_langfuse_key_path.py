"""Langfuse's project-key fields share the exact Hermes secret record."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CONVERGE_POLICY = ROOT / "roles/openbao/templates/ansible-converge-policy.hcl.j2"
HERMES_POLICY = ROOT / "roles/openbao/templates/hermes-policy.hcl.j2"
PATH_BLOCK = re.compile(
    r'path "([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]+)\]\s*\}',
    re.MULTILINE,
)
LANGFUSE_PATH = "{{ openbao_kv_mount }}/data/ai/hermes"
LANGFUSE_METADATA_PATH = "{{ openbao_kv_mount }}/metadata/ai/hermes"


def _grants(path: Path) -> list[tuple[str, tuple[str, ...]]]:
    return [
        (secret_path, tuple(re.findall(r'"([^"]+)"', capabilities)))
        for secret_path, capabilities in PATH_BLOCK.findall(path.read_text(encoding="utf-8"))
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


def test_langfuse_project_key_path_reuses_exact_converge_and_hermes_grants() -> None:
    converge_grants = _grants(CONVERGE_POLICY)
    hermes_grants = _grants(HERMES_POLICY)

    assert converge_grants.count((LANGFUSE_PATH, ("create", "update", "read"))) == 1
    assert converge_grants.count((LANGFUSE_METADATA_PATH, ("read",))) == 1
    assert hermes_grants.count((LANGFUSE_PATH, ("read",))) == 1
    assert not any(_wildcard_covers(path, LANGFUSE_PATH) for path, _ in converge_grants)
    assert not any(_wildcard_covers(path, LANGFUSE_PATH) for path, _ in hermes_grants)
