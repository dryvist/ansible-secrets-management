"""The Transit mount and OpenTofu state key are declared and provisioned once."""

from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main/01a-kv-hierarchy.yml"
INIT = ROOT / "roles/openbao/tasks/init.yml"
TRANSIT_TASKS = ROOT / "roles/openbao/tasks/init/04c-transit-engine.yml"
TERRAFORM_APPLY_POLICY = ROOT / "roles/openbao/templates/terraform-apply-policy.hcl.j2"
POLICY_PATH_BLOCK = re.compile(
    r'path "([^\"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]+)\]\s*\}',
    re.MULTILINE,
)


def _task(tasks, name):
    return next(task for task in tasks if task.get("name") == name)


class TransitStateKeyIsDeclared(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
        cls.init_tasks = yaml.safe_load(INIT.read_text(encoding="utf-8"))
        cls.transit_tasks = yaml.safe_load(TRANSIT_TASKS.read_text(encoding="utf-8"))

    def test_mount_and_key_names_are_defaults(self):
        self.assertEqual(self.defaults["openbao_transit_mount"], "transit")
        self.assertEqual(
            self.defaults["openbao_transit_mount_description"], "OpenTofu state encryption"
        )
        self.assertEqual(self.defaults["openbao_tofu_state_transit_key"], "tofu-state")

    def test_engine_uses_the_existing_mount_probe_and_enable_pattern(self):
        task = _task(self.transit_tasks, "Enable the Transit engine for OpenTofu state encryption")
        command = task["ansible.builtin.command"]["cmd"]
        self.assertIn("bao secrets enable", command)
        self.assertIn("openbao_transit_mount", command)
        self.assertIn("openbao_transit_mount_description", command)
        self.assertIn("transit", command)
        self.assertTrue(any("openbao_mounts_raw" in condition for condition in task["when"]))

    def test_key_creation_is_configured_and_only_runs_when_absent(self):
        check = _task(self.transit_tasks, "Check whether the OpenTofu state Transit key exists")
        create = _task(self.transit_tasks, "Create the OpenTofu state Transit key if absent")
        check_uri = check["ansible.builtin.uri"]
        create_uri = create["ansible.builtin.uri"]

        self.assertEqual(check_uri["method"], "GET")
        self.assertEqual(check_uri["status_code"], [200, 404])
        self.assertIn("openbao_tofu_state_transit_key", check_uri["url"])
        self.assertEqual(create_uri["method"], "POST")
        self.assertEqual(create_uri["body"], {
            "type": "aes256-gcm96",
            "exportable": False,
            "allow_plaintext_backup": False,
        })
        self.assertIn("openbao_tofu_state_transit_key_check.status == 404", create["when"])
        self.assertTrue(check["no_log"])
        self.assertTrue(create["no_log"])

    def test_transit_provisioning_is_skipped_in_reconcile_mode(self):
        task = _task(
            self.init_tasks,
            "Configure the Transit secrets engine for OpenTofu state encryption",
        )
        self.assertEqual(task["ansible.builtin.import_tasks"], "init/04c-transit-engine.yml")
        self.assertIn("not (openbao_reconcile_mode | default(false))", task["when"])

    def test_terraform_apply_transit_policy_grants_are_exact(self):
        template = TERRAFORM_APPLY_POLICY.read_text(encoding="utf-8")
        grants = []
        for path, capabilities in POLICY_PATH_BLOCK.findall(template):
            rendered_path = path.replace(
                "{{ openbao_transit_mount }}", self.defaults["openbao_transit_mount"]
            ).replace(
                "{{ openbao_tofu_state_transit_key }}",
                self.defaults["openbao_tofu_state_transit_key"],
            )
            if rendered_path.startswith(f'{self.defaults["openbao_transit_mount"]}/'):
                grants.append((path, tuple(re.findall(r'"([^\"]+)"', capabilities))))

        self.assertEqual(
            grants,
            [
                (
                    "{{ openbao_transit_mount }}/datakey/plaintext/{{ openbao_tofu_state_transit_key }}",
                    ("update",),
                ),
                (
                    "{{ openbao_transit_mount }}/decrypt/{{ openbao_tofu_state_transit_key }}",
                    ("update",),
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
