"""The AppRole bound-CIDR reconcile must not report drift for a /32 bind.

OpenBao returns a single-address token_bound_cidrs entry as the bare address
while secret_id_bound_cidrs keeps the /32. This renders the REAL reconcile
task's `vars` (the address-class resolution, the live read and `cidr_drift`)
against both shapes, so an identical bind is not rewritten on every converge
and a real difference still is.
"""

import json
from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles/openbao/tasks/init/10c-approle-ttl-bounds.yml"
TASK_NAME = "Reconcile AppRole TTL and token bounds on existing AppRoles"
NEEDED = ["approle_cidr_class", "approle_bound_cidrs", "live", "desired_bound_cidrs",
          "desired_bound_cidrs_cmp", "cidr_drift"]


def _task():
    for task in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if task.get("name") == TASK_NAME:
            return task
    raise AssertionError(f"task {TASK_NAME!r} not found in {TASKS}")


def _mark_templates(value):
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, dict):
        return {k: _mark_templates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mark_templates(v) for v in value]
    return value


def _render(template, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = _mark_templates(variables)
    return templar.template(trust_as_template(template))


def _drift(row, live, classes):
    """Resolve the task's own vars that cidr_drift depends on, in declaration order."""
    task_vars = _task()["vars"]
    namespace = {
        "item": [row, {"stdout": json.dumps({"data": live})}],
        "openbao_approle_cidr_class_map": {row["name"]: "machine"},
        "openbao_approle_cidr_classes": {"machine": classes},
    }
    for name in [n for n in task_vars if n in NEEDED]:
        namespace[name] = _render(task_vars[name], namespace)
    return namespace["cidr_drift"]


class ApproleCidrDriftTest(unittest.TestCase):
    def test_task_declares_every_input(self):
        self.assertTrue(set(NEEDED) <= set(_task()["vars"]))

    def test_slash32_bind_returned_bare_is_not_drift(self):
        row = {"name": "dispatcher", "secret_id_bound_cidrs": "192.0.2.5/32"}
        live = {"secret_id_bound_cidrs": ["192.0.2.5/32"], "token_bound_cidrs": ["192.0.2.5"]}
        self.assertFalse(_drift(row, live, ""))

    def test_different_slash32_address_is_drift(self):
        row = {"name": "dispatcher", "secret_id_bound_cidrs": "192.0.2.5/32"}
        live = {"secret_id_bound_cidrs": ["192.0.2.5/32"], "token_bound_cidrs": ["192.0.2.6"]}
        self.assertTrue(_drift(row, live, ""))

    def test_class_networks_match_is_not_drift(self):
        row = {"name": "domain"}
        live = {"secret_id_bound_cidrs": ["198.51.100.0/24", "192.0.2.0/24"],
                "token_bound_cidrs": ["192.0.2.0/24", "198.51.100.0/24"]}
        self.assertFalse(_drift(row, live, "192.0.2.0/24, 198.51.100.0/24"))

    def test_class_network_missing_from_token_bind_is_drift(self):
        row = {"name": "domain"}
        live = {"secret_id_bound_cidrs": ["192.0.2.0/24", "198.51.100.0/24"],
                "token_bound_cidrs": ["192.0.2.0/24"]}
        self.assertTrue(_drift(row, live, "192.0.2.0/24, 198.51.100.0/24"))

    def test_non_host_prefix_is_not_stripped(self):
        row = {"name": "domain"}
        live = {"secret_id_bound_cidrs": ["192.0.2.0"], "token_bound_cidrs": ["192.0.2.0"]}
        self.assertTrue(_drift(row, live, "192.0.2.0/24"))


if __name__ == "__main__":
    unittest.main()
