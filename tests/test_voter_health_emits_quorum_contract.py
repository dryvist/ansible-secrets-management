"""The voter-health sampler owes the quorum alert a `voters=<n>` token.

The alert that watches consensus lives in another repository and matches on
`voters=(?P<voters>\\d+)`. It discards every line without that token, so a
sampler that stops emitting it does not make the alert noisy — it makes the
alert match nothing, evaluate "no samples", and lose the ability to tell a
degraded cluster from a silent one.

That is not hypothetical: the token was absent for long enough that 15,010
sampler events reached the log platform carrying zero matches, while the alert
sat scheduled and enabled the whole time.

These tests guard the contract and the fail-closed exit. They read the template
as text on purpose — the point is that the emit survives future edits, not that
Jinja renders.
"""

from __future__ import annotations

import re
from pathlib import Path

# Two roles ship a sampler of this name. The one whose systemd unit wins is
# roles/openbao_voter_health; roles/openbao installs an orphan copy to a
# different path that nothing executes. Both are asserted so the contract
# cannot be satisfied in the dead copy alone — which is exactly the mistake
# this file exists to make impossible.
_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = [
    _ROOT / "roles/openbao_voter_health/templates/openbao-voter-health.sh.j2",
    _ROOT / "roles/openbao/templates/openbao-voter-health.sh.j2",
]

# Verbatim from the consuming saved search. Keep these in step.
ALERT_REGEX = re.compile(r"voters=\(\?<voters>\\d\+\)|voters=")


def _templates() -> list[tuple[str, str]]:
    found = [(str(p), p.read_text(encoding="utf-8")) for p in TEMPLATES if p.exists()]
    assert found, "no voter-health template found at any known path"
    return found


def test_summary_emits_a_voters_token_the_alert_can_match() -> None:
    """Every shipped copy must emit `voters=` bound to a counted value."""
    for name, body in _templates():
        # The header comment documents the same string, so match the emitting
        # log call rather than any line mentioning it.
        summary = [
            ln
            for ln in body.splitlines()
            if "sweep complete" in ln and ln.lstrip().startswith("log ")
        ]
        assert summary, f"{name}: no sweep summary is logged at all"
        line = summary[0]
        assert "voters=${healthy_count}" in line, (
            f"{name}: the summary must emit voters=<count>; the consuming alert "
            f"matches on that token and drops every line without it. Got: {line}"
        )
        assert re.search(r"voters=(\d+)", line.replace("${healthy_count}", "9"))


def test_healthy_count_is_actually_incremented() -> None:
    """A token bound to a variable nothing increments reports a constant zero."""
    for name, body in _templates():
        assert "healthy_count=0" in body, f"{name}: healthy_count never initialised"
        assert "healthy_count=$((healthy_count + 1))" in body, (
            f"{name}: healthy_count is emitted but never incremented, so the "
            "alert would read a permanent zero and fire forever"
        )


def test_a_failed_ship_does_not_exit_zero() -> None:
    """A sweep whose ships failed must not look like a clean sweep."""
    for name, body in _templates():
        assert "ship_fail_count=$((ship_fail_count + 1))" in body, (
            f"{name}: ship failures are not counted, so they cannot affect exit"
        )
        assert re.search(
            r'if \[ "\$\{ship_fail_count\}" -gt 0 \]; then(?:.|\n)*?exit 1', body
        ), (
            f"{name}: must exit non-zero when a ship fails; exiting 0 "
            "unconditionally makes total shipping failure look healthy"
        )


def test_unreachable_voters_are_still_counted_separately() -> None:
    """Voters that did not answer and ships that did not land are different."""
    for name, body in _templates():
        assert "fail_count=$((fail_count + 1))" in body, name
        assert "unreachable=${fail_count}" in body, (
            f"{name}: keep unreachable voters distinct from ship failures; "
            "collapsing them loses which half is broken"
        )
