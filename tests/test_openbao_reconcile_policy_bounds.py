"""Rendered and enforced bounds for the OpenBao reconcile KV ACL."""

import json
import re
import shlex
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml
from ansible.template import trust_as_template

from test_openbao_reconcile_grant_bounds import (
    RECONCILE,
    _allowed_parameters,
    _capabilities,
    _effective_policy_union,
    _render,
    _stanzas,
    _templar,
    _trust,
    rendered_defaults,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_SYNC = ROOT / "roles/openbao/tasks/init/02b-policy-sync.yml"
PATH_COMPONENTS = "^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$"
TASKS_03 = ROOT / "roles/openbao/tasks/init/03-kv-mounts-and-seed-secrets.yml"
TASKS_08A = ROOT / "roles/openbao/tasks/init/08a-roster-live-collisions.yml"
PROMOTE_TASKS = ROOT / "roles/openbao/tasks/promote_app_secret.yml"
GENERATED_SEED_TASKS = ROOT / "roles/openbao/tasks/seed_generated_app_secret.yml"
ROSTER_SEED_TASKS = ROOT / "roles/openbao/tasks/seed_roster_agent_leaf.yml"
ROSTER_OWNER_TASKS = ROOT / "roles/openbao/tasks/seed_roster_agent_leaf_owner.yml"
LEGACY_AGENT_TASKS = ROOT / "roles/openbao/tasks/remove_app_agent_legacy_fields.yml"
ROTATION_TASKS = ROOT / "roles/openbao/tasks/tag_rotation_exempt.yml"

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


def _request(base, token, method, path, body=None):
    headers = {"X-Vault-Token": token}
    if body is not None:
        headers["Content-Type"] = (
            "application/merge-patch+json" if method == "PATCH" else "application/json"
        )
    request = urllib.request.Request(
        f"{base}/v1/{path}",
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def _render_value(values, value, **overrides):
    return _templar(_trust(dict(values, **overrides))).template(_trust(value))


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


def _task_file(path):
    def flatten(tasks):
        for task in tasks or []:
            yield task
            for key in ("block", "rescue", "always"):
                yield from flatten(task.get(key, []))

    return list(flatten(yaml.safe_load(path.read_text(encoding="utf-8"))))


def _named_task(path, name):
    return next(task for task in _task_file(path) if task.get("name") == name)


def _include_details(task):
    modules = {
        module: module.rsplit(".", 1)[-1]
        for module in (
            "include_tasks",
            "ansible.builtin.include_tasks",
            "import_tasks",
            "ansible.builtin.import_tasks",
            "include_role",
            "ansible.builtin.include_role",
        )
    }
    matches = [(module, modules[module]) for module in modules if module in task]
    if not matches:
        return None
    if len(matches) != 1:
        raise AssertionError(
            f"task {task.get('name')!r} has multiple include/import actions"
        )

    module, action = matches[0]
    declaration = task[module]
    if isinstance(declaration, str):
        include = {"name" if action == "include_role" else "file": declaration}
    elif isinstance(declaration, dict):
        include = declaration
    else:
        raise AssertionError(
            f"cannot interpret {action} declaration in task {task.get('name')!r}"
        )

    target_key = "name" if action == "include_role" else "file"
    target = include.get(target_key)
    if not isinstance(target, str) or not target.strip():
        raise AssertionError(
            f"{action} task {task.get('name')!r} has no usable {target_key!r}"
        )

    task_vars = task.get("vars", {})
    if task_vars is None:
        task_vars = {}
    if not isinstance(task_vars, dict):
        raise AssertionError(
            f"vars on {action} task {task.get('name')!r} are not a mapping"
        )
    return action, include, task_vars


def _loop_values(values, expression):
    result = _render_value(values, expression)
    return yaml.safe_load(result) if isinstance(result, str) else result


def _command_text(task, values):
    command = task.get("ansible.builtin.command", {})
    text = command.get("cmd", " ".join(command.get("argv", [])))
    return _render_value(values, text) if text else ""


def _add_kv_command(grants, task, values):
    rendered = _command_text(task, values)
    if not rendered:
        return
    args = shlex.split(" ".join(rendered.split()))
    if args[:2] == ["bao", "kv"] and len(args) > 3:
        if args[2] == "metadata":
            action = args[3]
            target = args[-1]
            mount = next(
                (arg.split("=", 1)[1] for arg in args if arg.startswith("-mount=")),
                None,
            )
            if mount:
                target = f"{mount}/metadata/{target.lstrip('/')}"
            else:
                mount, relative = target.split("/", 1)
                target = f"{mount}/metadata/{relative}"
            capabilities = {"get": {"read"}, "list": {"list"}, "patch": {"patch"}}
        else:
            action = args[2]
            target = args[-1]
            mount, relative = target.split("/", 1)
            target = f"{mount}/data/{relative}"
            capabilities = {
                "get": {"read"},
                "list": {"list"},
                "put": {"create", "update"},
                "patch": {"patch"},
                "delete": {"delete"},
                "destroy": {"delete"},
            }
        grants.setdefault(target, set()).update(capabilities.get(action, set()))
    elif args[:2] in (["bao", "read"], ["bao", "write"]):
        target = next(
            (arg for arg in args[2:] if not arg.startswith("-") and "=" not in arg),
            "",
        )
        if target.endswith("/config"):
            grants.setdefault(target, set()).add(
                "read" if args[1] == "read" else "update"
            )


def _add_kv_uri(grants, task, values):
    uri = task.get("ansible.builtin.uri", {})
    url = uri.get("url", "")
    if "/v1/" not in url:
        return
    path = _render_value(values, url.split("/v1/", 1)[1])
    method = uri.get("method", "GET").upper()
    capabilities = {
        "GET": {"read"},
        "LIST": {"list"},
        "POST": {"create", "update"},
        "PATCH": {"patch"},
        "DELETE": {"delete"},
    }
    grants.setdefault(path, set()).update(capabilities.get(method, set()))


def _add_promoted_paths(grants, values, include_task):
    details = _include_details(include_task)
    if details is None:
        raise AssertionError(f"expected an include/import task: {include_task!r}")
    action, include, include_vars = details
    if action not in ("include_tasks", "import_tasks"):
        return
    filename = include["file"]
    if not filename.endswith("promote_app_secret.yml"):
        return
    loop_var = include_task.get("loop_control", {}).get("loop_var", "item")
    items = _loop_values(values, include_task["loop"]) if "loop" in include_task else [None]
    promote_tasks = _task_file(PROMOTE_TASKS)
    for item in items:
        context = dict(values)
        if item is not None:
            context[loop_var] = item
        for name in ("openbao_promote_app", "openbao_promote_mount", "openbao_promote_path"):
            if name in include_vars:
                context[name] = _render_value(context, include_vars[name])
        for task in promote_tasks:
            for name, expression in task.get("vars", {}).items():
                if name in ("_promote_mount", "_promote_path"):
                    context[name] = _render_value(context, expression)
            _add_kv_command(grants, task, context)
            _add_kv_uri(grants, task, context)


def _add_seeded_paths(grants, values, include_task):
    details = _include_details(include_task)
    if details is None:
        raise AssertionError(f"expected an include/import task: {include_task!r}")
    action, include, include_vars = details

    if action in ("include_tasks", "import_tasks"):
        filename = include["file"]
        if filename.endswith("seed_context7_key.yml"):
            # This legacy migration seed is explicitly disabled in reconcile mode.
            return
        if not filename.endswith(
            ("seed_generated_app_secret.yml", "seed_roster_agent_leaf.yml")
        ):
            if Path(filename).name.startswith("seed_"):
                raise AssertionError(f"unrecognized seed task include: {filename!r}")
            return
        is_roster_seed = filename.endswith("seed_roster_agent_leaf.yml")
        seed_task = _named_task(
            GENERATED_SEED_TASKS, "Call shared generate-if-absent seeding"
        )
        seed_details = _include_details(seed_task)
        if seed_details is None:
            raise AssertionError(
                "shared generated seeding task has no include_role action"
            )
        seed_action, seed_include, seed_vars = seed_details
        if (
            seed_action != "include_role"
            or seed_include["name"] != "dryvist.homelab.openbao_secrets"
            or seed_include.get("tasks_from", "main") != "seed_generated"
        ):
            raise AssertionError(
                "shared generated seeding task has an unexpected include_role"
            )
    elif action == "include_role":
        role_name = include["name"]
        tasks_from = include.get("tasks_from", "main")
        if (
            role_name != "dryvist.homelab.openbao_secrets"
            or tasks_from != "seed_generated"
        ):
            if "seed" in role_name or "seed" in str(tasks_from):
                raise AssertionError(
                    f"cannot interpret seeded include_role {role_name!r}:{tasks_from!r}"
                )
            return
        is_roster_seed = False
        seed_vars = include_vars
    else:
        raise AssertionError(f"cannot interpret seeded path source {action!r}")

    mount_expression = seed_vars.get("openbao_secrets_seed_mount")
    path_expression = seed_vars.get("openbao_secrets_seed_path")
    if not isinstance(mount_expression, str) or not isinstance(path_expression, str):
        raise AssertionError("seed include is missing its mount or path expression")

    loop_var = include_task.get("loop_control", {}).get("loop_var", "item")
    items = (
        _loop_values(values, include_task["loop"])
        if "loop" in include_task
        else [None]
    )
    for item in items:
        context = dict(values)
        if item is not None:
            context[loop_var] = item
        if "openbao_seed_app" in include_vars:
            context["openbao_seed_app"] = _render_value(
                context, include_vars["openbao_seed_app"]
            )
        mount = _render_value(context, mount_expression)
        path = _render_value(context, path_expression)
        grants.setdefault(f"{mount}/data/{path}", set()).update(
            {"create", "read", "update"}
        )
        if is_roster_seed:
            for task in _task_file(ROSTER_SEED_TASKS):
                _add_kv_command(grants, task, context)
                _add_kv_uri(grants, task, context)
            for task in _task_file(ROSTER_OWNER_TASKS):
                _add_kv_uri(grants, task, context)


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


@pytest.mark.parametrize(
    ("key", "valid"),
    [
        ("apps/open-llm/nested_key.v1", True),
        ("apps/bad*key", False),
        ("apps/bad+key", False),
        ('apps/bad"key', False),
        ("apps/foo..bar", False),
        ("/apps/open-llm", False),
        ("apps/open-llm/", False),
        ("apps/bad key", False),
    ],
)
def test_kv_path_assert_accepts_only_literal_nested_components(key, valid):
    tasks = yaml.safe_load(POLICY_SYNC.read_text(encoding="utf-8"))
    guard = next(
        task for task in tasks
        if task.get("name") == "Assert reconcile KV grant keys are literal path components"
    )
    conditions = guard["ansible.builtin.assert"]["that"]
    templar = _templar(_trust({"item": key}))

    results = [
        templar.template(trust_as_template("{{ " + condition + " }}"))
        for condition in conditions
    ]
    assert all(result is True or result == "True" for result in results) is valid


def test_path_guard_covers_template_sources_and_precedes_policy_write():
    tasks = yaml.safe_load(POLICY_SYNC.read_text(encoding="utf-8"))
    names = [task.get("name") for task in tasks]
    collect = next(
        task for task in tasks
        if task.get("name") == "Collect the KV keys used by the reconcile policy"
    )
    seed_paths = next(
        task for task in tasks
        if task.get("name") == "Add the generated seed paths used by the reconcile policy"
    )
    rotation_paths = next(
        task for task in tasks
        if task.get("name")
        == "Add the rotation-exempt mount and path components used by the reconcile policy"
    )
    guard_name = "Assert reconcile KV grant keys are literal path components"
    write_name = "Sync the reconcile policy from the declared set (policy-sync)"

    collection = collect["ansible.builtin.set_fact"]["openbao_reconcile_kv_policy_keys"]
    for variable in (
        "openbao_promoted_app_secrets",
        "openbao_promoted_external_secrets",
        "openbao_promoted_config_values",
        "openbao_seeded_generated_app_secrets",
        "openbao_roster_agent_generated_app_secrets",
        "openbao_caller_gateway_generated_app_secrets",
    ):
        assert variable in collection
    assert "openbao_generated_app_secret_paths" in str(
        seed_paths["ansible.builtin.set_fact"]
    )
    assert "openbao_rotation_exempt" in str(rotation_paths)
    assert names.index(guard_name) < names.index(write_name)


def test_dev_server_enforces_config_and_metadata_parameter_bounds(
    rendered_defaults,
):
    binary = shutil.which("bao")
    assert binary, "the bao binary must be on PATH for the local dev-server ACL check"
    values, _approles, _policies = rendered_defaults
    mount = values["openbao_config_mount"]
    declared_max_versions = str(values["openbao_config_mount_max_versions"])
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [
            binary,
            "server",
            "-dev",
            "-dev-root-token-id=root",
            f"-dev-listen-address=127.0.0.1:{port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                if _request(base, "root", "GET", "sys/health")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(0.5)
        else:
            pytest.fail("the bao dev server did not become healthy")

        status, body = _request(
            base,
            "root",
            "POST",
            f"sys/mounts/{mount}",
            {"type": "kv", "options": {"version": "2"}},
        )
        assert status == 204, body

        policy = _render(RECONCILE, values)
        policy_name = values["openbao_reconcile_policy_name"]
        status, body = _request(
            base,
            "root",
            "PUT",
            f"sys/policies/acl/{policy_name}",
            {"policy": policy},
        )
        assert status == 204, body
        status, body = _request(
            base,
            "root",
            "POST",
            "auth/token/create",
            {"policies": [policy_name]},
        )
        assert status == 200, body
        token = json.loads(body)["auth"]["client_token"]

        path = f"{mount}/config"
        assert _request(base, token, "POST", path, {"max_versions": "1"})[0] == 403
        assert (
            _request(
                base,
                token,
                "POST",
                path,
                {"max_versions": declared_max_versions},
            )[0]
            == 204
        )

        rotation_exempt = _templar(_trust(values)).template(
            _trust(values["openbao_rotation_exempt"])
        )
        metadata_mount, metadata_key = rotation_exempt[0].split(":", 1)
        metadata_path = f"{metadata_mount}/metadata/{metadata_key}"
        status, body = _request(
            base,
            "root",
            "POST",
            f"{metadata_mount}/data/{metadata_key}",
            {"data": {"fixture": "value"}},
        )
        assert status in (200, 204), body

        for forbidden in (
            {"max_versions": 3},
            {"delete_version_after": "24h"},
        ):
            status, body = _request(
                base, token, "PATCH", metadata_path, forbidden
            )
            assert status == 403, (forbidden, status, body)

        status, body = _request(
            base,
            token,
            "PATCH",
            metadata_path,
            {"custom_metadata": {"fixture": "allowed"}},
        )
        assert status in (200, 204), body
    finally:
        server.terminate()
        server.wait(timeout=30)


def test_reconcile_kv_task_paths_have_exact_grants(rendered_defaults):
    values, _approles, _policies = rendered_defaults
    context = dict(
        values,
        tofu_data={"agents": {"review-agent": {}}},
        agent_callers_registry={"review-caller": {}},
    )
    tasks = _task_file(TASKS_03)
    grants = {}

    # The tuned-config read and write use the same mount loop in init/03.
    config_read = _named_task(
        TASKS_03, "Read the current version-retention config of each tuned KV mount"
    )
    config_write = _named_task(
        TASKS_03, "Set KV v2 version retention on the tuned mounts (write-if-changed)"
    )
    for mount in _loop_values(context, config_read["loop"]):
        _add_kv_command(grants, config_read, dict(context, item=mount))
        _add_kv_command(grants, config_write, dict(context, item=(mount, {})))

    # Promotion and generate-if-absent paths come from the concrete task
    # includes and the target mount/path passed to the shared seed role.
    for task in tasks:
        if _include_details(task) is None:
            continue
        _add_promoted_paths(grants, context, task)
        _add_seeded_paths(grants, context, task)

    # The live roster collision probe reads all three candidate metadata paths
    # for each valid roster name, including the legacy ai/<agent> leaf.
    metadata_read = _named_task(
        TASKS_08A, "Read live metadata for roster agent KV paths"
    )
    for item in _loop_values(context, metadata_read["loop"]):
        _add_kv_command(grants, metadata_read, dict(context, item=item))

    readers = _render_value(context, context["openbao_app_agent_tier_readers"])
    for reader in readers:
        reader_context = dict(context, openbao_agent_tier_reader=reader)
        for task in _task_file(LEGACY_AGENT_TASKS):
            if (
                "login_path is defined" in str(task.get("when", ""))
                and "login_path" not in reader
            ):
                continue
            _add_kv_uri(grants, task, reader_context)

    rotation_exempt = _render_value(context, context["openbao_rotation_exempt"])
    for entry in rotation_exempt:
        mount, path = entry.split(":", 1)
        rotation_context = dict(
            context,
            openbao_rotation_exempt_entry=entry,
            openbao_rotation_exempt_mount=mount,
            openbao_rotation_exempt_path=path,
            openbao_rotation_exempt_metadata_path=f"{mount}/metadata/{path}",
        )
        for task in _task_file(ROTATION_TASKS):
            _add_kv_command(grants, task, rotation_context)

    rendered = _render(RECONCILE, context)
    stanzas = dict(_stanzas(rendered))
    for path, capabilities in grants.items():
        assert path in stanzas, f"no exact reconcile stanza covers task KV path {path}"
        assert "*" not in path and "+" not in path, path
        assert capabilities <= set(_capabilities(stanzas[path])), (path, capabilities)


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
