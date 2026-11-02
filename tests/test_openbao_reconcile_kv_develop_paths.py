"""KV data grants preserve the documented develop-path contract."""

from pathlib import Path
from openbao_reconcile_bounds_helpers import (
    RECONCILE,
    _capabilities,
    _effective_policy_union,
    _render,
    _render_value,
    _stanzas,
    _templar,
    _trust,
    rendered_defaults,
)
import subprocess

from ansible.template import trust_as_template

# Snapshot fallback for depth-one CI checkouts where origin/develop is absent.
# When the ref exists, the regression test renders its actual policy template.
# Metadata grants are outside this data-path regression check.
DEVELOP_KV_DATA_GRANTS = """
{% for mount in openbao_kv_mounts | default([]) %}
path "{{ mount.path | default(mount) }}/*" {
  capabilities = ["create", "read", "update", "list"]
}
{% endfor %}
{% for reader in openbao_app_agent_tier_readers %}
path "{{ openbao_agent_tier_mount }}/data/{{ reader.tier }}" {
  capabilities = ["create", "read", "update"]
}
{% if reader.login_path is defined %}
path "{{ openbao_agent_tier_mount }}/data/{{ reader.login_path }}" {
  capabilities = ["create", "read", "update"]
}
{% endif %}
{% endfor %}
"""
DEVELOP_INTENTIONALLY_REMOVED_KV_DATA_PATHS = {
    "secret/*": (
        "The bounded policy replaces mount-wide access with exact task and consumer grants."
    ),
    "secrets-external/*": (
        "The bounded policy replaces mount-wide access with exact task and consumer grants."
    ),
    "config/*": (
        "The bounded policy replaces mount-wide access with exact task and consumer grants."
    ),
}
ROOT = Path(__file__).resolve().parents[1]

def _render_template_text(values, template):
    templar = _templar(_trust(dict(values)))
    templar._loader.set_basedir(str(ROOT / "roles" / "openbao"))
    return templar.template(trust_as_template(template))

def _develop_reconcile_template():
    result = subprocess.run(
        [
            "git",
            "show",
            "origin/develop:roles/openbao/templates/openbao-reconcile-policy.hcl.j2",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    return result.stdout if result.returncode == 0 else DEVELOP_KV_DATA_GRANTS

def test_reconcile_kv_data_grants_preserve_develop_paths_or_explain_removal(
    rendered_defaults,
):
    values, _approles, _policies = rendered_defaults
    develop_rendered = _render_template_text(values, _develop_reconcile_template())
    all_develop_stanzas = dict(_stanzas(develop_rendered))
    mounts = _render_value(values, values["openbao_kv_mounts"])
    mount_wildcards = {
        f"{mount.get('path', mount) if isinstance(mount, dict) else mount}/*"
        for mount in mounts
    }
    develop = {
        path: body
        for path, body in all_develop_stanzas.items()
        if "/data/" in path or path in mount_wildcards
    }
    current = dict(_stanzas(_render(RECONCILE, values)))
    develop_data_paths = set(develop)
    assert set(DEVELOP_INTENTIONALLY_REMOVED_KV_DATA_PATHS) <= develop_data_paths

    for path in develop_data_paths:
        if path in DEVELOP_INTENTIONALLY_REMOVED_KV_DATA_PATHS:
            assert DEVELOP_INTENTIONALLY_REMOVED_KV_DATA_PATHS[path].strip(), path
            assert path not in current, f"removed wildcard returned: {path}"
            continue

        assert path in current, (
            f"develop KV data path was dropped without a reason: {path}"
        )
        assert "read" in _capabilities(current[path]), path
        assert "+" not in path and "*" not in path, path

    splunk_path = f"{values['openbao_kv_mount']}/data/platform/splunk/main"
    assert "read" in _effective_policy_union([develop], splunk_path)
    assert _effective_policy_union([current], splunk_path) == {"read"}
