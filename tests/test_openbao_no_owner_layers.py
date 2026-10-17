"""Prevent per-owner GitHub permission and Terrakube layers from returning."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLES = ROOT / "roles"
DEFAULTS = ROLES / "openbao" / "defaults"
TERRAKUBE = DEFAULTS / "main" / "05c-terrakube-and-remaining-domain-names.yml"

INSTALLATION_ID_LIST = re.compile(r"OPENBAO_GITHUB_[A-Z_]*INSTALLATION_IDS")
GENERATED_READ_ALL_NAME = re.compile(
    r"(?:['\"]name['\"]\s*:\s*)?['\"]read-['\"]\s*~.*?"
    r"~\s*['\"]-all['\"]",
    re.DOTALL,
)
JINJA_LOOP = re.compile(r"{%-?\s*for\b.*?{%-?\s*endfor\s*-?%}", re.DOTALL)


def _text(path):
    return path.read_text(encoding="utf-8", errors="ignore")


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


def test_static_tofu_github_workspace_uses_org_anchored_subject_glob():
    # A plain list, not a template: molecule's verify reads it straight from the file.
    workspaces = yaml.safe_load(_text(TERRAKUBE))["openbao_terrakube_workspaces"]
    assert isinstance(workspaces, list)
    (tofu_github,) = [w for w in workspaces if w.get("name") == "tofu-github"]
    assert tofu_github["bound_subjects_glob"] == ["tofu-github-org-*"]
