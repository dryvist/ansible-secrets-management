"""The Azure engine config counts as missing when the read fails or returns an empty client_id."""

import json
from pathlib import Path
import unittest

import yaml
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "04b-azure-engine.yml"
DECIDE_TASK = "Decide whether the Azure engine config is missing"


class AzureConfigMissing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tasks = {t["name"]: t for t in yaml.safe_load(TASKS.read_text(encoding="utf-8"))}
        assert DECIDE_TASK in tasks, f"{DECIDE_TASK!r} not found in {TASKS}"
        cls.expr = tasks[DECIDE_TASK]["ansible.builtin.set_fact"]["openbao_azure_config_missing"]
        cls.env = Environment()
        cls.env.filters["from_json"] = json.loads

    def _missing(self, check):
        return self.env.from_string(self.expr).render(openbao_azure_config_check=check).strip()

    def test_failed_read_is_missing(self):
        self.assertEqual(self._missing({"rc": 2, "stdout": ""}), "True")

    def test_unconfigured_defaults_are_missing(self):
        stdout = json.dumps({"data": {"client_id": "", "tenant_id": ""}})
        self.assertEqual(self._missing({"rc": 0, "stdout": stdout}), "True")

    def test_configured_engine_is_not_missing(self):
        stdout = json.dumps({"data": {"client_id": "abc", "tenant_id": "t"}})
        self.assertEqual(self._missing({"rc": 0, "stdout": stdout}), "False")

    def test_skipped_read_is_missing(self):
        self.assertEqual(self._missing({}), "True")


if __name__ == "__main__":
    unittest.main()
