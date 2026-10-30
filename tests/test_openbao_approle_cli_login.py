"""The OpenBao node timers log in through the shared bao-approle CLI.

The rotation, secret-age and snapshot scripts each used to pass their AppRole
secret_id on a command line. They now call `bao-approle login`, which takes the
credentials from the environment. These tests read the templates as text, the
same way the voter-health contract test does.
"""

from __future__ import annotations

import re
from pathlib import Path

_TEMPLATES = Path(__file__).resolve().parents[1] / "roles" / "openbao" / "templates"
_SCRIPTS = (
    "openbao-rotate.sh.j2",
    "openbao-secret-age.sh.j2",
    "openbao-snapshot.sh.j2",
)
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
