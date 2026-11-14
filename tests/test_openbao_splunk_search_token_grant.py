"""Converge may publish the Splunk platform search token at its single exact path, and nothing wider."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "roles/openbao/templates"
CONVERGE = TEMPLATES / "ansible-converge-policy.hcl.j2"
SEMAPHORE = TEMPLATES / "semaphore-policy.hcl.j2"
PATH_BLOCK = re.compile(r'path "([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]+)\]\s*\}', re.MULTILINE)
MOUNT = "{{ openbao_kv_mount }}"


def _grants(template: Path) -> dict[str, tuple[str, ...]]:
    return {
        path: tuple(re.findall(r'"([^"]+)"', caps))
        for path, caps in PATH_BLOCK.findall(template.read_text(encoding="utf-8"))
    }


def test_converge_grants_the_search_token_at_exact_paths_only() -> None:
    grants = _grants(CONVERGE)
    assert grants[f"{MOUNT}/data/platform/splunk/search"] == ("create", "update", "read")
    assert grants[f"{MOUNT}/metadata/platform/splunk/search"] == ("read",)
    assert grants[f"{MOUNT}/undelete/platform/splunk/search"] == ("update",)
    splunk = [path for path in grants if "platform/splunk" in path]
    assert sorted(splunk) == sorted(
        f"{MOUNT}/{kind}/platform/splunk/search" for kind in ("data", "metadata", "undelete")
    )


def test_no_wildcard_or_main_grant_reaches_the_platform_splunk_tree() -> None:
    for template in TEMPLATES.glob("*.hcl.j2"):
        for path in _grants(template):
            if "platform/splunk" in path or path.endswith(("/platform/*", "/platform/+")):
                assert "*" not in path and "+" not in path, f"{template.name}: {path}"
    assert f"{MOUNT}/data/platform/splunk/main" not in _grants(CONVERGE)
    assert _grants(SEMAPHORE)[f"{MOUNT}/data/platform/splunk/main"] == ("read",)


def test_converge_grants_the_rotator_credentials_at_exact_paths_only() -> None:
    grants = _grants(CONVERGE)
    assert grants[f"{MOUNT}/data/apps/splunk-rotator"] == ("create", "update", "read")
    assert grants[f"{MOUNT}/metadata/apps/splunk-rotator"] == ("read",)
    rotator = [path for path in grants if "splunk-rotator" in path]
    assert sorted(rotator) == sorted(f"{MOUNT}/{kind}/apps/splunk-rotator" for kind in ("data", "metadata"))
