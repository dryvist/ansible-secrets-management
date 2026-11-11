"""An empty pr-reconcile bind destroys stored secret_ids by accessor, and only then.

The gates, the absent-role skip and the failure classification are rendered from
the REAL task file (init/10e-pr-reconcile-secret-id-revoke.yml). The destroy command
is rendered and its path is checked, so no other AppRole can be named.
"""

from pathlib import Path
import re
import unittest

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template
import yaml

ROOT = Path(__file__).resolve().parents[1]
REVOKE = ROOT / "roles" / "openbao" / "tasks" / "init" / "10e-pr-reconcile-secret-id-revoke.yml"
INIT = ROOT / "roles" / "openbao" / "tasks" / "init.yml"
ROLE = "pr-reconcile"
ROLE_PATH = "{{ openbao_github_pr_reconcile_approle_name }}"

PRESENT = {"rc": 0, "stderr": ""}
ABSENT = {"rc": 2, "stderr": "No value found at auth/approle/role/pr-reconcile"}
DENIED = {"rc": 2, "stderr": "permission denied"}
LISTING = {"rc": 0, "stderr": "", "stdout": '["acc-1", "acc-2"]'}
NONE_STORED = {"rc": 2, "stderr": "No value found at auth/approle/role/pr-reconcile/secret-id"}


def _tasks():
    return {t["name"]: t for t in yaml.safe_load(REVOKE.read_text(encoding="utf-8"))}


def _templar(variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    return templar


def _gate(task_name, variables):
    when = _tasks()[task_name].get("when", [])
    conditions = [when] if isinstance(when, str) else when
    templar = _templar(variables)
    return all(templar.template(trust_as_template("{{ " + c + " }}")) for c in conditions)


def _variables(cidr="", role_read=PRESENT, reconcile_mode=False,
               accessor_list=LISTING, accessors=None):
    return {
        "openbao_bootstrap_token": "fixture",
        "openbao_reconcile_mode": reconcile_mode,
        "openbao_pr_reconcile_secret_id_cidr": cidr,
        "openbao_pr_reconcile_role_read": role_read,
        "openbao_pr_reconcile_accessor_list": accessor_list,
        "openbao_pr_reconcile_accessors": accessors if accessors is not None else [],
    }


DESTROY = "Destroy each stored pr-reconcile secret_id by accessor while its bind is empty"
LIST = "List the stored pr-reconcile secret_id accessors"
ABSENT_DEBUG = "Report that the pr-reconcile role is absent, so no secret_id can be stored for it"
READ_FAIL = "FAIL -- the pr-reconcile role read failed for a reason other than absence"
LIST_FAIL = "FAIL -- listing the pr-reconcile secret_ids failed for a reason other than none stored"


class DestroyGate(unittest.TestCase):
    def test_destroy_runs_only_when_empty_role_exists_and_privileged(self):
        cases = {
            "empty, present, privileged": (_variables(accessors=["acc-1"]), True),
            "bind set": (_variables(cidr="192.0.2.30/32", accessors=["acc-1"]), False),
            "role absent": (_variables(role_read=ABSENT, accessors=["acc-1"]), False),
            "reconcile mode": (_variables(reconcile_mode=True, accessors=["acc-1"]), False),
            "no accessors stored": (_variables(accessor_list=NONE_STORED, accessors=[]), False),
        }
        for label, (variables, expected) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(_gate(DESTROY, variables), expected)

    def test_list_runs_only_when_empty_and_role_exists(self):
        self.assertTrue(_gate(LIST, _variables()))
        self.assertFalse(_gate(LIST, _variables(cidr="192.0.2.30/32")))
        self.assertFalse(_gate(LIST, _variables(role_read=ABSENT)))
        self.assertFalse(_gate(LIST, _variables(reconcile_mode=True)))


class AbsentRoleSkipsCleanly(unittest.TestCase):
    def test_absent_role_skips_list_and_destroy_and_logs_the_decision(self):
        variables = _variables(role_read=ABSENT)
        self.assertFalse(_gate(LIST, variables))
        self.assertFalse(_gate(DESTROY, variables))
        self.assertTrue(_gate(ABSENT_DEBUG, variables))
        self.assertFalse(_gate(READ_FAIL, variables))


class FailClosedOnOtherErrors(unittest.TestCase):
    def test_denied_role_read_fails_instead_of_skipping(self):
        variables = _variables(role_read=DENIED)
        self.assertTrue(_gate(READ_FAIL, variables))
        self.assertFalse(_gate(ABSENT_DEBUG, variables))
        self.assertFalse(_gate(DESTROY, variables))

    def test_denied_list_fails_instead_of_treating_none_as_stored(self):
        denied_list = {"rc": 2, "stderr": "permission denied", "stdout": ""}
        variables = _variables(accessor_list=denied_list)
        self.assertTrue(_gate(LIST_FAIL, variables))
        self.assertFalse(_gate(LIST_FAIL, _variables(accessor_list=NONE_STORED)))


class OnlyTheRevokeRoleIsNamed(unittest.TestCase):
    def test_every_approle_path_names_pr_reconcile_and_nothing_else(self):
        text = REVOKE.read_text(encoding="utf-8")
        total = text.count("auth/approle/role/")
        named = len(re.findall(re.escape("auth/approle/role/" + ROLE_PATH), text))
        self.assertGreater(total, 0)
        self.assertEqual(named, total)

    def test_no_loop_over_other_approles(self):
        text = REVOKE.read_text(encoding="utf-8")
        self.assertNotIn("openbao_approles", text)
        self.assertNotIn("openbao_manageable_approles", text)
        self.assertNotIn("openbao_secrets_domain_approle_names", text)

    def test_destroy_command_renders_to_the_pr_reconcile_accessor_path(self):
        cmd = _tasks()[DESTROY]["ansible.builtin.command"]["cmd"]
        rendered = _templar({"openbao_github_pr_reconcile_approle_name": ROLE, "item": "acc-1"}) \
            .template(trust_as_template(cmd))
        self.assertEqual(
            " ".join(rendered.split()),
            "bao write auth/approle/role/pr-reconcile/secret-id-accessor/destroy secret_id_accessor=acc-1",
        )


class AccessorCollection(unittest.TestCase):
    def _collect(self, listing):
        raw = _tasks()["Collect the pr-reconcile secret_id accessors to destroy"]["ansible.builtin.set_fact"][
            "openbao_pr_reconcile_accessors"
        ]
        return _templar({"openbao_pr_reconcile_accessor_list": listing}).template(trust_as_template(raw))

    def test_listed_accessors_are_collected(self):
        self.assertEqual(self._collect(LISTING), ["acc-1", "acc-2"])

    def test_nothing_stored_collects_no_accessors(self):
        self.assertEqual(self._collect({"rc": 2, "stdout": ""}), [])


class RevokeIsImportedAfterIssuance(unittest.TestCase):
    def test_init_imports_the_revoke_after_secret_id_issuance(self):
        text = INIT.read_text(encoding="utf-8")
        issue = text.index("init/10b-approle-secret-ids.yml")
        revoke = text.index("init/10e-pr-reconcile-secret-id-revoke.yml")
        self.assertGreater(revoke, issue)


if __name__ == "__main__":
    unittest.main()
