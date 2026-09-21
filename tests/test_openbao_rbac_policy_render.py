"""The controller-side RBAC policy render must not reference an undefined
Jinja variable in ANY policy template that reads `item`, not only the
Terrakube workspace one.

`_openbao_rendered_policy_pairs` builds its dict via a Jinja `for item in
openbao_manageable_policies` loop declared inline in a `vars:` expression.
That `item` is local to this expression's own render pass -- it is never
part of the task's vars, which is the context `lookup('template', ...)`
hands to the sub-template it renders. Any template referencing `item`
(terrakube-workspace-policy.hcl.j2 via `item.workspace.name`,
kv-capability-policy.hcl.j2 via `item.mode`/`item.subtree`) failed live
with "'item' is undefined", originating inside the sub-template, not the
outer expression -- both cases below reproduce that and fail identically
pre-fix.

This renders the REAL expression out of the task file, with REAL template
files, never a reimplementation.
"""

from pathlib import Path
import unittest

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "08-rbac-policies.yml"
RENDER_TASK = "Render the RBAC policies on the controller"

WORKSPACE_POLICY = {
    "name": "terrakube-iac-platform",
    "template": "terrakube-workspace-policy.hcl.j2",
    "workspace": {"name": "iac-platform", "kv_read": ["iac-platform/foo"]},
}


def _task():
    for t in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if t.get("name") == RENDER_TASK:
            return t
    raise AssertionError(f"task {RENDER_TASK!r} not found in {TASKS}")


def render(policies):
    """Render the real pairs-builder expression from the task file."""
    task = _task()
    pairs_expr = task["vars"]["_openbao_rendered_policy_pairs"]
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "openbao_manageable_policies": policies,
        "openbao_kv_mount": "secret",
        "ansible_managed": "Ansible managed",
    }
    # lookup('template', ...) resolves relative to the role's templates/
    # dir via the search path the task's real loader would use.
    templar._loader.set_basedir(str(ROOT / "roles" / "openbao"))
    return templar.template(trust_as_template(pairs_expr))


class RenderDoesNotFailOnAnItemReferencingTemplate(unittest.TestCase):
    def test_workspace_policy_renders_without_undefined_item(self):
        pairs = render([WORKSPACE_POLICY])
        rendered = {p["key"]: p["value"] for p in pairs}
        self.assertIn("terrakube-iac-platform", rendered)
        self.assertIn("iac-platform", rendered["terrakube-iac-platform"])
        self.assertIn(
            'path "secret/data/iac-platform/foo"', rendered["terrakube-iac-platform"]
        )

    def test_non_workspace_template_referencing_item_also_renders(self):
        # Any template reading `item` hit the same undefined-variable error
        # pre-fix, not only the Terrakube workspace one.
        policy = {
            "name": "write-apps",
            "template": "kv-capability-policy.hcl.j2",
            "mode": "write",
            "subtree": "apps",
        }
        pairs = render([policy])
        self.assertEqual(pairs[0]["key"], "write-apps")
        self.assertIn('path "secret/data/apps/*"', pairs[0]["value"])


if __name__ == "__main__":
    unittest.main()
