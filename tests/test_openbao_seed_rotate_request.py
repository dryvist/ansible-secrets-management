"""An on-demand rotate request is parsed to a list and must name only generated fields."""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = yaml.safe_load(
    (ROOT / "roles/openbao/defaults/main/01b-app-secret-generation.yml").read_text(encoding="utf-8")
)
SEED_TASKS = yaml.safe_load(
    (ROOT / "roles/openbao/tasks/init/03-kv-mounts-and-seed-secrets.yml").read_text(encoding="utf-8")
)
ASSERT_NAME = "Require the rotate request to name only generated fields"
APPS = {"hatchet": ["hatchet_db_password", "hatchet_admin_password"]}
ROSTER = {"agent-a": ["agent_a_llm_router_key"]}
GATEWAY = {"gateway-a": ["gateway_a_llm_router_key"]}


def _tasks(tasks):
    for task in tasks or []:
        yield task
        yield from _tasks(task.get("block"))


ASSERT_TASK = next(task for task in _tasks(SEED_TASKS) if task.get("name") == ASSERT_NAME)


def _render(expression, rotate):
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "openbao_seed_rotate_fields": rotate,
        "openbao_seeded_generated_app_secrets": APPS,
        "openbao_roster_agent_generated_app_secrets": ROSTER,
        "openbao_caller_gateway_generated_app_secrets": GATEWAY,
        "openbao_seed_rotate_list": trust_as_template(DEFAULTS["openbao_seed_rotate_list"]),
        "openbao_seed_rotate_known_fields": trust_as_template(DEFAULTS["openbao_seed_rotate_known_fields"]),
    }
    return templar.template(trust_as_template(expression))


def _assert_passes(rotate):
    conditions = ASSERT_TASK["ansible.builtin.assert"]["that"]
    return all(_render("{{ " + condition + " }}", rotate) for condition in conditions)


class RotateRequest(unittest.TestCase):
    def test_key_value_string_form_parses_to_a_list(self):
        rotate = '["hatchet_admin_password"]'
        self.assertEqual(_render("{{ openbao_seed_rotate_list }}", rotate), ["hatchet_admin_password"])
        self.assertTrue(_assert_passes(rotate))

    def test_list_form_passes_through(self):
        rotate = ["agent_a_llm_router_key", "gateway_a_llm_router_key"]
        self.assertEqual(_render("{{ openbao_seed_rotate_list }}", rotate), rotate)
        self.assertTrue(_assert_passes(rotate))

    def test_empty_request_passes(self):
        self.assertTrue(_assert_passes([]))
        self.assertTrue(_assert_passes(""))

    def test_unknown_name_fails_loudly(self):
        self.assertFalse(_assert_passes(["hatchet_admin_pasword"]))
        self.assertFalse(_assert_passes('["not_a_field"]'))

    def test_seed_task_intersects_the_parsed_list(self):
        seed = (ROOT / "roles/openbao/tasks/seed_generated_app_secret.yml").read_text(encoding="utf-8")
        self.assertIn("openbao_seed_rotate_list | intersect(openbao_seed_fields)", seed)
        self.assertNotIn("openbao_seed_rotate_fields | default([])", seed)


if __name__ == "__main__":
    unittest.main()
