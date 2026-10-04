"""Contract: no KV secret value is ever written through a process argv.

`bao kv put/patch` takes every field as a `key=value` argument, so the values
are visible in the process table of the host that runs it. Secret writes go
through the OpenBao HTTP API instead (`ansible.builtin.uri`, body in the
module, `no_log: true`). This scans every task file in the repository for a
`command`/`shell` task that writes KV data, and every `uri` KV-data write for
`no_log`. KV *metadata* writes (`bao kv metadata ...`) carry no secret values
and stay allowed.
"""

from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCAN = [ROOT / "roles", ROOT / "playbooks"]
COMMAND_MODULES = {"command", "shell", "ansible.builtin.command", "ansible.builtin.shell"}
URI_MODULES = {"uri", "ansible.builtin.uri"}
# `kv put` / `kv patch` in a cmd string, or 'kv', 'put' / 'kv', 'patch' in an argv list.
KV_DATA_WRITE = re.compile(r"""kv['"]?\s*,?\s*['"]?(put|patch)\b""")


def offenders(text_by_file):
    argv_writes, unlogged_api_writes = [], []
    for path, text in text_by_file.items():
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        for task, inherited in walk(doc, False):
            for module in COMMAND_MODULES & task.keys():
                body = str(task[module]) + str(task.get("args", ""))
                if KV_DATA_WRITE.search(body):
                    argv_writes.append(f"{path}: {task.get('name')}")
            for module in URI_MODULES & task.keys():
                spec = task[module] if isinstance(task[module], dict) else {}
                if "/data/" in str(spec.get("url", "")) and str(spec.get("method", "GET")).upper() in {"POST", "PUT", "PATCH"}:
                    if not (task.get("no_log") is True or inherited):
                        unlogged_api_writes.append(f"{path}: {task.get('name')}")
    return argv_writes, unlogged_api_writes


def walk(node, inherited):
    if isinstance(node, list):
        for item in node:
            yield from walk(item, inherited)
    elif isinstance(node, dict):
        here = inherited or node.get("no_log") is True
        if any(k in node for k in COMMAND_MODULES | URI_MODULES):
            yield node, inherited
        for key in ("block", "rescue", "always", "tasks", "pre_tasks", "post_tasks", "handlers"):
            if key in node:
                yield from walk(node[key], here)


def repo_files():
    return {
        str(p.relative_to(ROOT)): p.read_text(encoding="utf-8")
        for base in SCAN for p in sorted(base.rglob("*.yml"))
    }


class SecretWritesUseTheApi(unittest.TestCase):
    def test_no_kv_data_write_through_argv(self):
        argv_writes, _ = offenders(repo_files())
        self.assertEqual(argv_writes, [], "KV data written via command/shell argv")

    def test_api_kv_data_writes_are_no_log(self):
        _, unlogged = offenders(repo_files())
        self.assertEqual(unlogged, [], "KV data written via uri without no_log")

    def test_detects_an_argv_write(self):
        bad = {"x.yml": "- name: put it\n  ansible.builtin.command:\n    argv: \"{{ ['bao', 'kv', 'put', 'secret/apps/a'] + pairs }}\"\n"}
        self.assertEqual(offenders(bad)[0], ["x.yml: put it"])

    def test_detects_a_cmd_string_write(self):
        bad = {"x.yml": "- name: put it\n  ansible.builtin.shell: bao kv patch secret/apps/a k=v\n"}
        self.assertEqual(offenders(bad)[0], ["x.yml: put it"])

    def test_metadata_write_is_allowed(self):
        ok = {"x.yml": "- name: meta\n  ansible.builtin.command:\n    argv: \"{{ ['bao', 'kv', 'metadata', 'put', '-mount=x'] }}\"\n"}
        self.assertEqual(offenders(ok)[0], [])

    def test_detects_an_unlogged_api_write(self):
        bad = {"x.yml": "- name: post it\n  ansible.builtin.uri:\n    url: http://a/v1/secret/data/apps/a\n    method: POST\n"}
        self.assertEqual(offenders(bad)[1], ["x.yml: post it"])


if __name__ == "__main__":
    unittest.main()
