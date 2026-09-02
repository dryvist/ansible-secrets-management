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

The B7a gate this file used to carry is gone: the rollout converged on
2026-07-08 and the index has held records continuously since. The skip
outlived the condition it described, which is how a four-hour blackout of the
audit trail on 2026-09-02 got through a green suite.
"""

from .helpers import query_splunk


class TestOpenBaoAuditFreshness:
    """Verify OpenBao audit entries keep landing in index=openbao_audit."""

    def test_audit_events_arrive(self, splunk_creds):
        """At least one audit entry indexed in the last 2h window.

        2h, not 6h: the failure this guards against is a stalled forwarding
        session, and every occurrence measured over the preceding 30 days was
        between 2 and 7 hours long. A 6h window passes straight through most
        of them, which is a detector that reports success during the outage
        it exists to catch.

        The floor that makes 2h safe is timer traffic: the raft snapshot and
        voter-health timers authenticate continuously, giving a measured
        baseline of ~96 audit records/hour with no human activity at all. A
        silent 2h window therefore means the chain is broken, never idle.
        """
        mgmt_url, user, password = splunk_creds
        results = query_splunk(
            mgmt_url,
            user,
            password,
            'index=openbao_audit sourcetype="openbao:audit" | head 5',
            earliest="-2h",
            timeout=30,
        )
        assert results, (
            "No openbao:audit events in index=openbao_audit within 2h — the "
            "audit device, the rsyslog imfile ruleset, or the openbao_audit "
            "ingest path appears broken."
        )
