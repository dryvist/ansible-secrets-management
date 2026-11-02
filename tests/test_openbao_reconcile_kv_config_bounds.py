"""Rendered KV configuration grants pin each mount retention."""

from openbao_reconcile_bounds_helpers import (
    _allowed_parameters, _render, _stanzas, rendered_defaults, RECONCILE
)

def test_rendered_kv_config_grants_pin_each_mount_to_its_declared_retention(
    rendered_defaults,
):
    values, _approles, _policies = rendered_defaults
    mounts = [
        {
            "path": values["openbao_config_mount"],
            "max_versions": values["openbao_config_mount_max_versions"],
        },
        {"path": values["openbao_kv_mount"], "max_versions": 7},
    ]
    context = dict(values, openbao_kv_tuned_mounts=mounts)
    stanzas = dict(_stanzas(_render(RECONCILE, context)))

    for mount in mounts:
        body = stanzas[f"{mount['path']}/config"]
        assert _allowed_parameters(body) == {
            "max_versions": [str(mount["max_versions"])]
        }
