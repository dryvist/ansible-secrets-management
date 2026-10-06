"""The CIDR class map must resolve a dual-caller role to its union class.

`flow-lock` is redeemed both interactively from the operator's workstation and
by every automation host during a converge/apply -- a single `machine` or
`workstation` class breaks one caller or the other. The fix is a
`machine_or_workstation` class, derived from the two existing CIDR lists
(never a restated literal), with `flow-lock` overridden onto it.

These render the REAL expressions out of the defaults file, never a
reimplementation of them.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_DIR = ROOT / "roles" / "openbao" / "defaults" / "main"


def _defaults():
    # openbao_approle_cidr_class_map (08b) references
    # openbao_github_write_scope_cidr_classes, declared in
    # 05b-domain-policy-approle-names.yml -- defaults/main/*.yml are merged
    # into one flat namespace at role-load time, so the real variable
    # universe is every file in the directory, not 08b alone.
    merged = {}
    for f in sorted(DEFAULTS_DIR.glob("*.yml")):
        merged.update(yaml.safe_load(f.read_text(encoding="utf-8")) or {})
    return merged


def _mark_templates(value):
    """Recursively mark every string in a loaded YAML structure as a trusted
    template, matching how Ansible treats values sourced from defaults/."""
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, dict):
        return {k: _mark_templates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mark_templates(v) for v in value]
    return value


def _render(key, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = _mark_templates(variables)
    return templar.template(templar.available_variables[key])


class TestCidrClassMap(unittest.TestCase):
    def setUp(self):
        self.variables = _defaults()
        # Minimal role set: one plain role plus flow-lock, standing in for
        # openbao_approles (built elsewhere from openbao_base_approles +
        # generated actor roles -- irrelevant to class resolution).
        self.variables["openbao_approles"] = [
            {"name": "some-machine-role"},
            {"name": "flow-lock"},
            {"name": "approle-issuer"},
            {"name": "openbao-reconcile"},
        ]
        self.variables["openbao_management_cidrs"] = "10.0.1.0/24,10.0.2.0/24"
        self.variables["openbao_workstation_cidrs"] = "10.0.9.10/32"

    def test_union_class_combines_both_lists_once_each(self):
        classes = _render("openbao_approle_cidr_classes", self.variables)
        self.assertEqual(
            set(classes["machine_or_workstation"].split(",")),
            {"10.0.1.0/24", "10.0.2.0/24", "10.0.9.10/32"},
        )

    def test_union_class_dedupes_overlapping_cidrs(self):
        self.variables["openbao_workstation_cidrs"] = "10.0.1.0/24"
        classes = _render("openbao_approle_cidr_classes", self.variables)
        self.assertEqual(classes["machine_or_workstation"].split(","), ["10.0.1.0/24", "10.0.2.0/24"])

    def test_union_class_handles_one_side_empty(self):
        self.variables["openbao_workstation_cidrs"] = ""
        classes = _render("openbao_approle_cidr_classes", self.variables)
        self.assertEqual(classes["machine_or_workstation"], "10.0.1.0/24,10.0.2.0/24")

    def test_flow_lock_resolves_to_the_union_class(self):
        class_map = _render("openbao_approle_cidr_class_map", self.variables)
        self.assertEqual(class_map["flow-lock"], "machine_or_workstation")

    def test_approle_issuer_resolves_to_the_union_class(self):
        class_map = _render("openbao_approle_cidr_class_map", self.variables)
        self.assertEqual(class_map["approle-issuer"], "machine_or_workstation")

    def test_openbao_reconcile_resolves_to_the_union_class(self):
        class_map = _render("openbao_approle_cidr_class_map", self.variables)
        self.assertEqual(class_map["openbao-reconcile"], "machine_or_workstation")

    def test_flow_lock_mints_only_short_lived_single_use_secret_ids(self):
        role = next(
            role
            for role in self.variables["openbao_base_approles_core"]
            if role.get("name") == "{{ openbao_flow_lock_approle_name }}"
        )
        self.assertEqual(
            role["secret_id_ttl"], "{{ openbao_approle_per_call_secret_id_ttl }}"
        )
        self.assertEqual(
            role["secret_id_num_uses"], "{{ openbao_approle_per_call_secret_id_num_uses }}"
        )
        self.assertNotIn(
            "{{ openbao_flow_lock_approle_name }}",
            self.variables["openbao_host_secret_zero_approle_names"],
        )
        self.assertIn(
            "{{ openbao_approle_issuer_approle_name }}",
            self.variables["openbao_host_secret_zero_approle_names"],
        )

    def test_an_unoverridden_role_still_resolves_to_the_default(self):
        class_map = _render("openbao_approle_cidr_class_map", self.variables)
        self.assertEqual(class_map["some-machine-role"], "machine")


if __name__ == "__main__":
    unittest.main()
