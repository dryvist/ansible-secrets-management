#!/usr/bin/env python3
"""Minimal stub of OpenBao's HTTP API for verify_provision_uicheck_totp.yml.

Implements only the endpoints playbooks/provision-uicheck-totp.yml calls:
  GET  /v1/sys/mounts             - list mounts
  POST /v1/sys/mounts/<mount>     - enable a secrets engine
  GET  /v1/<mount>/keys/<user>    - check whether a TOTP key exists
  POST /v1/<mount>/keys/<user>    - import a TOTP key

State lives in the file named by the TOTP_STATE_FILE env var, as
shell-sourceable KEY=VALUE lines, shared with fixtures/fake_authelia so both
sides of one test case agree on what has and has not been seeded yet. Read
fresh on every request (never cached) so a test case can rewrite the file
between playbook runs while this server keeps running underneath them.

Usage: fake_bao_server.py <port>
"""
import http.server
import json
import os
import re
import sys

MOUNTS_RE = re.compile(r"^/v1/sys/mounts/[^/]+$")
KEYS_RE = re.compile(r"^/v1/[^/]+/keys/[^/]+$")


def _state_path():
    path = os.environ.get("TOTP_STATE_FILE")
    if not path:
        raise SystemExit("TOTP_STATE_FILE must be set")
    return path


def _read_state():
    state = {"engine_enabled": "false", "key_exists": "false"}
    path = _state_path()
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    state[k] = v
    return state


def _append_state(line):
    with open(_state_path(), "a") as fh:
        fh.write(line + "\n")


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body=None):
        self.send_response(code)
        if code == 204:
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        payload = json.dumps(body if body is not None else {}).encode()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        state = _read_state()
        if self.path == "/v1/sys/mounts":
            mounts = {"totp/": {"type": "totp"}} if state["engine_enabled"] == "true" else {}
            self._send(200, {"data": mounts})
            return
        if KEYS_RE.match(self.path):
            if state["key_exists"] == "true":
                self._send(200, {"data": {"algorithm": "SHA1"}})
            else:
                self._send(404, {"errors": []})
            return
        self._send(404, {"errors": ["unhandled path: " + self.path]})

    def do_POST(self):
        if MOUNTS_RE.match(self.path):
            _append_state("engine_enabled=true")
            self._send(204)
            return
        if KEYS_RE.match(self.path):
            _append_state("key_exists=true")
            self._send(204)
            return
        self._send(404, {"errors": ["unhandled path: " + self.path]})

    def log_message(self, format: str, *args: object) -> None:
        del format, args  # keep test output quiet


if __name__ == "__main__":
    port = int(sys.argv[1])
    http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
