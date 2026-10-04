"""hindsight_api_key is generated at source in secret/apps/hindsight.

It is declared in openbao_generated_app_secrets.hindsight, so the seed task
mints it only when absent, never overwrites a stored value, and gives it the
generic app-secret length and alphabet. Renders the REAL task expressions.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
SEED = ROOT / "roles/openbao/tasks/seed_generated_app_secret.yml"
GENERATE = "Generate a random value for each field that is not yet stored"
FIELD = "hindsight_api_key"

TUNABLES = yaml.safe_load((DEFAULTS / "01b-app-secret-generation.yml").read_text())
GENERATED = yaml.safe_load((DEFAULTS / "01c-app-secrets-generated.yml").read_text())[
    "openbao_generated_app_secrets"
]


def _task():
    for task in yaml.safe_load(SEED.read_text(encoding="utf-8")):
        if task.get("name") == GENERATE:
            return task
    raise AssertionError(f"task {GENERATE!r} not found")


def _template(expr, stored):
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        **TUNABLES,
        "item": FIELD,
        "openbao_seed_current_data": {FIELD: stored} if stored else {},
        "openbao_seed_desired": {},
    }
    return templar.template(trust_as_template(expr))


def _generates(stored):
    cond = _task()["when"]
    cond = cond if isinstance(cond, list) else [cond]
    return all(bool(_template("{{ " + c + " }}", stored)) for c in cond)


class HindsightApiKeyContract(unittest.TestCase):
    def test_declared_in_the_hindsight_bucket(self):
        self.assertIn(FIELD, GENERATED["hindsight"])

    def test_generated_when_absent(self):
        self.assertTrue(_generates(""))

    def test_a_stored_value_is_never_overwritten(self):
        self.assertFalse(_generates("existing-value"))

    def test_takes_the_generic_app_secret_length_and_alphabet(self):
        # Not a username, router key or secret_key, so the seed task gives it
        # openbao_app_secret_length with upper + numbers and no prefix.
        self.assertFalse(FIELD.endswith(TUNABLES["openbao_app_secret_username_suffix"]))
        self.assertFalse(FIELD.endswith(TUNABLES["openbao_app_secret_router_key_suffix"]))
        self.assertNotEqual(FIELD, "secret_key")


if __name__ == "__main__":
    unittest.main()
