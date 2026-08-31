"""The RBAC write must be a no-op when the server already holds the policy.

The write fires when the stored text differs from the rendered text, so it is
idempotent only if those two can ever compare equal. They could not, for two
independent reasons:

  * `bao policy read -format=json` returns {"policy": ...} at TOP LEVEL. The
    expression read `.data.policy`, which does not exist, so every entry
    resolved to '' and every policy looked changed on every converge.
  * The server appends a trailing newline on write, so even with the correct
    key the stored text is the rendered text plus "\\n", and an exact !=
    is always true.

Either defect alone rewrites every policy on every run while the task honestly
reports "changed" -- so fixing one without the other looks like a fix and
changes nothing. Both are asserted here.

Measured live before the fix: rendered 475 bytes, stored 476, differing only in
that newline.

These render the REAL expressions out of the task file, never a reimplementation.
"""

from pathlib import Path
import json
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "08-rbac-policies.yml"
EXISTING_TASK = "Build the existing RBAC policy content map"
WRITE_TASK = "Write the RBAC policies that are missing or changed"

# What the CLI actually returns: no `data` envelope, trailing newline appended.
POLICY_BODY = 'path "sys/policies/acl/apps" {\n  capabilities = ["read"]\n}\n'
SERVER_STORED = POLICY_BODY + "\n"


def _task(name):
    for t in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if t.get("name") == name:
            return t
    raise AssertionError(f"task {name!r} not found in {TASKS}")


def _render(expr, variables, wrap=False):
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    return templar.template(
        trust_as_template("{{ " + expr + " }}" if wrap else expr)
    )


def existing_map(name, stdout):
    """Render the existing-map expression for one read result."""
    expr = _task(EXISTING_TASK)["ansible.builtin.set_fact"][
        "openbao_existing_policy_map"
    ]
    return _render(
        expr,
        {
            "openbao_existing_policy_map": {},
            "item": {"item": {"name": name}, "stdout": stdout, "rc": 0},
        },
    )


def write_fires(name, existing, rendered):
    """Render the write task's own content-comparison condition."""
    cond = [
        c for c in _task(WRITE_TASK)["when"]
        if "openbao_rendered_policy_map" in str(c)
    ]
    assert len(cond) == 1, f"expected one comparison condition, got {cond}"
    return _render(
        cond[0],
        {
            "item": {"name": name},
            "openbao_policies_raw": {"stdout": json.dumps([name])},
            "openbao_existing_policy_map": existing,
            "openbao_rendered_policy_map": rendered,
        },
        wrap=True,
    )


class ExistingMapReadsTheRightKey(unittest.TestCase):
    def test_top_level_policy_key_is_read(self):
        got = existing_map("apps", json.dumps({"policy": SERVER_STORED}))
        self.assertEqual(got["apps"], POLICY_BODY.strip())

    def test_a_data_envelope_is_NOT_what_the_cli_returns(self):
        # Guards the original defect directly: if the expression goes back to
        # `.data.policy`, this shape is what it would need, and the real CLI
        # never sends it. An empty result here means every policy looks changed.
        got = existing_map("apps", json.dumps({"data": {"policy": SERVER_STORED}}))
        self.assertEqual(got["apps"], "", "sanity: no top-level policy key")


class WriteIsIdempotent(unittest.TestCase):
    def test_unchanged_policy_does_NOT_fire_the_write(self):
        # The whole point: stored == rendered + "\n" must compare equal.
        existing = existing_map("apps", json.dumps({"policy": SERVER_STORED}))
        self.assertFalse(
            write_fires("apps", existing, {"apps": POLICY_BODY.strip()})
        )

    def test_a_genuinely_changed_policy_still_fires_the_write(self):
        # The guard must not disable the behaviour it protects.
        existing = existing_map("apps", json.dumps({"policy": SERVER_STORED}))
        self.assertTrue(
            write_fires("apps", existing, {"apps": 'path "other" {}'})
        )

    def test_trailing_whitespace_alone_is_never_a_change(self):
        existing = existing_map(
            "apps", json.dumps({"policy": POLICY_BODY + "\n\n  "})
        )
        self.assertFalse(
            write_fires("apps", existing, {"apps": POLICY_BODY.strip()})
        )


if __name__ == "__main__":
    unittest.main()
