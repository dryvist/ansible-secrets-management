#!/usr/bin/env python3
"""A stored secret_id can go dead between converges with no create/absence
signal at all -- the existence check in 10-approles.yml only proves the ROLE
is there, not that its currently-deployed secret_id still authenticates. The
converge's own recap (`ok=N changed=0`) reads clean while every domain behind
an expired secret_id sits isolated for the rest of the play (Vikunja 3197).

roles/openbao/tasks/init/10b-approle-secret-ids.yml now probes every existing
AppRole's stored credential and:

  * in EVERY mode, folds a dead name into the set that gets a fresh
    secret_id minted (alongside anything created this run);
  * under the reconcile identity specifically (which cannot mint -- that
    would 403), fails the play loudly instead of silently carrying the dead
    credential forward.

These assertions cover the wiring, not a live OpenBao call:

  1. The probe task exists and never logs the credentials it tests.
  2. A probe result of 400/403 folds that role into openbao_approle_mint_names;
     a clean 200 does not.
  3. The mint task's `when` is driven by that same derived set (i.e. it
     "names" the probe's output, not a re-typed literal).
  4. A routine reconcile run with a dead name present fails loudly; a
     privileged run with the same dead name does not.
"""

import unittest
from pathlib import Path

import yaml
from jinja2 import Environment
from jinja2.nativetypes import NativeEnvironment

INIT = Path(__file__).resolve().parent.parent / "roles" / "openbao" / "tasks" / "init"
# 10b registers the probe results; 10c (included from 10b) classifies them.
TASK_FILES = (INIT / "10b-approle-secret-ids.yml", INIT / "10c-approle-probe-classify.yml")

PROBE = "Probe whether each existing AppRole's stored secret_id still authenticates"
DEAD_NAMES = "Determine which existing AppRoles hold a dead stored secret_id"
MINT_NAMES = "Determine which AppRole names need a secret_id minted this run"
MINT = "Generate newly-created AppRole secret_ids"
RECONCILE_FAIL = "FAIL -- a routine reconcile found a dead stored secret_id it cannot remint"


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


class ApproleSecretIdLiveness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = {
            t["name"]: t for f in TASK_FILES for t in _tasks(yaml.safe_load(f.read_text()))
        }
        for name in (PROBE, DEAD_NAMES, MINT_NAMES, MINT, RECONCILE_FAIL):
            assert name in cls.tasks, f"{name!r} not found in {TASK_FILES}"
        cls.env = Environment()
        # NativeEnvironment gives back the real Python object (a list) for an
        # expression whose template is nothing but that one expression --
        # plain Environment.render() always returns str, which would turn
        # ['observability'] into the *string* "['observability']" and defeat
        # the point of comparing lists below.
        cls.native_env = NativeEnvironment()

    def _render(self, expr, **context):
        return self.env.from_string("{{ %s }}" % expr).render(**context)

    def _render_native(self, template, **context):
        return self.native_env.from_string(template).render(**context)

    def test_the_probe_never_logs_the_credential_it_tests(self):
        self.assertTrue(self.tasks[PROBE].get("no_log"))
        self.assertTrue(
            self.tasks["Look up ambient credentials for a login probe of each existing AppRole"]
            .get("no_log")
        )

    def _dead_names(self, probe_results):
        expr = self.tasks[DEAD_NAMES]["ansible.builtin.set_fact"]["openbao_approle_dead_names"]
        return list(self._render_native(
            expr, openbao_approle_probes={"results": probe_results}
        ))

    def test_a_failed_probe_marks_the_role_dead(self):
        results = [{"item": {"name": "observability"}, "status": 400,
                    "json": {"errors": ["invalid role or secret ID"]}}]
        self.assertEqual(self._dead_names(results), ["observability"])

    def test_a_refused_probe_also_marks_the_role_dead(self):
        results = [{"item": {"name": "observability"}, "status": 403,
                    "json": {"errors": ["invalid role or secret ID"]}}]
        self.assertEqual(self._dead_names(results), ["observability"])

    def test_a_cidr_refused_probe_is_not_evidence_of_death(self):
        results = [{
            "item": {"name": "github-runner"},
            "status": 400,
            "json": {"errors": ["source address unauthorized by CIDR restrictions on the role"]},
        }]
        self.assertEqual(self._dead_names(results), [])

    def test_a_clean_probe_leaves_the_role_alive(self):
        results = [{"item": {"name": "observability"}, "status": 200}]
        self.assertEqual(self._dead_names(results), [])

    def test_a_skipped_probe_is_not_evidence_of_death(self):
        results = [{"item": {"name": "observability"}, "skipped": True}]
        self.assertEqual(self._dead_names(results), [])

    def _mint_names(self, approle_checks_results, dead_names):
        expr = self.tasks[MINT_NAMES]["ansible.builtin.set_fact"]["openbao_approle_mint_names"]
        rendered = self._render_native(
            expr,
            openbao_approle_checks={"results": approle_checks_results},
            openbao_approle_dead_names=dead_names,
        )
        return sorted(rendered)

    def test_a_dead_existing_role_is_folded_into_the_mint_set(self):
        # rc == 0: the role already exists (10-approles.yml's own existence
        # check), so only the liveness probe -- not "missing" -- puts it here.
        checks = [{"item": {"name": "observability"}, "rc": 0}]
        self.assertEqual(
            self._mint_names(checks, dead_names=["observability"]),
            ["observability"],
        )

    def test_a_live_existing_role_is_not_in_the_mint_set(self):
        checks = [{"item": {"name": "observability"}, "rc": 0}]
        self.assertEqual(self._mint_names(checks, dead_names=[]), [])

    def test_a_newly_created_role_is_still_in_the_mint_set(self):
        # rc != 0: absent before this run -- the pre-existing create path,
        # unaffected by the liveness probe (which never ran for it).
        checks = [{"item": {"name": "new-role"}, "rc": 1}]
        self.assertEqual(self._mint_names(checks, dead_names=[]), ["new-role"])

    def test_the_mint_task_when_is_driven_by_the_derived_set_not_a_literal(self):
        conds = self.tasks[MINT]["when"]
        joined = " ".join(conds) if isinstance(conds, list) else conds
        self.assertIn("openbao_approle_mint_names", joined)
        # Renders true for a name the derived set carries, false otherwise --
        # this is the same expression 10b actually evaluates per loop item.
        item_cond = next(c for c in conds if "openbao_approle_mint_names" in c)
        self.assertEqual(
            self._render(
                item_cond,
                item=[{"name": "observability"}],
                openbao_approle_mint_names=["observability"],
            ).strip(),
            "True",
        )
        self.assertEqual(
            self._render(
                item_cond,
                item=[{"name": "observability"}],
                openbao_approle_mint_names=[],
            ).strip(),
            "False",
        )

    def test_reconcile_mode_fails_loudly_on_a_dead_name_instead_of_minting(self):
        fail_conds = self.tasks[RECONCILE_FAIL]["when"]
        self.assertIn("openbao_reconcile_mode | default(false)", fail_conds)
        length_cond = next(c for c in fail_conds if "length" in c)
        self.assertEqual(
            self._render(length_cond, openbao_approle_dead_names=["observability"]).strip(),
            "True",
        )
        self.assertEqual(
            self._render(length_cond, openbao_approle_dead_names=[]).strip(),
            "False",
        )

    def test_mint_still_refuses_reconcile_mode(self):
        # Unchanged from before this file's edit: reconcile cannot mint,
        # 403s if it tries -- the liveness probe only decides WHAT would be
        # minted, never lifts this gate.
        conds = self.tasks[MINT]["when"]
        self.assertIn("not (openbao_reconcile_mode | default(false))", conds)


if __name__ == "__main__":
    unittest.main()
