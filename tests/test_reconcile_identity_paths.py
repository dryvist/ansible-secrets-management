#!/usr/bin/env python3
"""Routine reconciliation uses one issuer-minted credential per run."""

import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
INIT = REPO / "roles" / "openbao" / "tasks" / "init"
RECONCILE = INIT / "02-initialize-cluster.yml"
LIVENESS = INIT / "10a-approle-issuer-liveness.yml"


def _tasks(node):
    if isinstance(node, list):
        for entry in node:
            yield from _tasks(entry)
    elif isinstance(node, dict):
        if "name" in node:
            yield node
        for key in ("block", "rescue", "always"):
            if key in node:
                yield from _tasks(node[key])


class ReconcileIdentityPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reconcile_tasks = {
            task["name"]: task for task in _tasks(yaml.safe_load(RECONCILE.read_text()))
        }
        cls.liveness_tasks = {
            task["name"]: task for task in _tasks(yaml.safe_load(LIVENESS.read_text()))
        }

    def test_routine_reconcile_authenticates_to_issuer_and_mints_target_secret_id(self):
        tasks = self.reconcile_tasks
        issuer_login = tasks["Authenticate to the AppRole issuer for routine reconciliation"]
        self.assertEqual(
            issuer_login["community.hashi_vault.vault_login"]["auth_method"], "approle"
        )
        self.assertEqual(
            issuer_login["community.hashi_vault.vault_login"]["role_id"],
            "{{ openbao_approle_issuer_role_id }}",
        )
        self.assertEqual(
            issuer_login["community.hashi_vault.vault_login"]["secret_id"],
            "{{ openbao_approle_issuer_secret_id }}",
        )

        mint = tasks["Mint a single-use reconcile secret_id through the issuer"]
        self.assertEqual(
            mint["community.hashi_vault.vault_write"]["path"],
            "auth/approle/role/{{ openbao_reconcile_approle_name }}/secret-id",
        )
        self.assertIn("openbao_reconcile_issuer_login.login.auth.client_token", str(mint))

        target_login = tasks["Log in as openbao-reconcile with the single-use secret_id"]
        self.assertIn(
            "openbao_reconcile_role_id_read.data.data.role_id", str(target_login)
        )
        self.assertIn(
            "openbao_reconcile_secret_id_mint.data.data.secret_id", str(target_login)
        )

    def test_target_secret_id_is_destroyed_after_the_login_attempt(self):
        tasks = self.reconcile_tasks
        names = list(tasks)
        login = names.index("Log in as openbao-reconcile with the single-use secret_id")
        destroy = names.index("Destroy the single-use reconcile secret_id by accessor")
        self.assertLess(login, destroy)
        task = tasks["Destroy the single-use reconcile secret_id by accessor"]
        request = task["ansible.builtin.uri"]
        self.assertTrue(request["url"].endswith("secret-id-accessor/destroy"))
        self.assertIn("secret_id_accessor", request["body"])
        self.assertTrue(task["no_log"])

    def test_destroy_tolerates_exactly_the_spent_secret_id_message(self):
        task = self.reconcile_tasks["Destroy the single-use reconcile secret_id by accessor"]
        request = task["ansible.builtin.uri"]
        # 500 passes the status check only so the body can be judged. failed_when
        # replaces the module's status check, so the module failure (any other
        # status, or no response) must be re-raised explicitly.
        self.assertEqual(request["status_code"], [204, 500])
        self.assertTrue(request["return_content"])
        self.assertEqual(task["changed_when"], "openbao_reconcile_destroy.status == 204")
        self.assertEqual(
            " ".join(task["failed_when"].split()),
            "(openbao_reconcile_destroy.failed | default(false)) or "
            "(openbao_reconcile_destroy.status | default(0) == 500 and "
            "'failed to find accessor entry for secret_id_accessor' not in "
            "(openbao_reconcile_destroy.content | default('')))",
        )

    def test_legacy_static_target_pair_and_unsupported_flow_lock_command_are_absent(self):
        defaults = (REPO / "roles/openbao/defaults/main/08a-admin-and-ttls.yml").read_text()
        self.assertRegex(
            defaults,
            r"openbao_reconcile_approle_secret_id_num_uses:\s*1(?:\s|$)",
        )
        tasks = RECONCILE.read_text()
        self.assertNotIn("OPENBAO_APPROLE_OPENBAO_RECONCILE_ROLE_ID", defaults)
        self.assertNotIn("OPENBAO_APPROLE_OPENBAO_RECONCILE_SECRET_ID", defaults)
        self.assertNotIn("openbao_reconcile_role_id:", defaults)
        self.assertNotIn("openbao_reconcile_secret_id:", defaults)
        self.assertNotIn("flow-lock", tasks)
        self.assertNotIn("OPENBAO_RECONCILE_TOKEN", tasks)

    def test_routine_reconcile_attempts_issuer_login_and_fails_on_rejection(self):
        task = self.reconcile_tasks[
            "Authenticate to the AppRole issuer for routine reconciliation"
        ]
        self.assertIn("openbao_provisioning_token | length == 0", task["when"])
        self.assertTrue(task["ignore_errors"])
        failure = self.reconcile_tasks["FAIL — the AppRole issuer could not authenticate"]
        self.assertIn("openbao_reconcile_issuer_login", str(failure["when"]))

    def test_issuer_liveness_mints_and_revokes_even_with_a_provisioning_token(self):
        tasks = self.liveness_tasks
        issuer_login = tasks["Authenticate to approle-issuer for the reconcile liveness probe"]
        mint = tasks["Mint a reconcile liveness secret_id through approle-issuer"]
        destroy = tasks["Revoke the reconcile liveness secret_id by accessor"]
        for task in (issuer_login, mint, destroy):
            self.assertEqual(task["when"], "openbao_status.initialized")
            self.assertTrue(task["no_log"])
            self.assertNotIn("openbao_bootstrap_token", str(task["when"]))
            self.assertNotIn("openbao_provisioning_token", str(task["when"]))
        self.assertIn("/secret-id", mint["community.hashi_vault.vault_write"]["path"])
        self.assertTrue(
            destroy["community.hashi_vault.vault_write"]["path"].endswith(
                "secret-id-accessor/destroy"
            )
        )

    def test_scoped_bootstrap_orders_rbac_before_roles_and_issuer_probe(self):
        init = yaml.safe_load((REPO / "roles/openbao/tasks/init.yml").read_text())
        names = [task.get("name") for task in init]
        rbac = names.index("Render and reconcile the RBAC policies")
        roles = names.index("Declare AppRoles and reconcile their policy and TTL bounds")
        liveness = names.index("Probe the per-call reconcile issuer liveness path")
        probe = names.index("Issue per-call and stored AppRole credentials")
        self.assertLess(rbac, roles)
        self.assertLess(roles, liveness)
        self.assertLess(liveness, probe)
        self.assertIn("openbao_rbac", init[rbac]["tags"])
        self.assertIn("openbao_approle", init[roles]["tags"])
        self.assertIn("openbao_approle", init[liveness]["tags"])
        self.assertIn("openbao_approle", init[probe]["tags"])


if __name__ == "__main__":
    unittest.main()
