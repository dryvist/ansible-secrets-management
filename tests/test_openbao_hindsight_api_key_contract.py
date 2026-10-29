"""hindsight_api_key uses the shared seed contract's generic field settings."""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
SEED = ROOT / "roles/openbao/tasks/seed_generated_app_secret.yml"
FIELD_TASK = "Add a shared declaration for each generated app-secret field"
FIELD = "hindsight_api_key"

TUNABLES = yaml.safe_load((DEFAULTS / "01b-app-secret-generation.yml").read_text())
GENERATED = yaml.safe_load((DEFAULTS / "01c-app-secrets-generated.yml").read_text())[
    "openbao_generated_app_secrets"
]


def _field_declaration(name):
    tasks = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    task = next(task for task in tasks if task.get("name") == FIELD_TASK)
    expression = task["ansible.builtin.set_fact"]["openbao_seed_shared_fields"]
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        **TUNABLES,
        "openbao_seed_shared_fields": [],
        "item": name,
    }
    return templar.template(trust_as_template(expression))[0]


class HindsightApiKeyContract(unittest.TestCase):
    def test_declared_in_the_hindsight_bucket(self):
        self.assertIn(FIELD, GENERATED["hindsight"])

    def test_uses_the_generic_app_secret_length_and_alphabet(self):
        field = _field_declaration(FIELD)
        self.assertEqual(field["length"], TUNABLES["openbao_app_secret_length"])
        self.assertEqual(field["charset"], "alnum")
        self.assertEqual(field["prefix"], "")
        self.assertNotIn("valid_pattern", field)


if __name__ == "__main__":
    unittest.main()
