"""Prevent per-owner GitHub permission and Terrakube layers from returning."""

import ast
import re
from pathlib import Path

import yaml
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
ROLES = ROOT / "roles"
DEFAULTS = ROLES / "openbao" / "defaults"
TERRAKUBE = DEFAULTS / "main" / "05c-terrakube-and-remaining-domain-names.yml"
RETIRED = DEFAULTS / "main" / "07c-approle-undeclared-exceptions.yml"
RETIRE_TASKS = ROLES / "openbao" / "tasks" / "init" / "09f-retired-terrakube-jwt-roles.yml"
JWT_TASKS = ROLES / "openbao" / "tasks" / "init" / "09-auth-methods-and-terrakube-jwt.yml"

INSTALLATION_ID_LIST = re.compile(r"OPENBAO_GITHUB_[A-Z_]*INSTALLATION_IDS")
GENERATED_READ_ALL_NAME = re.compile(
    r"(?:['\"]name['\"]\s*:\s*)?['\"]read-['\"]\s*~.*?"
    r"~\s*['\"]-all['\"]",
    re.DOTALL,
)
JINJA_LOOP = re.compile(r"{%-?\s*for\b.*?{%-?\s*endfor\s*-?%}", re.DOTALL)


def _text(path):
    return path.read_text(encoding="utf-8", errors="ignore")


def _render_jinja_list(expression, **variables):
    environment = Environment()
    environment.filters["regex_replace"] = (
        lambda value, pattern, replacement: re.sub(pattern, replacement, value)
    )
    return ast.literal_eval(environment.from_string(expression).render(**variables))


def test_roles_have_no_github_installation_id_lists():
    matches = [
        str(path.relative_to(ROOT))
        for path in ROLES.rglob("*")
        if path.is_file() and INSTALLATION_ID_LIST.search(_text(path))
    ]
    assert not matches, f"installation-ID list env names remain in roles: {matches}"


def test_defaults_do_not_generate_read_owner_all_permission_sets():
    matches = []
    for path in DEFAULTS.rglob("*.yml"):
        loops = JINJA_LOOP.findall(_text(path))
        if any(GENERATED_READ_ALL_NAME.search(block) for block in loops):
            matches.append(str(path.relative_to(ROOT)))
    assert not matches, f"generated read-<owner>-all permission sets remain: {matches}"


def test_terrakube_does_not_append_per_owner_github_workspaces():
    text = _text(TERRAKUBE)
    assert not re.search(
        r"{%-?\s*for\b.*?_workspaces\.append\(\s*\{\s*['\"]name['\"]\s*:\s*"
        r"['\"]tofu-github-['\"]\s*~",
        text,
        re.DOTALL,
    )


def test_tofu_github_workspace_does_not_declare_per_owner_roles():
    defaults = yaml.safe_load(_text(TERRAKUBE))
    workspaces = defaults["openbao_terrakube_workspaces"]
    assert isinstance(workspaces, list)
    (tofu_github,) = [w for w in workspaces if w.get("name") == "tofu-github"]
    assert not any(key.startswith("bound_subjects") for key in tofu_github)
    assert "tofu-github-org-" not in _text(TERRAKUBE)


def test_tofu_github_subject_claims_include_exact_and_glob_subjects():
    defaults = yaml.safe_load(_text(TERRAKUBE))
    task_list = yaml.safe_load(_text(JWT_TASKS))
    reconcile = next(
        task
        for task in task_list
        if task.get("name") == "Reconcile Terrakube workspace JWT roles"
    )
    exact_subject = (
        f"organization:{defaults['openbao_terrakube_organization']}"
        ":workspace:tofu-github"
    )
    claims = _render_jinja_list(
        reconcile["vars"]["_workspace_sub_claims"],
        _workspace_sub_claim=exact_subject,
        item=({"name": "tofu-github"}, {}),
    )
    assert claims == [exact_subject, f"{exact_subject}-*"]


def test_terrakube_claims_type_uses_glob_only_for_tofu_github():
    assert "glob" not in _text(TERRAKUBE).lower()
    task_list = yaml.safe_load(_text(JWT_TASKS))
    reconcile = next(
        task
        for task in task_list
        if task.get("name") == "Reconcile Terrakube workspace JWT roles"
    )
    type_expression = reconcile["vars"]["_workspace_bound_claims_type"]
    type_template = Environment().from_string(type_expression)
    assert type_template.render(item=({"name": "tofu-github"}, {})) == "glob"
    assert type_template.render(item=({"name": "iac-platform"}, {})) == "string"
    assert "!= _workspace_bound_claims_type" in _text(JWT_TASKS)


def test_retired_terrakube_prefix_spares_the_shared_tofu_github_identity():
    prefix = yaml.safe_load(_text(RETIRED))["openbao_retired_terrakube_prefix"]
    assert prefix == "terrakube-tofu-github-"
    live = ["terrakube-tofu-github", "terrakube-tofu-github-owner-a", "terrakube-iac-platform"]
    assert [name for name in live if re.match("^" + re.escape(prefix), name)] == [
        "terrakube-tofu-github-owner-a"
    ]
    assert "openbao_retired_terrakube_prefix | regex_escape" in _text(RETIRE_TASKS)
