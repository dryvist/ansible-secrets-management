"""The semaphore execution role keeps its intended policy union."""

from openbao_reconcile_bounds_helpers import (
    _attached_stanzas, _effective_policy_union, _role_policies, rendered_defaults
)


def test_semaphore_execution_role_keeps_its_intended_policy_union(rendered_defaults):
    values, approles, policies = rendered_defaults
    semaphore = next(
        role for role in approles
        if role["name"] == values["openbao_semaphore_approle_name"]
    )
    attached = _role_policies(semaphore)
    assert values["openbao_reconcile_policy_name"] in attached
    assert values["openbao_ansible_converge_policy_name"] in attached
    assert values["openbao_semaphore_policy_name"] in attached

    attached_stanzas = _attached_stanzas(
        values, approles, policies, values["openbao_semaphore_approle_name"]
    )

    assert _effective_policy_union(
        attached_stanzas, "secret/data/apps/semaphore"
    ) == {"create", "read", "update"}
    assert _effective_policy_union(
        attached_stanzas, "secret/data/apps/unlisted"
    ) == set()
    assert _effective_policy_union(
        attached_stanzas, "secret/data/ai/mcp/cribl"
    ) == set()


def test_execution_role_reads_every_platform_env_document(rendered_defaults):
    values, approles, policies = rendered_defaults
    attached_stanzas = _attached_stanzas(
        values, approles, policies, values["openbao_semaphore_approle_name"]
    )
    env_path = values["openbao_platform_env_path"]

    for mount in (values["openbao_config_mount"], values["openbao_kv_mount"], "secrets-external"):
        assert _effective_policy_union(
            attached_stanzas, f"{mount}/data/{env_path}"
        ) == {"read"}, mount
        assert _effective_policy_union(
            attached_stanzas, f"{mount}/metadata/{env_path}"
        ) == {"read"}, mount


def test_execution_role_inherits_the_reconcile_reads_it_attaches(rendered_defaults):
    # The execution role attaches the reconcile policy by design, so every
    # reconcile read leaf also reaches it through that attachment.
    values, approles, policies = rendered_defaults
    attached_stanzas = _attached_stanzas(
        values, approles, policies, values["openbao_semaphore_approle_name"]
    )
    kv_mount = values["openbao_kv_mount"]

    assert _effective_policy_union(
        attached_stanzas, f"{kv_mount}/data/platform/terrakube/main"
    ) == {"read"}
