"""Per-kind OpenBao selection uses the role's tasks and native templating."""

from pathlib import Path

import yaml
import pytest
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.loader import test_loader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/openbao"
SELECTOR = ROLE / "tasks/init/select-objects.yml"

# The collection loader resolves the FQCN in a role run; unit rendering uses
# the same collection plugin directly from this checkout.
test_loader.add_directory(str(ROOT / "plugins/test"))


def task(name, path=SELECTOR):
    return next(t for t in yaml.safe_load(path.read_text()) if t.get("name") == name)


def render(expression, variables):
    templar = Templar(loader=DataLoader(), variables=variables)
    return templar.template(trust_as_template(expression))


def condition(expression, variables):
    return render("{{ " + expression + " }}", variables)


def resolve(select, kind="policies", names=("apps", "read-apps", "read-other")):
    variables = {
        "openbao_select": select,
        "openbao_select_kind": kind,
        "openbao_select_candidates": [{"name": n} for n in names],
    }
    expression = task("Match every selector against the declared OpenBao candidates")[
        "ansible.builtin.set_fact"]["openbao_selector_matches"]
    # The unit loader has no installed copy of this checkout's collection.
    expression = expression.replace("dryvist.secrets_management.openbao_glob", "openbao_glob")
    variables["openbao_selector_matches"] = render(expression, variables)
    targets = task("Resolve the selected OpenBao objects for this kind")[
        "ansible.builtin.set_fact"]["openbao_object_targets"]
    return variables["openbao_selector_matches"], render(targets, variables)


def test_selection_defaults_keep_full_set_behavior():
    defaults = yaml.safe_load(
        (ROLE / "defaults/main/00-install-and-node.yml").read_text()
    )
    assert defaults["openbao_select"] == "{{ openbao_select_retired_inputs }}"
    assert defaults["openbao_select_max"] == 25


@pytest.mark.parametrize(("selectors", "expected"), [
    (["apps"], ["apps"]),
    (["read-*"], ["read-apps", "read-other"]),
    (["apps", "read-?pps", "read-apps"], ["apps", "read-apps"]),
    (["read-[a-c]*"], ["read-apps"]),
    (["read-[!a]*"], ["read-other"]),
])
def test_exact_glob_and_overlapping_selectors(selectors, expected):
    _, targets = resolve({"policies": selectors})
    assert [t["name"] for t in targets] == expected


def test_mixed_kinds_resolve_independently_and_omitted_kind_is_empty():
    selection = {"policies": ["read-*"], "approles": ["apps"]}
    assert resolve(selection)[1] == [{"name": "read-apps"}, {"name": "read-other"}]
    assert resolve(selection, "approles")[1] == [{"name": "apps"}]
    assert resolve(selection, "ssh_roles")[1] == []
    assert resolve({})[1] == [{"name": "apps"}, {"name": "read-apps"}, {"name": "read-other"}]


def test_unmatched_selector_fails_and_names_the_entry():
    matches, _ = resolve({"policies": ["apps", "unknown-*"]})
    check = task("Require every OpenBao selector to match a declared object")["ansible.builtin.assert"]
    assert not condition(check["that"][0], {"item": matches[1]})
    assert "unknown-*" in render(check["fail_msg"], {"item": matches[1], "openbao_select_kind": "policies"})


def test_broad_glob_fails_the_resolved_object_cap():
    _, targets = resolve({"policies": ["*"]})
    check = task("Cap the resolved OpenBao selection")["ansible.builtin.assert"]
    assert not condition(check["that"][0], {"_selected_count": len(targets), "openbao_select_max": 2})


def test_globs_preserve_case_and_resolve_each_object_once():
    assert resolve({"policies": ["*"]}, names=("Apps", "apps", "apps"))[1] == [
        {"name": "Apps"}, {"name": "apps"},
    ]
    assert resolve({"policies": ["Apps"]}, names=("Apps", "apps"))[1] == [{"name": "Apps"}]
