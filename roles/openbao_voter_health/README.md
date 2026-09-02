# openbao_voter_health

Read-only telemetry for the OpenBao Raft cluster. It periodically samples
every voter's **unauthenticated** `sys/health` and `sys/leader` endpoints
directly over plain HTTP (backends terminate TLS at the ingress proxy; an
`https://` probe to a backend reads `000` and lies about the node being down)
and ships one event per voter per cycle to Splunk HEC. It exists to build the
longitudinal evidence a future, separately-approved membership change would
need — **it makes no membership, policy, or AppRole change itself**, and
deploying it is reversible (stop/disable the timer, nothing else changes).

## How it works

- Deployed identically on every `openbao_group` member (same footprint as
  the existing raft-snapshot timer), but the script leader-gates at runtime:
  only the node currently holding Raft leadership performs the full
  cross-cluster sweep each cycle. A standby exits `0` as a no-op, so exactly
  one set of events ships per cycle regardless of who leads.
- Per voter, per cycle: HTTP status code + label (`active` / `standby` /
  `dr_secondary` / `performance_standby` / `uninitialized` / `sealed` /
  `unreachable`), request latency in ms, and leadership self-report
  (`is_self`, `leader_address`).
- Host + port are never hardcoded — the FQDN is derived from
  `tofu_data.domain` and the port from `tofu_data.constants`
  (`.claude/rules/ip-addressing.md`). The Splunk HEC token is the same
  `SPLUNK_HEC_TOKEN` every other HEC consumer in this repo already uses — no
  new secret is introduced.

## Known gap: raft apply-lag is not yet authenticated

`sys/storage/raft/autopilot/state` (the endpoint that reports each voter's
applied-index lag vs the leader) requires a token with `sys/` read
capability. No existing least-privilege AppRole in `roles/openbao` grants
that (they are all KV-scoped), and minting a new AppRole/policy is
**explicitly out of scope for this role** — that's an OpenBao policy change,
which is operator-gated separately. The script emits `raft_lag_ms: null`
until `OPENBAO_APPROLE_VOTER_HEALTH_ROLE_ID` / `OPENBAO_APPROLE_VOTER_HEALTH_SECRET_ID` are
supplied (env, same delivery pattern as every other AppRole credential in
this repo); wiring those up is a follow-up that provisions a `voter-health`
AppRole scoped to exactly that one read.

## SPL: per-voter health scorecard (7 / 30 day)

Assumes events land in the `openbao` index with sourcetype
`openbao:voter:health` (both configurable via role defaults) and Splunk is
already configured to accept them — this role ships the shipping mechanism
only; it does not configure Splunk.

```spl
| tstats count avg(latency_ms) perc95(latency_ms) as p95_latency_ms
    values(health_state) as states
    from datamodel=OpenBaoVoterHealth
    OR (index=openbao sourcetype="openbao:voter:health")
    where earliest=-30d latest=now
    by voter
| eval uptime_pct_30d = round((count(eval(health_state="active" OR health_state="standby")) / count) * 100, 2)
```

A more direct non-datamodel version (adjust `index`/`sourcetype` to your
environment):

```spl
index=openbao sourcetype="openbao:voter:health" earliest=-30d@d latest=now
| eval healthy = if(health_state IN ("active","standby"), 1, 0)
| stats
    count as samples_30d
    sum(healthy) as healthy_samples_30d
    avg(latency_ms) as avg_latency_ms
    perc95(latency_ms) as p95_latency_ms_30d
    values(raft_lag_ms) as raft_lag_samples
    by voter
| eval uptime_pct_30d = round((healthy_samples_30d / samples_30d) * 100, 2)
| append
    [ search index=openbao sourcetype="openbao:voter:health" earliest=-7d@d latest=now
      | eval healthy = if(health_state IN ("active","standby"), 1, 0)
      | stats count as samples_7d sum(healthy) as healthy_samples_7d avg(latency_ms) as avg_latency_ms_7d by voter
      | eval uptime_pct_7d = round((healthy_samples_7d / samples_7d) * 100, 2) ]
| stats values(*) as * by voter
```

Flap count (health_state transitions) over the same windows:

```spl
index=openbao sourcetype="openbao:voter:health" earliest=-30d@d latest=now
| sort 0 voter, _time
| streamstats current=f last(health_state) as prev_state by voter
| eval flapped = if(health_state!=prev_state, 1, 0)
| stats sum(flapped) as flap_count_30d by voter
```

## Alert: voter unhealthy > 24h

```spl
index=openbao sourcetype="openbao:voter:health" earliest=-24h latest=now
| stats count as samples,
    count(eval(health_state NOT IN ("active","standby"))) as unhealthy_samples,
    max(_time) as last_seen by voter
| eval unhealthy_pct = round((unhealthy_samples / samples) * 100, 2)
| where unhealthy_pct = 100 OR (now() - last_seen) > 86400
```

Schedule this as a saved search / alert (cron `*/15 * * * *` is enough given
the 5-minute sample cadence) with a severity that pages, not just logs — a
voter unhealthy for a full day is exactly the kind of chronic-flake evidence
this telemetry exists to surface.

## From scores to a keep/demote recommendation

This role produces evidence. It does **not** recommend or perform a
membership change — that stays operator-gated. Suggested evidence
thresholds for a human (or a separate, explicitly-scoped follow-up) to act
on:

| Signal (30-day window) | Keep | Investigate | Demote candidate |
| --- | --- | --- | --- |
| Uptime % | ≥ 99% | 95–99% | < 95% |
| Flap count | ≤ 3 | 4–10 | > 10 |
| p95 latency | within 2× cluster median | 2–5× | > 5× cluster median |
| Consecutive unhealthy | none > 1h | 1–24h | > 24h (see alert above) |

A voter landing in "demote candidate" on **any** signal for two consecutive
30-day windows is the evidence bar for opening a separate, explicitly-scoped
change to actually alter Raft membership (`bao operator raft remove-peer`
plus the corresponding `openbao_raft_peer_ips` / inventory update) — that
change is out of scope here and must be its own reviewed PR against
`roles/openbao`, never an automatic action taken by this telemetry.
