"""openbao_terrakube_base_policies (roles/openbao/defaults/main/07c-base-policies.yml)
generates the nine Terrakube workspace policy entries from
openbao_terrakube_workspaces instead of nine hand-written rows that referenced
it by list position. This proves the derivation reproduces, exactly, what the
nine hardcoded rows it replaced produced: same names, same order, same
template, and the FULL matching workspace object as `workspace` (not just its
name) -- terrakube-workspace-policy.hcl.j2 reads item.workspace.kv_read /
.api_update / .api_read / .github_mint, all of which live only on the whole
object.

Renders the REAL derivation expression from the real defaults file against the
REAL openbao_terrakube_workspaces list, never a reimplementation of either.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
OPENBAO_DEFAULTS_DIR = ROOT / "roles" / "openbao" / "defaults" / "main"
WORKSPACES_FILE = OPENBAO_DEFAULTS_DIR / "05c-terrakube-and-remaining-domain-names.yml"
BASE_POLICIES_FILE = OPENBAO_DEFAULTS_DIR / "07c-base-policies.yml"


def _workspaces():
    data = yaml.safe_load(WORKSPACES_FILE.read_text(encoding="utf-8"))
    return data["openbao_terrakube_workspaces"]


def _derivation_expr():
    data = yaml.safe_load(BASE_POLICIES_FILE.read_text(encoding="utf-8"))
    return data["openbao_terrakube_base_policies"]


def _render_derived_entries(workspaces):
    templar = Templar(loader=DataLoader())
    templar.available_variables = {"openbao_terrakube_workspaces": workspaces}
    # lookup/template resolution is unused by this expression, but set for
    # parity with how the real task file's Templar is constructed.
    templar._loader.set_basedir(str(ROOT / "roles" / "openbao"))
    return templar.template(trust_as_template(_derivation_expr()))


class TerrakubeBasePoliciesDerivation(unittest.TestCase):
    def test_derived_entry_count_matches_workspace_count(self):
        entries = _render_derived_entries(_workspaces())
        self.assertEqual(len(entries), len(_workspaces()))

    def test_derived_names_are_terrakube_prefixed_workspace_names_in_order(self):
        # Ground truth is openbao_terrakube_workspaces itself, never a second,
        # hand-typed copy of its names here -- a copy is exactly the
        # position-coupling this derivation replaced, and re-embeds real
        # workspace names in a test file (disclosure-denylist hit).
        workspaces = _workspaces()
        entries = _render_derived_entries(workspaces)
        names = [e["name"] for e in entries]
        expected = ["terrakube-" + w["name"] for w in workspaces]
        self.assertEqual(names, expected)

    def test_every_entry_uses_the_terrakube_workspace_template(self):
        entries = _render_derived_entries(_workspaces())
        for entry in entries:
            self.assertEqual(entry["template"], "terrakube-workspace-policy.hcl.j2")

    def test_each_entrys_workspace_is_the_full_matching_workspace_object(self):
        workspaces = _workspaces()
        entries = _render_derived_entries(workspaces)
        for entry, workspace in zip(entries, workspaces):
            self.assertEqual(entry["name"], "terrakube-" + workspace["name"])
            self.assertEqual(entry["workspace"], workspace)


if __name__ == "__main__":
    unittest.main()
