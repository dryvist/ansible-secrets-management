"""Converge has exact writer grants for its AI seeds and app publishers."""

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "roles/openbao/templates/ansible-converge-policy.hcl.j2"
DEFAULTS = ROOT / "roles/openbao/defaults/main/07c-base-policies.yml"
PATH_BLOCK = re.compile(
    r'path "([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]+)\]\s*\}',
    re.MULTILINE,
)
AI_SEED_APPS = ("langfuse", "langflow", "phoenix", "dify")
PUBLISH_APPS = ("grafana", "status-stack")


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


def test_ai_seed_grants_use_exact_data_and_metadata_paths() -> None:
    grants = _grants()
    for app in AI_SEED_APPS:
        data_path = f"{{{{ openbao_kv_mount }}}}/data/ai/{app}"
        metadata_path = f"{{{{ openbao_kv_mount }}}}/metadata/ai/{app}"
        assert grants.count((data_path, ("create", "update", "read"))) == 1
        assert grants.count((metadata_path, ("read",))) == 1
        assert not any(_wildcard_covers(path, data_path) for path, _ in grants)
        assert not any(_wildcard_covers(path, metadata_path) for path, _ in grants)


def test_new_app_publisher_buckets_are_listed_once_with_exact_template_paths() -> None:
    apps = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))[
        "openbao_credential_publish_apps"
    ]
    for app in PUBLISH_APPS:
        assert apps.count(app) == 1

    policy = POLICY.read_text(encoding="utf-8")
    assert (
        'path "{{ openbao_kv_mount }}/data/apps/{{ app }}" {\n'
        '  capabilities = ["create", "update", "read"]\n}'
    ) in policy
    assert (
        'path "{{ openbao_kv_mount }}/metadata/apps/{{ app }}" {\n'
        '  capabilities = ["read"]\n}'
    ) in policy
    assert 'path "{{ openbao_kv_mount }}/data/apps/*"' not in policy
    assert 'path "{{ openbao_kv_mount }}/metadata/apps/*"' not in policy


def test_eval_namespace_grants_are_exact_specialist_platform_leaves() -> None:
    eval_grants = [(path, caps) for path, caps in _grants() if "/ai/eval/" in path]
    expected = []
    for app in ("sim", "langflow", "dify", "hermes"):
        expected += [
            (f"{{{{ openbao_kv_mount }}}}/data/ai/eval/specialist-platform/{app}", ("create", "update", "read")),
            (f"{{{{ openbao_kv_mount }}}}/metadata/ai/eval/specialist-platform/{app}", ("read",)),
        ]
    assert eval_grants == expected
    assert not any("*" in path or "+" in path for path, _ in eval_grants)
