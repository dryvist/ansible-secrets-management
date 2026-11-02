"""The semaphore execution role keeps its intended policy union."""

from openbao_reconcile_bounds_helpers import (
    _effective_policy_union, _render, _role_policies, _stanzas, rendered_defaults, TEMPLATES
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

    policy_by_name = {policy["name"]: policy for policy in policies}
    attached_stanzas = []
    for policy_name in attached:
        policy = policy_by_name.get(policy_name)
        if policy is None:
            continue
        context = dict(values, item=policy)
        attached_stanzas.append(
            dict(_stanzas(_render(TEMPLATES / policy["template"], context)))
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
