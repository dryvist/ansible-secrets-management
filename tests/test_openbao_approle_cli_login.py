"""The OpenBao node timers log in through the shared bao-approle CLI.

The rotation, secret-age and snapshot scripts each used to pass their AppRole
secret_id on a command line. They now call `bao-approle login`, which takes the
credentials from the environment. These tests read the templates as text, the
same way the voter-health contract test does.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATES = Path(__file__).resolve().parents[1] / "roles" / "openbao" / "templates"
_NODE_DEFAULTS = _ROOT / "roles" / "openbao" / "defaults" / "main" / "00-install-and-node.yml"
_SCRIPTS = (
    "openbao-rotate.sh.j2",
    "openbao-secret-age.sh.j2",
    "openbao-snapshot.sh.j2",
)


def _render_openbao_config(loopback_enabled: bool) -> str:
    variables = {
        "ansible_managed": "test managed",
        "openbao_data_dir": "/opt/openbao/data",
        "openbao_node_id": "openbao-test",
        "openbao_raft_peer_ips": [],
        "openbao_env_file": "/etc/openbao/openbao.env",
        "openbao_seal_key_id": "static-1",
        "openbao_seal_previous_key_id": "",
        "openbao_bind_address": "192.0.2.20",
        "openbao_api_port": 8200,
        "openbao_snapshot_loopback_listener_enabled": loopback_enabled,
        "openbao_api_addr": "http://192.0.2.20:8200",
        "openbao_cluster_addr": "https://192.0.2.20:8201",
        "openbao_plugin_dir": "/opt/openbao/plugins",
        "openbao_audit_device_name": "file",
        "openbao_audit_log_path": "/var/log/openbao/audit.log",
        "openbao_enable_ui": True,
        "openbao_prometheus_retention_time": "24h",
        "openbao_unauthenticated_metrics_access": True,
        "openbao_xff_authorized_addrs": ["192.0.2.10", "192.0.2.11"],
    }
    template = trust_as_template((_TEMPLATES / "openbao.hcl.j2").read_text(encoding="utf-8"))
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    return templar.template(template)


# A secret_id written as a `key=value` argument or a JSON member, including the
# escaped form inside a -d body. Case-sensitive, so the uppercase environment
# names the scripts pass to the CLI do not match.
_SECRET_ID_ON_ARGV = re.compile(r'secret_id\\?"?\s*[:=]')


def _text(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def test_each_script_logs_in_through_the_shared_cli() -> None:
    for name in _SCRIPTS:
        assert "bao-approle login" in _text(name), name


def test_no_script_posts_to_the_approle_login_endpoint() -> None:
    for name in _SCRIPTS:
        assert "auth/approle/login" not in _text(name), name


def test_no_secret_id_is_written_onto_a_command_line() -> None:
    for name in _SCRIPTS:
        assert not _SECRET_ID_ON_ARGV.search(_text(name)), name


def test_snapshot_uses_the_enabled_loopback_listener_by_default() -> None:
    defaults = yaml.safe_load(_NODE_DEFAULTS.read_text(encoding="utf-8"))
    assert defaults["openbao_snapshot_loopback_listener_enabled"] is True

    script = _text("openbao-snapshot.sh.j2")
    assert 'BAO_ADDR="http://127.0.0.1:{{ openbao_api_port }}"' in script
    assert "ONBOX_IP" not in script


def test_rotate_and_secret_age_use_the_enabled_loopback_listener_by_default() -> None:
    defaults = yaml.safe_load(_NODE_DEFAULTS.read_text(encoding="utf-8"))
    assert defaults["openbao_snapshot_loopback_listener_enabled"] is True

    for name in ("openbao-rotate.sh.j2", "openbao-secret-age.sh.j2"):
        script = _text(name)
        assert 'BAO_ADDR="http://127.0.0.1:{{ openbao_api_port }}"' in script, name
        assert "{{ openbao_api_addr }}" not in script, name


def test_rendered_snapshot_listener_is_loopback_only_and_omits_xff() -> None:
    rendered = _render_openbao_config(loopback_enabled=True)
    snapshot_listener = re.search(
        r'listener "tcp" \{\s+address\s*=\s*"127\.0\.0\.1:8200"'
        r'\s+tls_disable\s*=\s*1\s*\}',
        rendered,
    )
    assert snapshot_listener is not None
    assert "x_forwarded_for" not in snapshot_listener.group(0)
    assert rendered.count('listener "tcp" {') == 2

    rendered_disabled = _render_openbao_config(loopback_enabled=False)
    assert 'address     = "127.0.0.1:8200"' not in rendered_disabled
    assert rendered_disabled.count('listener "tcp" {') == 1


def test_snapshot_login_logs_redacted_helper_stderr_without_capturing_it_as_token(
    tmp_path: Path,
) -> None:
    login = _text("openbao-snapshot.sh.j2").split("login_stderr_file=", 1)[1]
    login = "login_stderr_file=" + login.split("# 4. Take", 1)[0]

    assert 'token="$(' in login
    assert 'bao-approle login 2>"${login_stderr_file}"' in login
    assert "login_diagnostic=\"$(<\"${login_stderr_file}\")\"" in login
    assert (
        'fail "snapshot AppRole login failed: ${login_diagnostic:-bao-approle returned no diagnostic}"'
        in login
    )
    assert (
        'for _sensitive in "${token}" "${OPENBAO_SNAPSHOT_ROLE_ID:-}" '
        '"${OPENBAO_SNAPSHOT_SECRET_ID:-}"'
        in login
    )
    assert "2>&1" not in login

    harness = """\
set -uo pipefail
OPENBAO_SNAPSHOT_ROLE_ID='role-id-value'
OPENBAO_SNAPSHOT_SECRET_ID='secret-id-value'
bao-approle() {
  printf '%s' 'client-token-value'
  printf 'login failed for role_id=%s secret_id=%s: connection refused\\n' \\
    "$BAO_APPROLE_ROLE_ID" "$BAO_APPROLE_SECRET_ID" >&2
  return 1
}
fail() {
  printf 'failure: %s\\n' "$*" >&2
  exit 9
}
mktemp() {
  printf '%s\\n' "$TEST_LOGIN_DIAGNOSTIC"
}
""" + login
    result = subprocess.run(
        ["bash"],
        input=harness,
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
        env={
            **os.environ,
            "TEST_LOGIN_DIAGNOSTIC": str(tmp_path / "login.stderr"),
        },
    )

    assert result.returncode == 9
    assert "connection refused" in result.stderr
    assert "role_id=[REDACTED]" in result.stderr
    assert "secret_id=[REDACTED]" in result.stderr
    assert "client-token-value" not in result.stdout + result.stderr
    assert "role-id-value" not in result.stdout + result.stderr
    assert "secret-id-value" not in result.stdout + result.stderr


def test_snapshot_login_stderr_temp_file_is_removed_when_the_script_is_killed(
    tmp_path: Path,
) -> None:
    login = _text("openbao-snapshot.sh.j2").split("login_stderr_file=", 1)[1]
    login = "login_stderr_file=" + login.split("# 4. Take", 1)[0]

    # The stubbed AppRole login blocks after the redirect has created the
    # diagnostic file, so the SIGTERM lands inside the window between the
    # mktemp and the explicit removals, where only the EXIT trap still owns
    # the file. Without the trap the default SIGTERM kills the script right
    # away and leaves the file behind.
    diagnostic = tmp_path / "login.stderr"
    marker = tmp_path / "login.started"
    harness = f"""\
set -uo pipefail
OPENBAO_SNAPSHOT_ROLE_ID='role-id-value'
OPENBAO_SNAPSHOT_SECRET_ID='secret-id-value'
bao-approle() {{
  : > '{marker}'
  sleep 3
  return 1
}}
fail() {{
  printf 'failure: %s\\n' "$*" >&2
  exit 9
}}
mktemp() {{
  printf '%s\\n' '{diagnostic}'
}}
""" + login
    proc = subprocess.Popen(
        ["bash"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    assert proc.stdin is not None
    proc.stdin.write(harness.encode("utf-8"))
    proc.stdin.close()

    deadline = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert marker.exists(), "the stubbed AppRole login never started"
    assert diagnostic.exists(), "the kill window was never reached"

    proc.send_signal(signal.SIGTERM)
    returncode = proc.wait(timeout=10)

    assert returncode == 143, f"expected exit 143, got {returncode}"
    assert not diagnostic.exists(), "the SIGTERM kill orphaned the login diagnostic file"
