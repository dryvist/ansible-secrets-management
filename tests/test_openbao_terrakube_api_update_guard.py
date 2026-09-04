"""Inventory data must not be able to grant a workspace the control plane.

`terrakube-workspace-policy.hcl.j2` renders three loops. Two prefix every entry
with the KV mount, so inventory can only widen WITHIN that mount:

    path "{{ openbao_kv_mount }}/data/{{ path }}"

The third does not -- it renders the inventory value verbatim:

    {% for path in item.workspace.api_update | default([]) %}
    path "{{ path }}" { capabilities = ["read", "update"] }

Every live value today is an `aws/sts/<role>` path, so nothing is over-granted.
The defect is that nothing MAKES that true: a `sys/policies/acl/...` entry would
render a self-escalation grant for that workspace's job identity, and the
converge would report success.

These render the REAL assert conditions out of the task file, never a
reimplementation -- retyping a template performs its own escaping and can pass
while the real expression fails.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
REL = "roles/openbao/tasks/init/07-ssh-ca-engine.yml"
TASK = "Assert Terrakube api_update paths stay outside the control plane"

DEFAULTS = ROOT / "roles/openbao/defaults/main"

# The real values, read out of role defaults rather than retyped.
FORBIDDEN = yaml.safe_load((DEFAULTS / "06-ai-access-model.yml").read_text())[
    "openbao_ai_forbidden_subtrees"
]
KV_MOUNT = yaml.safe_load((DEFAULTS / "01-kv-hierarchy-and-rbac.yml").read_text())[
    "openbao_kv_mount"
]
LIVE_WORKSPACES = yaml.safe_load(
    (DEFAULTS / "05c-terrakube-and-remaining-domain-names.yml").read_text()
)["openbao_terrakube_workspaces"]


def _task():
    for task in yaml.safe_load((ROOT / REL).read_text(encoding="utf-8")):
        if task.get("name") == TASK:
            return task
    raise AssertionError(f"task {TASK!r} not found in {REL}")


def _passes(workspaces):
    """Render the task's own `vars` chain, then its own `that` conditions.

    The vars are order-dependent (`_tk_api_update_forbidden` consumes
    `_tk_api_update_paths`), so they are resolved in declaration order into the
    namespace the assert then evaluates against -- as Ansible itself does.
    """
    task = _task()
    templar = Templar(loader=DataLoader())
    variables = {
        "openbao_terrakube_workspaces": workspaces,
        "openbao_ai_forbidden_subtrees": FORBIDDEN,
        "openbao_kv_mount": KV_MOUNT,
    }
    for name, expr in task["vars"].items():
        templar.available_variables = variables
        variables[name] = templar.template(trust_as_template(expr))

    templar.available_variables = variables
    return all(
        # A bare YAML boolean is passed through rather than templated. That keeps
        # the negative control honest: disarm the guard to `that: [true]` and this
        # returns True, so only the REFUSED assertions fail -- the real detection
        # -- while the PASSES assertions still pass. Templating the boolean
        # instead raises, turning every case red and hiding which one moved.
        cond
        if isinstance(cond, bool)
        else bool(templar.template(trust_as_template("{{ " + cond + " }}")))
        for cond in task["ansible.builtin.assert"]["that"]
    )


class ApiUpdateGuard(unittest.TestCase):
    def test_the_LIVE_inventory_passes(self):
        # The guard must not disable the behaviour it protects: every real
        # workspace today is legitimate and must keep rendering.
        self.assertTrue(_passes(LIVE_WORKSPACES))

    def test_a_control_plane_path_is_REFUSED(self):
        # The one that matters. `sys/policies/acl/...` with read+update lets the
        # workspace rewrite its own policy; `auth/...` lets it mint an identity.
        for bad in (
            "sys/policies/acl/terrakube-tofu-proxmox",
            "auth/approle/role/admin",
            "infra/anything",
        ):
            with self.subTest(path=bad):
                self.assertFalse(_passes([{"name": "evil", "api_update": [bad]}]))

    def test_the_kv_mount_is_REFUSED(self):
        # Naming the KV mount here bypasses the prefixing the other two loops do,
        # reaching paths kv_read/kv_write could not express.
        self.assertFalse(
            _passes([{"name": "evil", "api_update": [f"{KV_MOUNT}/data/apps/media"]}])
        )

    def test_a_wildcard_is_REFUSED(self):
        # A literal path is auditable; a glob is not, whatever it points at.
        self.assertFalse(_passes([{"name": "evil", "api_update": ["aws/sts/*"]}]))

    def test_a_legitimate_sts_path_PASSES(self):
        self.assertTrue(_passes([{"name": "ok", "api_update": ["aws/sts/tf-proxmox"]}]))

    def test_a_workspace_with_no_api_update_PASSES(self):
        # `selectattr('api_update', 'defined')` must tolerate the common case --
        # most workspaces declare only kv_read.
        self.assertTrue(_passes([{"name": "ok", "kv_read": ["apps/media"]}]))

    def test_one_bad_entry_among_good_ones_is_still_caught(self):
        # A violation must not be masked by legitimate siblings.
        self.assertFalse(
            _passes(
                [
                    {"name": "ok", "api_update": ["aws/sts/tf-proxmox"]},
                    {"name": "evil", "api_update": ["sys/policies/acl/x"]},
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
