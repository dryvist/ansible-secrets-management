"""A converge without OPENBAO_STATIC_SEAL_KEY_ID keeps the nodes' current id.

roles/openbao/templates/openbao.hcl.j2 renders `current_key_id` from
`openbao_seal_key_id`. The seal key itself is already preserved from the
nodes' EnvironmentFile when the environment carries none; the id was not, and
defaulted to the fresh-cluster value, so a converge run without the variable
rewrote every peer's config with an id that never encrypted the stored root
key. Each restart then failed to unseal ("unknown key id") and the cluster
lost quorum.

This pins: the default is empty (never a guessed id), the tasks resolve the
id from the existing server config before the config is rendered, and the
fresh-cluster id is only used behind openbao_allow_fresh_init.
"""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles" / "openbao" / "defaults" / "main" / "00-install-and-node.yml"
TASKS = ROOT / "roles" / "openbao" / "tasks" / "main" / "seal_material.yml"


def _task_names(node) -> list:
    names = []
    if isinstance(node, dict):
        if "name" in node and any(k in node for k in ("ansible.builtin.slurp", "ansible.builtin.set_fact", "ansible.builtin.assert", "ansible.builtin.template")):
            names.append(node["name"])
        for value in node.values():
            names.extend(_task_names(value))
    elif isinstance(node, list):
        for item in node:
            names.extend(_task_names(item))
    return names


class SealKeyIdIsPreserved(unittest.TestCase):
    def test_default_never_guesses_an_id(self):
        defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
        self.assertIn("default('', true)", defaults["openbao_seal_key_id"])
        self.assertNotIn("static-1", defaults["openbao_seal_key_id"])
        self.assertEqual(defaults["openbao_seal_key_id_fresh"], "static-1")

    def test_id_is_resolved_from_the_nodes_before_the_config_renders(self):
        names = _task_names(yaml.safe_load(TASKS.read_text(encoding="utf-8")))
        read = names.index("Read the existing server config from every node for the seal key id")
        take = names.index("Take the seal key id from an existing node config when the environment has none")
        refuse = names.index("Refuse to render a server config without a seal key id")
        render = names.index("Render OpenBao server config")
        self.assertLess(read, take)
        self.assertLess(take, refuse)
        self.assertLess(refuse, render)

    def test_fresh_id_is_gated_behind_fresh_init(self):
        text = TASKS.read_text(encoding="utf-8")
        fresh = text.index("Start a fresh cluster at the initial seal key id")
        gate = text.index("openbao_allow_fresh_init | bool", fresh)
        render = text.index("Render OpenBao server config")
        self.assertLess(gate, render)


if __name__ == "__main__":
    unittest.main()
