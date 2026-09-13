"""Contract for the AppRole source-address coverage gate in 10-approles.yml.

`openbao_approle_cidr_class_map` is built from `openbao_approles` alone, so a
role created from any other list carries no class and is written with nothing
deciding where its secret_id may be redeemed. Two asserts close that:

* every name the converge loops must be a key of the class map, or the run
  fails naming the role before a single write;
* every key of the override map must name a declared role, or the override is
  a silent no-op that leaves the role on the machine default.

Both render the REAL Jinja out of the task and defaults files, never a
reimplementation -- a retyped copy of an expression tests the copy.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "10-approles.yml"
DEFAULTS = ROOT / "roles" / "openbao" / "defaults" / "main" / "08b-cidr-and-unlock.yml"

UNCLASSED_TASK = "Assert every AppRole this run creates has a source-address class"


def _task(name):
    for t in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if t.get("name") == name:
            return t
    raise AssertionError(f"task {name!r} not found in {TASKS}")


def _trust(value):
    """Mark every string as templatable -- ansible-core 2.19+ requires it.

    Recursive because the AppRole rows nest `{{ ..._approle_name }}` inside
    lists of dicts, and an untrusted nested string renders as its own literal.
    """
    if isinstance(value, str):
        return trust_as_template(value)
    if isinstance(value, list):
        return [_trust(v) for v in value]
    if isinstance(value, dict):
        return {k: _trust(v) for k, v in value.items()}
    return value


def _render(expr, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = _trust(variables)
    return templar.template(trust_as_template(expr))


def unclassed(declared, class_map):
    """Render the assert task's own _unclassed expression."""
    expr = _task(UNCLASSED_TASK)["vars"]["_unclassed"]
    return _render(expr, {
        "openbao_manageable_approles": [{"name": n} for n in declared],
        "openbao_approle_cidr_class_map": class_map,
    })


def unknown_overrides(declared, overrides):
    """Render openbao_approle_unknown_cidr_class_overrides from defaults."""
    expr = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))[
        "openbao_approle_unknown_cidr_class_overrides"
    ]
    return _render(expr, {
        "openbao_approle_cidr_class_overrides": overrides,
        "openbao_approles": [{"name": n} for n in declared],
    })


class TestUnclassedRoles(unittest.TestCase):
    def test_role_in_neither_collection_is_flagged(self):
        # `orphan` is created by the converge but reaches the class map from no
        # route at all -- neither a default entry nor an `unbound` override.
        self.assertEqual(
            unclassed(
                ["apps", "public", "orphan"],
                {"apps": "machine", "public": "unbound"},
            ),
            ["orphan"],
        )

    def test_unbound_is_covered_not_uncovered(self):
        # The documented opt-out is a decision written down, so it passes.
        self.assertEqual(unclassed(["public"], {"public": "unbound"}), [])

    def test_fully_covered_set_passes(self):
        self.assertEqual(
            unclassed(["apps", "admin"], {"apps": "machine", "admin": "workstation"}),
            [],
        )


class TestUnknownOverrides(unittest.TestCase):
    def test_override_naming_no_declared_role_is_flagged(self):
        self.assertEqual(
            unknown_overrides(
                ["apps", "admin"],
                {"admin": "workstation", "adnim": "workstation"},
            ),
            ["adnim"],
        )

    def test_every_override_naming_a_declared_role_passes(self):
        self.assertEqual(
            unknown_overrides(["apps", "admin"], {"admin": "workstation"}),
            [],
        )


class TestShippedDeclarationIsClean(unittest.TestCase):
    """The repo's own override map must name only roles it declares."""

    def test_no_unknown_overrides_in_repo(self):
        loaded = {}
        for f in sorted((ROOT / "roles" / "openbao" / "defaults" / "main").glob("*.yml")):
            loaded.update(yaml.safe_load(f.read_text(encoding="utf-8")) or {})
        overrides = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))[
            "openbao_approle_cidr_class_overrides"
        ]
        # Role names are variable references; resolve them off the same defaults.
        # openbao_approles, not openbao_base_approles: that is what the shipped
        # expression in 08 checks against, and the declarations have since been
        # split across several files to stay under the per-file size budget.
        # Reading only the base list reported every role declared in one of the
        # others as an override naming nothing.
        names = _render(
            "{{ openbao_approles | map(attribute='name') | list }}", loaded
        )
        self.assertEqual(
            sorted(set(overrides) - set(names)),
            [],
            "openbao_approle_cidr_class_overrides names a role that is not declared",
        )


if __name__ == "__main__":
    unittest.main()
