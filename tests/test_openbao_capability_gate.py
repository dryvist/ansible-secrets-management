"""Contract for the reconcile-mode capability gate in 08-rbac-policies.yml.

The gate asks the server what the reconcile identity may actually write, then
refuses the converge if any declared policy is unreachable. It is a HARD fail,
so a wrong answer blocks every routine converge -- which is exactly what
happened: it read only the `data` key of the sys/capabilities-self response,
got an empty dict against a live policy that granted create/read/update on
every path asked about, and reported "grants update on none of these 56".

These render the REAL Jinja expressions out of the task file (never a
reimplementation of them) against each response shape.
"""

import json
from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles" / "openbao" / "tasks" / "init" / "08-rbac-policies.yml"

CAPS = ["create", "read", "update"]
NAMES = ["hermes", "apps", "media"]
PATHS = {f"sys/policies/acl/{n}": CAPS for n in NAMES}
ENVELOPE = {
    "request_id": "abc",
    "lease_id": "",
    "lease_duration": 0,
    "renewable": False,
    "wrap_info": None,
    "warnings": None,
    "auth": None,
}


def _task(name):
    for t in yaml.safe_load(TASKS.read_text(encoding="utf-8")):
        if t.get("name") == name:
            return t
    raise AssertionError(f"task {name!r} not found in {TASKS}")


def resolve_caps(stdout):
    """Render the task file's own openbao_policy_caps expression."""
    task = _task("Resolve what the server said this identity may write")
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "openbao_policy_capabilities": {"stdout": stdout, "rc": 0},
        # the task's own sibling vars, as Ansible would resolve them
        **{k: trust_as_template(v) if isinstance(v, str) else v
           for k, v in task.get("vars", {}).items()},
    }
    # ansible-core 2.19+ only templates strings explicitly marked trusted.
    return templar.template(
        trust_as_template(task["ansible.builtin.set_fact"]["openbao_policy_caps"])
    )


def unwritable(caps, declared):
    task = _task("FAIL -- the reconcile identity cannot manage every declared policy")
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "openbao_policy_caps": caps,
        "openbao_manageable_policies": [{"name": n} for n in declared],
        # the task's own sibling vars, as Ansible would resolve them
        **{k: trust_as_template(v) if isinstance(v, str) else v
           for k, v in task["vars"].items()},
    }
    return templar.template(trust_as_template(task["vars"]["_unwritable"]))


def probe_paths(declared):
    """Render the task file's OWN probe command and return its `paths=` args.

    Loaded from the task file rather than retyped. Retyping is what hid the
    original bug: the replacement was `paths=sys/policies/acl/\\1`, and in
    Python source that literal is ALREADY the unescaped two-character form, so
    a transcribed check silently performs the unescaping step whose absence was
    the defect and passes while production fails.
    """
    task = _task("Ask the server which declared policies this identity may actually write")
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "openbao_manageable_policies": [{"name": n} for n in declared],
        "openbao_api_addr": "http://127.0.0.1:8200",
        "openbao_bootstrap_token": "s.test",
    }
    rendered = templar.template(
        trust_as_template(task["ansible.builtin.command"]["cmd"])
    )
    return [a[len("paths="):] for a in rendered.split() if a.startswith("paths=")]


class CapabilityResolution(unittest.TestCase):
    def test_data_only_response(self):
        body = json.dumps(dict(ENVELOPE, data=PATHS))
        self.assertEqual(resolve_caps(body), PATHS)

    def test_top_level_only_response(self):
        # The shape that broke it: no `data` wrapper at all. Reading only
        # `data` yielded {} here, which the gate then called "denied".
        body = json.dumps(dict(ENVELOPE, **PATHS))
        self.assertEqual(resolve_caps(body), PATHS)

    def test_both_places_response(self):
        body = json.dumps(dict(ENVELOPE, data=PATHS, **PATHS))
        self.assertEqual(resolve_caps(body), PATHS)

    def test_envelope_keys_are_never_mistaken_for_paths(self):
        body = json.dumps(dict(ENVELOPE, data=PATHS))
        self.assertEqual(resolve_caps(body), PATHS)

    def test_non_path_response_fields_cannot_collide_with_a_policy_name(self):
        # The response also carries capabilities/mount_* fields, and future
        # ones would join them. A stray key surviving resolution is compared
        # against declared policy NAMES later (the prefix is stripped there,
        # not filtered), so a collision would mark a policy writable that is
        # not -- a false green in the guard built to prevent one.
        noise = {
            "capabilities": CAPS,
            "mount_type": "system",
            "mount_class": "secret",
            "some_future_field": CAPS,
        }
        body = json.dumps(dict(ENVELOPE, data=PATHS, **noise))
        self.assertEqual(resolve_caps(body), PATHS)

    def test_an_envelope_only_response_resolves_empty(self):
        # Must reach the "probe returned nothing usable" arm, never be read as
        # a denial of everything.
        self.assertEqual(resolve_caps(json.dumps(ENVELOPE)), {})


class UnwritableVerdict(unittest.TestCase):
    def test_granted_policies_are_not_reported_unwritable(self):
        caps = resolve_caps(json.dumps(dict(ENVELOPE, **PATHS)))
        self.assertEqual(unwritable(caps, NAMES), [])

    def test_a_genuinely_missing_grant_is_still_caught(self):
        # The gate must keep catching the real drift it exists for.
        caps = resolve_caps(json.dumps(dict(ENVELOPE, **PATHS)))
        self.assertEqual(unwritable(caps, NAMES + ["brand-new"]), ["brand-new"])

    def test_read_only_grant_counts_as_unwritable(self):
        partial = {"sys/policies/acl/hermes": ["read"]}
        caps = resolve_caps(json.dumps(dict(ENVELOPE, **partial)))
        self.assertEqual(unwritable(caps, ["hermes"]), ["hermes"])


class ProbeAsksAboutRealPaths(unittest.TestCase):
    """The probe must name every declared policy, once, at its real path.

    The gate reported "grants update on none of these 56" against a live policy
    that granted create/read/update on all of them. Cause: a regex
    backreference that did not survive YAML -> Jinja -> shlex.split, so all 60
    paths rendered as the single literal `sys/policies/acl/1` -- a policy that
    does not exist, which the server answered `deny`. The probe had never once
    asked about a real path, and every failure arm downstream was reasoning
    about an answer to a question nobody asked.
    """

    def test_every_declared_policy_is_asked_about_at_its_real_path(self):
        self.assertEqual(
            probe_paths(NAMES),
            [f"sys/policies/acl/{n}" for n in NAMES],
        )

    def test_the_backreference_collapse_cannot_return(self):
        # The exact regression: N declared policies collapsing to one literal.
        paths = probe_paths(NAMES)
        self.assertNotIn("sys/policies/acl/1", paths)
        self.assertEqual(len(set(paths)), len(NAMES))

    def test_a_policy_name_is_never_mangled(self):
        # Names carrying regex-significant characters must pass through whole;
        # the prefix is added by matching '^', so there is nothing to escape.
        odd = ["ai-api-key-openai", "read.platform", "a+b"]
        self.assertEqual(
            probe_paths(odd),
            [f"sys/policies/acl/{n}" for n in odd],
        )


if __name__ == "__main__":
    unittest.main()
