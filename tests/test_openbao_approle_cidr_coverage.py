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
IDENTITIES = ROOT / "roles" / "openbao" / "defaults" / "main" / "05l-dify-agent-identities.yml"

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


def _dify_agent_names(defaults, suffix):
    return [
        value
        for name, value in defaults.items()
        if name.startswith("openbao_dify_agent_") and name.endswith(suffix)
    ]


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

    def test_per_tool_roles_use_sandbox_agent_cidrs(self):
        defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
        overrides = defaults["openbao_approle_cidr_class_overrides"]
        for tool in ("zcode", "opencode", "cursor"):
            for tier in ("read", "write"):
                self.assertEqual(overrides[f"sandbox-{tool}-{tier}"], "sandbox_agent")
        identities = yaml.safe_load(IDENTITIES.read_text(encoding="utf-8"))
        for role in _dify_agent_names(identities, "_approle_name"):
            self.assertNotIn(role, overrides)

    def test_dify_roles_are_gated_and_bind_both_credentials_to_the_host_cidr(self):
        defaults = {}
        for path in sorted((ROOT / "roles/openbao/defaults/main").glob("*.yml")):
            defaults.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})

        host_cidr = "192.0.2.10/32"
        defaults["openbao_platform_env"] = {"OPENBAO_DIFY_AGENT_CIDR": host_cidr}
        roles = _render("{{ openbao_dify_agent_approles }}", defaults)
        approle_names = _dify_agent_names(defaults, "_approle_name")
        policy_names = _dify_agent_names(defaults, "_policy_name")
        self.assertEqual(approle_names, policy_names)
        self.assertEqual(
            [role["name"] for role in roles],
            approle_names,
        )
        for role, name in zip(roles, approle_names):
            self.assertEqual(role["policy"], name)
            self.assertEqual(role["secret_id_bound_cidrs"], host_cidr)
            self.assertEqual(role["secret_id_ttl"], "720h")
            self.assertEqual(role["secret_id_num_uses"], 0)
            self.assertEqual(role["token_ttl"], "15m")
            self.assertEqual(role["token_max_ttl"], "15m")
            self.assertFalse(role["manage_secret_id"])

        defaults["openbao_approles"] = roles
        parameters = _render("{{ openbao_approle_cli_parameters }}", defaults)
        for name in approle_names:
            self.assertEqual(parameters[name]["secret_id_bound_cidrs"], host_cidr)
            self.assertEqual(parameters[name]["token_bound_cidrs"], host_cidr)

        defaults["openbao_dify_agent_cidrs"] = ""
        self.assertEqual(_render("{{ openbao_dify_agent_approles }}", defaults), [])

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
        self.assertIn("claude-code-router-key", names)
        self.assertEqual(overrides["claude-code-router-key"], "workstation")
        self.assertEqual(
            sorted(set(overrides) - set(names)),
            [],
            "openbao_approle_cidr_class_overrides names a role that is not declared",
        )

    def test_agent_tier_readers_have_their_declared_source_class(self):
        loaded = {}
        for path in sorted((ROOT / "roles/openbao/defaults/main").glob("*.yml")):
            loaded.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        loaded["openbao_management_cidrs"] = "machine-network"
        loaded["openbao_workstation_cidrs"] = "workstation-network"
        roles = _render("{{ openbao_approles }}", loaded)
        loaded["openbao_approles"] = roles
        class_map = _render("{{ openbao_approle_cidr_class_map }}", loaded)
        cidr_classes = _render("{{ openbao_approle_cidr_classes }}", loaded)
        roles_by_name = {role["name"]: role for role in roles}
        for reader in loaded["openbao_app_agent_tier_readers"]:
            name = f"app-agent-{reader['tier']}"
            self.assertEqual(class_map[name], reader["cidr_class"])
            self.assertEqual(roles_by_name[name]["secret_id_bound_cidrs"],
                             cidr_classes[reader["cidr_class"]])


if __name__ == "__main__":
    unittest.main()
