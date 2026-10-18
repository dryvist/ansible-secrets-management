"""The workstation OpenTofu role grants only its dedicated Transit paths."""

from pathlib import Path
import re
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
POLICY_TEMPLATE = ROOT / "roles/openbao/templates/tofu-state-workstation-policy.hcl.j2"
POLICY_PATH_BLOCK = re.compile(
    r'path "([^\"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]+)\]\s*\}',
    re.MULTILINE,
)


def _trust(value):
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, list):
        return [_trust(item) for item in value]
    if isinstance(value, dict):
        return {key: _trust(item) for key, item in value.items()}
    return value


def _render(expression, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = _trust(variables)
    return templar.template(trust_as_template(expression))


class TestTofuStateWorkstationAppRole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.variables = {"ansible_managed": "Ansible managed"}
        for path in sorted(DEFAULTS.glob("*.yml")):
            cls.variables.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})

        cls.policy_name = _render(
            "{{ openbao_tofu_state_workstation_policy_name }}", cls.variables
        )
        cls.approle_name = _render(
            "{{ openbao_tofu_state_workstation_approle_name }}", cls.variables
        )
        cls.roles = _render("{{ openbao_approles }}", cls.variables)
        cls.role = next(role for role in cls.roles if role["name"] == cls.approle_name)
        cls.cidr_classes = _render("{{ openbao_approle_cidr_class_map }}", cls.variables)
        cls.excluded_policies = _render(
            "{{ openbao_reconcile_policy_excluded_names }}", cls.variables
        )
        cls.rendered_policy = _render(POLICY_TEMPLATE.read_text(encoding="utf-8"), cls.variables)
        cls.policy_paths = [
            (path, tuple(cap.strip().strip('"') for cap in capabilities.split(",")))
            for path, capabilities in POLICY_PATH_BLOCK.findall(cls.rendered_policy)
        ]

    def test_policy_has_only_the_two_transit_state_paths(self):
        mount = _render("{{ openbao_transit_mount }}", self.variables)
        key = _render("{{ openbao_tofu_state_transit_key }}", self.variables)
        self.assertEqual(
            self.policy_paths,
            [
                (f"{mount}/datakey/plaintext/{key}", ("update",)),
                (f"{mount}/decrypt/{key}", ("update",)),
            ],
        )

    def test_approle_is_single_use_workstation_bound_and_reconciled(self):
        self.assertEqual(self.role["policy"], self.policy_name)
        # Routine reconcile drops roles that set manage_secret_id or per_call issuance.
        self.assertNotIn("manage_secret_id", self.role)
        self.assertNotIn("secret_id_issuance", self.role)
        self.assertEqual(
            self.role["secret_id_ttl"], self.variables["openbao_approle_human_secret_id_ttl"]
        )
        self.assertEqual(self.role["secret_id_num_uses"], 1)
        self.assertEqual(self.cidr_classes[self.approle_name], "workstation")

    def test_policy_is_not_excluded_from_reconcile(self):
        self.assertNotIn(self.policy_name, self.excluded_policies)


if __name__ == "__main__":
    unittest.main()
