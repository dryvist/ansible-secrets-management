"""Rendered AppRole creation commands enforce declared bounds."""

from openbao_reconcile_bounds_helpers import (
    APPROLE_TASKS,
    RECONCILE,
    TTL_TASKS,
    _allowed_parameters,
    _render,
    _stanzas,
    _task,
    _templar,
    _trust,
    rendered_defaults,
)
import json
import re

from ansible.template import trust_as_template


def _render_task_command(task, values, role):
    live = {
        "data": {
            "secret_id_bound_cidrs": [],
            "token_bound_cidrs": [],
            "secret_id_ttl": 0,
            "secret_id_num_uses": 0,
            "token_ttl": 0,
            "token_max_ttl": 0,
            "token_explicit_max_ttl": 0,
            "token_type": "default",
        }
    }
    command = task["ansible.builtin.command"]["cmd"]
    context = dict(
        values,
        item=(role, {"rc": 0, "stdout": json.dumps(live)}),
        live=live["data"],
        approle_cli_parameters=values["openbao_approle_cli_parameters"][role["name"]],
    )
    task_vars = task.get("vars", {})
    if "approle_cli_parameters" in task_vars:
        assert task_vars["approle_cli_parameters"] == (
            "{{ openbao_approle_cli_parameters[item.0.name] }}"
        )
    referenced = dict.fromkeys(re.findall(r"{{\s*([A-Za-z_]\w*)", command))
    for name in referenced:
        if name in task_vars and name != "approle_cli_parameters":
            context[name] = _templar(_trust(context)).template(_trust(task_vars[name]))
    return _templar(_trust(context)).template(trust_as_template(command))

def _command_arguments(command):
    return dict(re.findall(r"(?:^|\s)([a-z_]+)=([^\s]+)", command))

def test_managed_approle_writes_pin_declared_policy_binding_and_cidrs(rendered_defaults):
    values, approles, _policies = rendered_defaults
    reconcile = _render(RECONCILE, values)
    roles_by_name = {role["name"]: role for role in approles}
    root_paths = {
        path.removeprefix("auth/approle/role/"): body
        for path, body in _stanzas(reconcile)
        if re.fullmatch(r"auth/approle/role/[^/]+", path)
        and '"create"' in body
        and '"update"' in body
    }
    policy_paths = {
        path.removeprefix("auth/approle/role/").removesuffix("/policies"): body
        for path, body in _stanzas(reconcile)
        if re.fullmatch(r"auth/approle/role/[^/]+/policies", path)
        and '"create"' in body
        and '"update"' in body
    }
    assert root_paths
    assert set(root_paths) == set(policy_paths)

    pinned_parameters = {
        "token_ttl",
        "token_max_ttl",
        "token_explicit_max_ttl",
        "token_type",
        "secret_id_ttl",
        "secret_id_num_uses",
    }
    create_task = _task(APPROLE_TASKS, "Create the missing AppRoles bound to their policy")
    policy_task = _task(APPROLE_TASKS, "Reconcile token_policies on existing AppRoles")
    ttl_task = _task(TTL_TASKS, "Reconcile AppRole TTL and token bounds on existing AppRoles")
    for name, body in root_paths.items():
        role = roles_by_name[name]
        parameters = values["openbao_approle_cli_parameters"][name]
        allowed = _allowed_parameters(body)
        assert allowed["token_policies"] == [parameters["token_policies"]], name
        assert allowed["bind_secret_id"] == [parameters["bind_secret_id"]], name
        pinned = {"token_policies", "bind_secret_id"}
        if parameters["secret_id_bound_cidrs"]:
            pinned.update({"secret_id_bound_cidrs", "token_bound_cidrs"})
            assert allowed["secret_id_bound_cidrs"] == [parameters["secret_id_bound_cidrs"]], name
            assert allowed["token_bound_cidrs"] == [parameters["token_bound_cidrs"]], name
        pinned.update(pinned_parameters)
        assert set(allowed) == pinned, name
        assert all(
            isinstance(value, str) and "*" not in value
            for key in pinned
            for value in allowed[key]
        ), name
        assert not re.search(
            r'"(?:token_ttl|token_max_ttl|token_explicit_max_ttl|token_type|'
            r'secret_id_ttl|secret_id_num_uses)"\s*=\s*\[\]',
            body,
        ), name
        for key in pinned_parameters:
            assert allowed[key] == [parameters[key]], (name, key)

        for task in (create_task, ttl_task):
            sent = _command_arguments(_render_task_command(task, values, role))
            for key in pinned:
                assert sent[key].encode() == allowed[key][0].encode(), (name, task["name"], key)
            if not parameters["secret_id_bound_cidrs"]:
                assert not {"secret_id_bound_cidrs", "token_bound_cidrs"} & sent.keys(), name

    for name, body in policy_paths.items():
        role = roles_by_name[name]
        parameters = values["openbao_approle_cli_parameters"][name]
        allowed = _allowed_parameters(body)
        assert allowed == {"token_policies": [parameters["token_policies"]]}, name
        assert "*" not in allowed["token_policies"][0], name
        sent = _command_arguments(_render_task_command(policy_task, values, role))
        assert sent["token_policies"].encode() == allowed["token_policies"][0].encode(), name
        assert json.loads(
            re.search(r"required_parameters\s*=\s*(\[[^\n]*\])", body).group(1)
        ) == ["token_policies"], name

    for name, body in root_paths.items():
        required = json.loads(
            re.search(r"required_parameters\s*=\s*(\[[^\n]*\])", body).group(1)
        )
        role = roles_by_name[name]
        expected_required = ["token_policies", "bind_secret_id"]
        expected_required.extend(
            [
                "token_ttl",
                "token_max_ttl",
                "token_explicit_max_ttl",
                "token_type",
                "secret_id_ttl",
                "secret_id_num_uses",
            ]
        )
        if values["openbao_approle_cli_parameters"][name]["secret_id_bound_cidrs"]:
            expected_required.extend(["secret_id_bound_cidrs", "token_bound_cidrs"])
        assert required == expected_required, name

def test_ansible_converge_writer_renders_exact_machine_bound_batch_parameters(rendered_defaults):
    values, _approles, _policies = rendered_defaults
    name = values["openbao_ansible_converge_writer_approle_name"]
    parameters = values["openbao_approle_cli_parameters"][name]
    ceiling = values["openbao_approle_token_max_ttl"]

    assert (
        values["openbao_approle_cidr_class_map"][name],
        {key: parameters[key] for key in (
            "token_policies",
            "token_type",
            "token_ttl",
            "token_max_ttl",
            "secret_id_ttl",
        )},
        str(parameters["secret_id_num_uses"]),
    ) == (
        "machine",
        {
            "token_policies": "ansible-converge,authelia-signing-writer,seed-writer-dify-secret-id-issuer",
            "token_type": "batch",
            "token_ttl": ceiling,
            "token_max_ttl": ceiling,
            "secret_id_ttl": values["openbao_rotated_domain_secret_id_ttl"],
        },
        "0",
    )
