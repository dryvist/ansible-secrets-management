"""A stored router virtual key without the `sk-` prefix must be regenerated.

LiteLLM's /key/generate rejects a caller-supplied virtual key that does not
start with `sk-`. seed_generated_app_secret.yml's generate-if-absent rule
would otherwise leave an unprefixed value stored forever, since nothing has
ever accepted it. Router-key fields (openbao_app_secret_router_key_suffix)
get one carve-out: regenerate when empty OR when stored but missing the
prefix. Every other field keeps the empty-only rule untouched.

Renders the REAL `when` expression, never a reimplementation, the same
pattern test_openbao_denied_vs_absent_writes.py uses.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
REL = "roles/openbao/tasks/seed_generated_app_secret.yml"
TASK = "Generate a random value for each field that is not yet stored"

DEFAULTS = yaml.safe_load(
    (ROOT / "roles/openbao/defaults/main/01b-app-secret-generation.yml").read_text()
)
ROUTER_SUFFIX = DEFAULTS["openbao_app_secret_router_key_suffix"]
ROUTER_PREFIX = DEFAULTS["openbao_app_secret_router_key_prefix"]


def _find(rel, name):
    tasks = yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
    for t in tasks:
        if t.get("name") == name:
            return t
    raise AssertionError(f"task {name!r} not found in {rel}")


def _render(expr, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    return bool(templar.template(trust_as_template("{{ " + expr + " }}")))


def _regenerates(item, stored_value):
    cond = _find(REL, TASK)["when"]
    if not isinstance(cond, list):
        cond = [cond]
    variables = {
        "item": item,
        "openbao_seed_current_data": {item: stored_value} if stored_value else {},
        "openbao_app_secret_router_key_suffix": ROUTER_SUFFIX,
        "openbao_app_secret_router_key_prefix": ROUTER_PREFIX,
    }
    return all(_render(c, variables) for c in cond)


class RouterKeyPrefixRegeneration(unittest.TestCase):
    ROUTER_FIELD = "open_webui" + ROUTER_SUFFIX

    def test_an_empty_router_key_regenerates(self):
        self.assertTrue(_regenerates(self.ROUTER_FIELD, ""))

    def test_an_unprefixed_stored_router_key_regenerates(self):
        # The defect this fixes: a value minted before the sk- rule existed.
        self.assertTrue(_regenerates(self.ROUTER_FIELD, "abc123"))

    def test_a_correctly_prefixed_router_key_is_left_alone(self):
        self.assertFalse(_regenerates(self.ROUTER_FIELD, ROUTER_PREFIX + "abc123"))

    def test_an_empty_non_router_field_still_regenerates(self):
        self.assertTrue(_regenerates("hindsight_db_password", ""))

    def test_a_stored_non_router_field_is_never_touched(self):
        # Must NOT gain the router carve-out just because it holds a value
        # that happens not to start with sk- -- the suffix check must gate it.
        self.assertFalse(_regenerates("hindsight_db_password", "abc123"))


if __name__ == "__main__":
    unittest.main()
