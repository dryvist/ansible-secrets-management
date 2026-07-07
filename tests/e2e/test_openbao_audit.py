"""OpenBao audit-log shipping test (stub — skipped until converged).

The openbao role enables the file audit device and ships
/var/log/openbao/audit.log via a dedicated rsyslog imfile ruleset to the
openbao_audit AI ingest listener (syslog CNAME -> HAProxy -> Cribl Stream
ai_stamp -> Splunk index=openbao_audit).

Sentinel injection is NOT possible from a runner: audit entries are only
produced by real API traffic against the cluster, and the audit file is not
runner-writable. So this is a freshness gate (like test_macos.py) — any
authenticated request produces an audit entry, and the snapshot timer alone
guarantees regular traffic.

Skipped until the B7a rollout has converged on the openbao guests AND the
openbao_audit index exists on the Splunk side; then drop the skip mark.
"""

import pytest

from .helpers import query_splunk


@pytest.mark.skip(
    reason=(
        "openbao audit shipping (B7a) not yet converged — enable after the "
        "audit device + rsyslog ruleset are live and the openbao_audit "
        "Splunk index exists"
    )
)
class TestOpenBaoAuditFreshness:
    """Verify OpenBao audit entries keep landing in index=openbao_audit."""

    def test_audit_events_arrive(self, splunk_creds):
        """At least one audit entry indexed in the last 6h window.

        The raft snapshot timer authenticates every openbao_snapshot_interval
        (6h), so a fully-silent 6h window means the shipping chain is broken
        (device disabled, rsyslog ruleset gone, or listener down).
        """
        mgmt_url, user, password = splunk_creds
        results = query_splunk(
            mgmt_url,
            user,
            password,
            'index=openbao_audit sourcetype="openbao:audit" | head 5',
            earliest="-6h",
            timeout=30,
        )
        assert results, (
            "No openbao:audit events in index=openbao_audit within 6h — the "
            "audit device, the rsyslog imfile ruleset, or the openbao_audit "
            "ingest path appears broken."
        )
