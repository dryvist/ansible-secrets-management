"""Regression for the reconcile-mode sys/mounts handling in 03-kv-mounts-and-seed-secrets.yml.

templates/openbao-reconcile-policy.hcl.j2 grants sys/mounts read/list to the
reconcile identity, so 03's own probe (`bao secrets list`) is meant to succeed
under reconcile mode. A denied read there means the DEPLOYED reconcile policy
is stale against the template (05d-reconcile-exclusions.yml excludes that
policy from its own reconciliation, so only a privileged converge refreshes
it) -- not that the grant was never meant to exist. This asserts:

* the hard `fail` on a denied listing only fires OUTSIDE reconcile mode, so a
  stale policy under reconcile mode does not abort init.yml (and therefore
  the AppRole/CIDR reconcile task that runs after this file);
* a loud warning fires INSTEAD, under reconcile mode, on a denied listing;
* the rest of the file's KV-mount and app-secret work is gated on the probe
  having actually succeeded (rc == 0), not on reconcile mode alone -- so it
  runs normally in reconcile mode once the deployed policy is refreshed.
"""

from pathlib import Path
import unittest

import yaml
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "03-kv-mounts-and-seed-secrets.yml"

FAIL_TASK = "Fail with the reason the secrets-engine listing did not succeed"
WARN_TASK = "WARN -- deployed openbao-reconcile policy is stale (sys/mounts denied)"
GATED_BLOCK = "Enable the KV mounts and seed per-app service secrets (probe succeeded)"


def _load():
    return yaml.safe_load(TASKS.read_text(encoding="utf-8"))


class ReconcileModeMountHandling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = {t["name"]: t for t in _load()}
        for name in (FAIL_TASK, WARN_TASK, GATED_BLOCK):
            assert name in cls.tasks, f"{name!r} not found in {TASKS}"
        cls.env = Environment()

    def _fires(self, task_name, **context):
        conds = self.tasks[task_name]["when"]
        conds = [conds] if isinstance(conds, str) else conds
        for c in conds:
            rendered = self.env.from_string("{{ %s }}" % c).render(**context)
            if rendered.strip() != "True":
                return False
        return True

    def test_fail_does_not_fire_under_reconcile_mode(self):
        self.assertFalse(
            self._fires(
                FAIL_TASK,
                openbao_bootstrap_token="tok",
                openbao_reconcile_mode=True,
                openbao_mounts_raw={"rc": 1},
            )
        )

    def test_fail_still_fires_outside_reconcile_mode(self):
        self.assertTrue(
            self._fires(
                FAIL_TASK,
                openbao_bootstrap_token="tok",
                openbao_reconcile_mode=False,
                openbao_mounts_raw={"rc": 1},
            )
        )

    def test_warn_fires_under_reconcile_mode_on_denial(self):
        self.assertTrue(
            self._fires(
                WARN_TASK,
                openbao_bootstrap_token="tok",
                openbao_reconcile_mode=True,
                openbao_mounts_raw={"rc": 1},
            )
        )

    def test_warn_does_not_fire_when_the_probe_succeeded(self):
        self.assertFalse(
            self._fires(
                WARN_TASK,
                openbao_bootstrap_token="tok",
                openbao_reconcile_mode=True,
                openbao_mounts_raw={"rc": 0},
            )
        )

    def test_gated_block_skips_on_a_denied_probe(self):
        self.assertFalse(
            self._fires(
                GATED_BLOCK,
                openbao_bootstrap_token="tok",
                openbao_mounts_raw={"rc": 1},
            )
        )

    def test_gated_block_runs_once_the_probe_succeeds(self):
        self.assertTrue(
            self._fires(
                GATED_BLOCK,
                openbao_bootstrap_token="tok",
                openbao_mounts_raw={"rc": 0},
            )
        )


if __name__ == "__main__":
    unittest.main()
