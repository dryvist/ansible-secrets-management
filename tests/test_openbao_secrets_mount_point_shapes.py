"""fetch_domain.yml's engine_mount_point must survive all three `paths` shapes.

ansible-core 2.21's "Finalization of task args" resolves a task's own
cross-references (a value in one key referring to another key of the same
item) with raw Python attribute semantics rather than Jinja's lenient
Undefined-on-missing-key behaviour. `item.mount if item is mapping else ...`
worked under 2.20 because a mapping without `mount` rendered Undefined, which
is falsy-but-harmless in most contexts; under 2.21 the same expression raises
`AttributeError: object of type 'dict' has no attribute 'mount'` and aborts
the whole domain's OpenBao read -- confirmed live against
`apps/pve-exporter` declared `{optional: true, path: "apps/pve-exporter"}`
with no `mount` key (blamed to c239fc1d, PR #1691, present since 2026-09-02).

classify_reads.yml's own failure/warning messages used a superficially
similar shape (`item.item.mount | default(...)`) -- checked here too, and
verified NOT to reproduce the failure: a `default()` filter piped after the
attribute access DOES rescue it (proven below by reverting the fetch_domain
fix alone and confirming only the ternary-form test fails, not the
filter-form ones). It was changed to `.get()` anyway for one consistent,
unambiguous pattern with fetch_domain.yml -- not because it was broken.

These render the REAL Jinja expressions out of both task files (never a
reimplementation of them), across all three `paths` entry shapes: a bare
string, a mapping declaring `mount`, and a mapping that omits it.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template


ROOT = Path(__file__).resolve().parents[1]
FETCH_DOMAIN = ROOT / "roles" / "openbao_secrets" / "tasks" / "fetch_domain.yml"
CLASSIFY_READS = ROOT / "roles" / "openbao_secrets" / "tasks" / "classify_reads.yml"

KV_MOUNT = "secret"

# The three shapes a `paths` entry can take, per fetch_domain.yml's own
# comment and openbao_secrets/defaults/main.yml's documented example.
BARE_STRING = "observability/grafana"
MAPPING_WITH_MOUNT = {"path": "apps/homarr", "mount": "custom-mount"}
MAPPING_NO_MOUNT = {"optional": True, "path": "apps/pve-exporter"}


def _find_task(doc, name):
    """Depth-first search for a task by name, recursing into block/rescue/always."""
    for entry in doc:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") == name:
            return entry
        for section in ("block", "rescue", "always"):
            if section in entry:
                found = _find_task(entry[section], name)
                if found is not None:
                    return found
    return None


def _task(path, name):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    task = _find_task(doc, name)
    if task is None:
        raise AssertionError(f"task {name!r} not found in {path}")
    return task


def _render(template_string, item, extra=None):
    # The strings pulled from the task files are already full Jinja
    # templates (each one is YAML `>-` folding a literal `{{ ... }}`, or in
    # classify_reads.yml's case prose with `{{ ... }}` embedded in it) --
    # render them exactly as extracted, never re-wrap in another `{{ }}`.
    templar = Templar(loader=DataLoader())
    templar.available_variables = {
        "item": item,
        "openbao_secrets_kv_mount": KV_MOUNT,
        **(extra or {}),
    }
    return templar.template(trust_as_template(template_string))


def engine_mount_point(item):
    task = _task(FETCH_DOMAIN, "Read each KV path for {{ openbao_domain.name }}")
    expr = task["community.hashi_vault.vault_kv2_get"]["engine_mount_point"]
    return _render(expr.strip(), item)


def kv_path(item):
    task = _task(FETCH_DOMAIN, "Read each KV path for {{ openbao_domain.name }}")
    expr = task["community.hashi_vault.vault_kv2_get"]["path"]
    return _render(expr.strip(), item)


def fail_msg_mount_and_path(item):
    task = _task(
        CLASSIFY_READS, "Fail on any unreadable required KV path for {{ openbao_domain.name }}"
    )
    rendered = _render(
        task["ansible.builtin.fail"]["msg"].strip(),
        {"item": item, "msg": "some read error"},
        extra={"openbao_domain": {"name": "apps"}},
    )
    return rendered


def warn_msg_mount(item):
    task = _task(
        CLASSIFY_READS, "Warn about optional paths that are not seeded for {{ openbao_domain.name }}"
    )
    rendered = _render(
        task["ansible.builtin.debug"]["msg"].strip(),
        {"item": item, "msg": "404 not found"},
        extra={"openbao_domain": {"name": "apps"}},
    )
    return rendered


class EngineMountPointSurvivesEveryShape(unittest.TestCase):
    def test_bare_string_falls_back_to_the_default_mount(self):
        self.assertEqual(engine_mount_point(BARE_STRING), KV_MOUNT)

    def test_mapping_with_mount_uses_its_own_mount(self):
        self.assertEqual(engine_mount_point(MAPPING_WITH_MOUNT), "custom-mount")

    def test_mapping_without_mount_falls_back_without_raising(self):
        # The exact regression case: a mapping declaring `optional`/`path`
        # but no `mount` key at all -- must resolve, never AttributeError.
        self.assertEqual(engine_mount_point(MAPPING_NO_MOUNT), KV_MOUNT)


class PathResolutionUnaffected(unittest.TestCase):
    """The fix only touches engine_mount_point; path resolution must be identical."""

    def test_bare_string_is_its_own_path(self):
        self.assertEqual(kv_path(BARE_STRING), BARE_STRING)

    def test_mapping_uses_its_path_key(self):
        self.assertEqual(kv_path(MAPPING_WITH_MOUNT), "apps/homarr")
        self.assertEqual(kv_path(MAPPING_NO_MOUNT), "apps/pve-exporter")


class ClassifyReadsMessagesSurviveEveryShape(unittest.TestCase):
    """classify_reads.yml's `default()`-piped access never actually raised
    here (verified by reverting only fetch_domain.yml and confirming these
    still pass) -- switched to `.get()` for consistency with fetch_domain.yml,
    not to fix a live bug. These pin that the switch didn't change output."""

    def test_fail_msg_renders_for_a_bare_string_item(self):
        msg = fail_msg_mount_and_path(BARE_STRING)
        self.assertIn(f"{KV_MOUNT}/{BARE_STRING}", msg)

    def test_fail_msg_renders_for_a_mapping_with_mount(self):
        msg = fail_msg_mount_and_path(MAPPING_WITH_MOUNT)
        self.assertIn("custom-mount/apps/homarr", msg)

    def test_fail_msg_renders_for_a_mapping_without_mount(self):
        # The exact regression case, reached via classify_reads.yml this time.
        msg = fail_msg_mount_and_path(MAPPING_NO_MOUNT)
        self.assertIn(f"{KV_MOUNT}/apps/pve-exporter", msg)

    def test_warn_msg_renders_for_a_mapping_without_mount(self):
        # This task's `when:` only ever reaches it for mappings, but the
        # missing-mount case is exactly what this whole fix is about.
        msg = warn_msg_mount(MAPPING_NO_MOUNT)
        self.assertIn(f"{KV_MOUNT}/apps/pve-exporter", msg)

    def test_warn_msg_renders_for_a_mapping_with_mount(self):
        msg = warn_msg_mount(MAPPING_WITH_MOUNT)
        self.assertIn("custom-mount/apps/homarr", msg)


if __name__ == "__main__":
    unittest.main()
