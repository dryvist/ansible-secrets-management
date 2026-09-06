"""A DENIED read must never reach a privileged write.

Five instances of this defect were fixed in #1641/#1653/#1656/#1659/#1661. These
are the remaining six, and two of them are DESTRUCTIVE rather than merely loud:

  * openbao_secrets/tasks/publish.yml -- the read-before-write exists so a
    single-field publish cannot drop siblings. A denied read leaves `.secret`
    undefined, `default({}, true)` contributes no siblings, and the anti-clobber
    merge BECOMES the clobber. Authelia's storage encryption key travels this
    path and is unrecoverable if lost.
  * openbao/tasks/seed_generated_app_secret.yml -- a denied read collapses to
    {}, so EVERY declared field looks unset, fresh values are minted for all of
    them, and the write rotates live credentials the file's own header promises
    are "never rewritten".

Both the 403 case and the 404 case are asserted for every site. Testing only the
404 path passes *because of* the bug -- absence was always tolerated correctly;
it is the denial that was conflated with it.

These render the REAL expressions out of the task files, never a reimplementation
-- retyping a template performs its own escaping and can pass while the real
expression fails.

The upstream site where the false "absent" is minted, openbao_secrets' KV read
gate, is not covered here: it lives in its own task file and is exercised end to
end against synthetic results by tests/openbao_secrets/verify_read_gate.yml.
"""

from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]

# The real markers, read out of the role defaults rather than retyped.
BAO_ABSENT = yaml.safe_load(
    (ROOT / "roles/openbao/defaults/main/01-kv-hierarchy-and-rbac.yml").read_text()
)["openbao_absent_stderr_marker"]
MOD_ABSENT = yaml.safe_load(
    (ROOT / "roles/openbao_secrets/defaults/main.yml").read_text()
)["openbao_secrets_absent_msg_marker"]

# What the two tools actually emit, taken from the CLI and from
# community.hashi_vault's vault_kv2_get source.
CLI_ABSENT = f"{BAO_ABSENT} at secret/apps/nope\n"
CLI_DENIED = "Code: 403. Errors:\n\n* 1 error occurred:\n\t* permission denied\n"
MOD_ABSENT_MSG = (
    f"{MOD_ABSENT} ['apps/nope'] with secret version 'latest'. "
    "Check the path or secret version."
)
MOD_DENIED_MSG = "Forbidden: Permission Denied to path ['apps/nope']."


def _tasks(rel):
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def _find(rel, name):
    def walk(items):
        for t in items or []:
            if t.get("name") == name:
                return t
            for key in ("block", "rescue", "always"):
                if key in t:
                    hit = walk(t[key])
                    if hit:
                        return hit
        return None

    hit = walk(_tasks(rel))
    if hit is None:
        raise AssertionError(f"task {name!r} not found in {rel}")
    return hit


def _render(expr, variables, wrap=True):
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    text = "{{ " + expr + " }}" if wrap else expr
    return templar.template(trust_as_template(text))


def _all(conds, variables):
    """Render a `failed_when` / `when` list. Ansible ANDs the elements.

    A bare YAML boolean is passed through rather than templated. That keeps the
    negative control honest: with the pre-fix `failed_when: false` this returns
    False, so the DENIED assertions fail (the real detection) while the absent
    and success assertions still pass -- absence was always tolerated correctly,
    and it is only the denial that was conflated with it. Templating the boolean
    instead would raise, turning every case red and hiding which one changed.
    """
    if not isinstance(conds, list):
        conds = [conds]
    return all(
        c if isinstance(c, bool) else bool(_render(c, variables)) for c in conds
    )


def _cli(rc, stderr, stdout="{}"):
    return {"rc": rc, "stderr": stderr, "stdout": stdout}


class SeedGeneratedAppSecret(unittest.TestCase):
    """A denied read must not mint fresh values over live credentials."""

    REL = "roles/openbao/tasks/seed_generated_app_secret.yml"
    TASK = "Read the app secret's currently-stored fields"

    def _fails(self, result):
        return _all(
            _find(self.REL, self.TASK)["failed_when"],
            {
                "openbao_seed_current": result,
                "openbao_absent_stderr_marker": BAO_ABSENT,
            },
        )

    def test_a_DENIED_read_fails_the_task(self):
        # The one that matters. Before the fix this was swallowed, every field
        # looked unset, and the write rotated the live secret.
        self.assertTrue(self._fails(_cli(2, CLI_DENIED)))

    def test_a_genuinely_absent_path_does_NOT_fail(self):
        # Generate-if-absent must still work on a first converge.
        self.assertFalse(self._fails(_cli(2, CLI_ABSENT)))

    def test_a_successful_read_does_NOT_fail(self):
        self.assertFalse(self._fails(_cli(0, "")))

    def test_an_unreachable_server_fails_rather_than_seeding(self):
        # Neither absent nor denied -- anything unrecognised must fail closed.
        self.assertTrue(self._fails(_cli(1, "connection refused")))


class PromoteAppSecret(unittest.TestCase):
    """A denied read must not wipe the siblings the merge promises to keep."""

    REL = "roles/openbao/tasks/promote_app_secret.yml"
    TASK = "Read the app's currently-stored secret fields"

    def _fails(self, result):
        return _all(
            _find(self.REL, self.TASK)["failed_when"],
            {
                "openbao_promote_current": result,
                "openbao_absent_stderr_marker": BAO_ABSENT,
            },
        )

    def test_a_DENIED_read_fails_the_task(self):
        self.assertTrue(self._fails(_cli(2, CLI_DENIED)))

    def test_a_genuinely_absent_path_does_NOT_fail(self):
        self.assertFalse(self._fails(_cli(2, CLI_ABSENT)))

    def test_a_successful_read_does_NOT_fail(self):
        self.assertFalse(self._fails(_cli(0, "")))


class PublishReadBeforeWrite(unittest.TestCase):
    """The highest-consequence site: the anti-clobber merge must not clobber."""

    # The read itself registers unconditionally: a bare `msg` is not injected
    # into `failed_when` on ansible-core 2.21, so the classification is the
    # separate task below it and that is what carries the discrimination.
    REL = "roles/openbao_secrets/tasks/publish.yml"
    TASK = "Fail unless the read-before-write found the path simply absent"

    def _fails(self, result):
        return _all(
            _find(self.REL, self.TASK)["when"],
            {
                "openbao_secrets_publish_existing": result,
                "openbao_secrets_absent_msg_marker": MOD_ABSENT,
            },
        )

    def test_a_DENIED_read_fails_rather_than_clobbering(self):
        self.assertTrue(self._fails({"failed": True, "msg": MOD_DENIED_MSG}))

    def test_a_not_yet_seeded_path_does_NOT_fail(self):
        # A first publish must still be able to create the path.
        self.assertFalse(self._fails({"failed": True, "msg": MOD_ABSENT_MSG}))

    def test_a_successful_read_does_NOT_fail(self):
        self.assertFalse(self._fails({"failed": False, "secret": {"a": "b"}}))


class KvRetentionProbe(unittest.TestCase):
    """A denied config read must not fire a privileged retention write."""

    REL = "roles/openbao/tasks/init/03-kv-mounts-and-seed-secrets.yml"
    FAIL_TASK = 'FAIL -- the retention read was DENIED, so "unset" cannot be concluded'
    WRITE_TASK = "Set KV v2 version retention on the tuned mounts (write-if-changed)"

    def _denied(self, results):
        return _render(
            _find(self.REL, self.FAIL_TASK)["vars"]["_denied"],
            {
                "openbao_kv_config_checks": {"results": results},
                "openbao_absent_stderr_marker": BAO_ABSENT,
            },
            wrap=False,
        )

    def _write_fires(self, check):
        conds = [
            c
            for c in _find(self.REL, self.WRITE_TASK)["when"]
            if "openbao_bootstrap_token" not in str(c)
        ]
        return _all(
            conds,
            {
                "item": [{"path": "secret", "max_versions": 10}, check],
                "openbao_absent_stderr_marker": BAO_ABSENT,
            },
        )

    def test_a_denied_config_read_is_named(self):
        got = self._denied(
            [{"rc": 2, "stderr": CLI_DENIED, "item": {"path": "secret"}}]
        )
        self.assertEqual(list(got), ["secret"])

    def test_an_absent_config_is_NOT_named(self):
        got = self._denied(
            [{"rc": 2, "stderr": CLI_ABSENT, "item": {"path": "secret"}}]
        )
        self.assertEqual(list(got), [])

    def test_the_write_does_NOT_fire_on_a_denied_read(self):
        self.assertFalse(self._write_fires(_cli(2, CLI_DENIED)))

    def test_the_write_STILL_fires_on_a_genuinely_absent_config(self):
        # The guard must not disable the behaviour it protects.
        self.assertTrue(self._write_fires(_cli(2, CLI_ABSENT)))

    def test_the_write_fires_when_retention_differs(self):
        self.assertTrue(
            self._write_fires(_cli(0, "", '{"data": {"max_versions": 3}}'))
        )

    def test_the_write_does_NOT_fire_when_retention_already_matches(self):
        self.assertFalse(
            self._write_fires(_cli(0, "", '{"data": {"max_versions": 10}}'))
        )


class ObjectStorageProbes(unittest.TestCase):
    """head-bucket returns 403 and 404 with no rc-level distinction."""

    REL = "roles/object_storage/tasks/main.yml"
    CASES = [
        ("Check which default buckets already exist", "object_storage_bucket_check"),
        ("Read current versioning status", "object_storage_versioning_current"),
        (
            "Read current lifecycle configuration on versioned buckets",
            "object_storage_lifecycle_current",
        ),
    ]

    def _fails(self, task_name, var, result):
        return _all(_find(self.REL, task_name)["failed_when"], {var: result})

    def test_a_DENIED_probe_fails_every_site(self):
        for task_name, var in self.CASES:
            with self.subTest(task=task_name):
                self.assertTrue(
                    self._fails(task_name, var, _cli(255, "An error occurred (403)"))
                )

    def test_a_genuinely_absent_object_does_NOT_fail(self):
        for task_name, var in self.CASES:
            with self.subTest(task=task_name):
                self.assertFalse(
                    self._fails(
                        task_name, var, _cli(255, "An error occurred (404) Not Found")
                    )
                )

    def test_success_does_NOT_fail(self):
        for task_name, var in self.CASES:
            with self.subTest(task=task_name):
                self.assertFalse(self._fails(task_name, var, _cli(0, "")))


class TechnitiumZoneList(unittest.TestCase):
    """A bad token answers HTTP 200, so status is the only honest discriminator."""

    REL = "roles/technitium_dns/tasks/main/build_records.yml"
    TASK = "FAIL -- the zone list was not usable, so the live zone type is unknown"

    def _fails(self, zone_list):
        task = _find(self.REL, self.TASK)
        variables = {
            "technitium_dns_zone_list": zone_list,
            "technitium_dns_apply": True,
        }
        variables["_status"] = _render(task["vars"]["_status"], variables, wrap=False)
        return _all(task["when"], variables)

    def test_an_invalid_token_fails_rather_than_using_the_heuristic(self):
        # HTTP 200 with an error body -- the shape that caused Zammad #17246.
        self.assertTrue(
            self._fails({"status": 200, "json": {"status": "invalid-token"}})
        )

    def test_an_ok_response_does_NOT_fail(self):
        self.assertFalse(
            self._fails(
                {"status": 200, "json": {"status": "ok", "response": {"zones": []}}}
            )
        )

    def test_a_transport_failure_fails(self):
        self.assertTrue(self._fails({"status": -1, "json": {}}))


if __name__ == "__main__":
    unittest.main()
