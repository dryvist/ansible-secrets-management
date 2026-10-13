"""Every declared OpenBao AppRole has one explicit trust class."""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
CLASSES = {
    "operator-admin",
    "trusted-agent-read",
    "trusted-agent-write",
    "converge-automation",
    "service-runtime",
    "untrusted-sandbox",
}


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


class TestAppRoleTaxonomy(unittest.TestCase):
    def test_every_declared_approle_has_one_identity_class(self):
        variables = {}
        for path in sorted((ROOT / "roles/openbao/defaults/main").glob("*.yml")):
            variables.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})

        roles = _render("{{ openbao_approles }}", variables)
        class_map = _render("{{ openbao_approle_class_map }}", variables)
        unclassified = sorted({role["name"] for role in roles} - set(class_map))
        invalid_classes = {
            name: identity_class
            for name, identity_class in class_map.items()
            if identity_class not in CLASSES
        }

        self.assertEqual(unclassified, [])
        self.assertEqual(invalid_classes, {})
        self.assertEqual(class_map["ai-orchestrator"], "trusted-agent-write")


if __name__ == "__main__":
    unittest.main()
