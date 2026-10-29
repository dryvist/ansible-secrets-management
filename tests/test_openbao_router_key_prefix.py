"""Router-key declarations make the shared seed task repair invalid prefixes."""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "roles/openbao/tasks/seed_generated_app_secret.yml"
DEFAULTS = yaml.safe_load(
    (ROOT / "roles/openbao/defaults/main/01b-app-secret-generation.yml").read_text()
)
FIELD_TASK = "Add a shared declaration for each generated app-secret field"


def _field_declaration(name):
    tasks = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    task = next(task for task in tasks if task.get("name") == FIELD_TASK)
    expression = task["ansible.builtin.set_fact"]["openbao_seed_shared_fields"]
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        **DEFAULTS,
        "openbao_seed_shared_fields": [],
        "item": name,
    }
    return templar.template(trust_as_template(expression))[0]


class RouterKeyPrefixRegeneration(unittest.TestCase):
    def test_explicit_contract_router_field_requires_prefix(self):
        field = _field_declaration("router_key")
        self.assertEqual(field["prefix"], "sk-")
        self.assertEqual(field["valid_pattern"], "^sk-")

    def test_second_explicit_contract_router_field_requires_prefix(self):
        field = _field_declaration("claude_ocg_router_key")
        self.assertEqual(field["prefix"], "sk-")
        self.assertEqual(field["valid_pattern"], "^sk-")

    def test_namespaced_router_field_requires_prefix(self):
        field = _field_declaration("open_webui_llm_router_key")
        self.assertEqual(field["prefix"], "sk-")
        self.assertEqual(field["valid_pattern"], "^sk-")

    def test_ordinary_field_has_no_router_repair_pattern(self):
        field = _field_declaration("ordinary_password")
        self.assertEqual(field["prefix"], "")
        self.assertNotIn("valid_pattern", field)


if __name__ == "__main__":
    unittest.main()
