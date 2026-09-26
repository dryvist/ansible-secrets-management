"""Proves the dynamic include_role tag-gating mechanism that
playbooks/site/04a-openbao.yml relies on for `openbao_kv_seed` (and every
other per-phase tag): an `include_role` task's OWN `tags:` decide whether
--tags enters it at all, and once entered, each task loaded from the role is
filtered individually by its own tags -- including the special `always` tag,
which fires whenever the include was entered, regardless of which specific
tag matched it in.

This matters because `ansible-playbook --list-tasks` cannot expand a dynamic
include at all (verified separately, by hand, against the real playbook: it
always prints just the one opaque "Include openbao role" line, with or
without a --tags filter) -- so the only way to prove the INNER filtering
behaviour is to actually run something and watch which tasks execute. Running
the real, heavy openbao role for that would install packages and touch a
real host; tests/tag_scope/fixture_playbook.yml mimics the exact same
structure (play tags, an include_role with its own explicit tag list, and
`always` + two finer phase tags inside the included role) with three
`ansible.builtin.debug` markers instead, so this is a real run against the
real ansible-core in this repo's toolchain, not a description of expected
behaviour.

The second test below is the static half: it asserts the REAL include task
in playbooks/site/04a-openbao.yml lists every phase tag actually declared
anywhere inside the real openbao role (minus `always`, which must never be
one of them -- see the module docstring above for why), so a future phase
tag added inside the role without updating the include's own list would fail
here instead of silently becoming unreachable from site.yml.
"""

from pathlib import Path
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PLAYBOOK = ROOT / "tests" / "tag_scope" / "fixture_playbook.yml"


def _run(tags):
    return subprocess.run(
        ["ansible-playbook", str(FIXTURE_PLAYBOOK), "-c", "local", "--tags", tags],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


class IncludeRoleTagGating(unittest.TestCase):
    def test_unrelated_tag_skips_the_include_entirely(self):
        out = _run("fx_unrelated")
        self.assertNotIn("MARKER:", out)
        self.assertNotIn("Include fixture role", out)

    def test_phase_tag_runs_that_phase_plus_always_only(self):
        out = _run("fx_kv_seed")
        self.assertIn("MARKER:ALWAYS_RAN", out)
        self.assertIn("MARKER:KV_SEED_RAN", out)
        self.assertNotIn("MARKER:RBAC_RAN", out)

    def test_umbrella_tag_runs_every_phase(self):
        out = _run("fx_umbrella")
        self.assertIn("MARKER:ALWAYS_RAN", out)
        self.assertIn("MARKER:KV_SEED_RAN", out)
        self.assertIn("MARKER:RBAC_RAN", out)


def _declared_tags(path):
    tags = set()

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "tags" and isinstance(value, list):
                    tags.update(str(item) for item in value)
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(yaml.safe_load(path.read_text(encoding="utf-8")))
    return tags


class RealIncludeCoversEveryPhaseTag(unittest.TestCase):
    def test_04a_openbao_include_lists_every_phase_tag_the_role_declares(self):
        role_tags = set()
        for path in sorted((ROOT / "roles" / "openbao" / "tasks").rglob("*.yml")):
            role_tags |= _declared_tags(path)
        role_tags.discard("always")

        playbook = yaml.safe_load(
            (ROOT / "playbooks" / "site" / "04a-openbao.yml").read_text(
                encoding="utf-8"
            )
        )
        include_task = playbook[0]["tasks"][0]["block"][0]
        self.assertEqual(include_task["name"], "Include openbao role")
        include_tags = set(include_task.get("tags", []))

        self.assertNotIn(
            "always",
            include_tags,
            "the include must never be tagged `always` -- that would make its "
            "always-tagged prerequisites (install, config render, service "
            "start, cluster probe/init) fire on ANY unrelated --tags run",
        )
        missing = role_tags - include_tags
        self.assertEqual(
            missing,
            set(),
            f"phase tag(s) {sorted(missing)} exist inside roles/openbao/tasks "
            "but are missing from the include's own tags in "
            "playbooks/site/04a-openbao.yml -- a run scoped to one of them "
            "would skip the whole role before ever reaching it",
        )


if __name__ == "__main__":
    unittest.main()
