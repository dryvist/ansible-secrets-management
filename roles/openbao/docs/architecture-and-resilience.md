# Architecture and resilience

## Architecture

- **5-voter Raft HA** (quorum 3): every node carries a `retry_join` for each peer
  (built from `openbao_group` hostvars' `container_ip`), so a node that is not
  yet part of a cluster finds the leader and joins automatically. The target
  placement is pve1:1, pve2:2, pve3:2, so a whole Proxmox server outage still
  leaves quorum.
- **On-prem static-key auto-unseal**: a single 32-byte AES-256 key (base64),
  shared by all nodes, unwraps the root key on every start — each node
  self-unseals on reboot with no operator key entry and **no cloud dependency**.
  The key is injected at runtime from Doppler tier-0 (`OPENBAO_STATIC_SEAL_KEY`),
  never committed, and lands in the `0600` `openbao.env` systemd EnvironmentFile.
- **Bootstrap election**: exactly one node — `openbao_bootstrap_host`, the
  alphabetically-first `openbao_group` member — runs `bao operator init`. Every
  other node only joins + auto-unseals; it never initializes.
- **Recovery shares**: as with any auto-unseal seal, `init` produces recovery
  shares (5, threshold 3) + a root token. These are the paper break-glass if the
  seal key is ever lost.

## Resilience — "never lost even in the worst conditions"

The durability guarantee holds from this role alone:

- **5 live Raft copies** spread across three Proxmox servers.
- **Recovery shares** transcribed to paper, split across custodians.
- **The seal key** in Doppler tier-0 (kept OUT of OpenBao so a cold cluster
  can't brick).
- The data dir (`/opt/openbao/data`) lives on a dataset covered by the host
  backup path (PBS / ZFS snapshot + offsite).

### Automated raft snapshots (on-box timer)

An on-box `openbao-snapshot.timer` (every `openbao_snapshot_interval`, default
`6h`) takes a logical raft snapshot on the **active node only** — the script
leader-gates at runtime via `/v1/sys/leader` `is_self`, so standby nodes no-op
and exactly one snapshot is taken per cycle regardless of who holds leadership.
It:

- authenticates with the least-privilege **`snapshot` AppRole** (scoped to
  `sys/storage/raft/snapshot`), over the node's **own VLAN IP** (`api_addr`),
  never the Traefik ingress VIP — OpenBao has no loopback listener, and a backup
  must come from a known specific node;
- integrity-checks each snapshot (`gzip -t` — raft snapshots are gzipped tar) and
  keeps the newest `openbao_snapshot_retain` (default 14) under the data volume,
  which sits on the ZFS/PBS-backed dataset that already replicates **off-box**;
- pings the healthchecks deadman + ntfy on every run (OK on success, `/fail` +
  an urgent ntfy alert on any failure), reusing the `service_deadman` stack.

The daemon is deployed on **every** node (so surviving nodes keep snapshotting
after a leadership change) and is gated on the snapshot AppRole creds being
present — a pre-provisioning converge skips it cleanly rather than shipping an
empty-cred EnvironmentFile. **Seal/liveness alerting** is handled by the
`service_deadman` role's `openbao_group` check (`bao status` exits non-zero when
a node is sealed or down → pages via the same deadman + ntfy path).

**Deliberately deferred** (tracked follow-ups — the durability guarantee above
does not depend on either):

- **A second off-box copy into the RustFS `openbao-snapshots` S3 bucket** (with a
  `HeadObject` + size/sha256 verify — never trusting the ETag, per RustFS
  `#1458`). The OpenBao LXCs are WAN-firewalled (`outbound-internal`), and a
  checksum-verifiable S3 client can't be delivered to them WAN-free the way the
  `.deb` is; hand-rolling SigV4 in shell is out (repo policy). ZFS replication of
  the data volume already carries snapshots off-box in the meantime.
- **A full restore-to-scratch-node drill.** Needs a scratch OpenBao node that
  does not exist yet; OpenBao 2.5.x has no `snapshot inspect` subcommand, so
  `gzip -t` is the strongest safe on-box integrity check today.

## Voter health scoring

An on-box `openbao-voter-health.timer` (every `openbao_voter_health_interval`,
default `5min`), deployed on every `openbao_group` member, samples every
voter's own plain-HTTP `api_addr` — never the Traefik ingress VIP, since a
backend has no loopback listener and an `https://` probe to it lies with a
`000` (see [`.claude/rules/ip-addressing.md`](../../../.claude/rules/ip-addressing.md)).
Like the snapshot timer it leader-gates at runtime via `/v1/sys/leader`
`is_self`, so exactly one voter performs the full cross-cluster sweep per
cycle regardless of who holds leadership.

**This is read-only telemetry.** It never joins/removes a Raft peer, never
writes a policy or AppRole, and never mutates cluster state. Raft membership
changes stay operator-gated — this feature only produces the evidence a human
uses to decide whether one is warranted.

Each cycle ships one Splunk HEC event per voter (`index=openbao`,
`sourcetype=openbao:voter:health`) recording:

| Field | Meaning |
| --- | --- |
| `voter` | inventory hostname of the sampled node |
| `http_code` | raw `sys/health` HTTP status (200/429/472/473/501/503/000) |
| `health_state` | decoded label: `active`, `standby`, `performance_standby`, `dr_secondary`, `uninitialized`, `sealed`, `unreachable`, `unknown` |
| `latency_ms` | round-trip time of the `sys/health` probe |
| `is_self` | whether this voter reports itself as the current Raft leader |
| `leader_address` | the leader address this voter currently sees |
| `raft_lag_ms` | apply-lag vs the leader — currently always `null`; see "Known gap" below |
| `sampled_by` | which voter performed the sweep (the leader at sample time) |

Reference SPL — a 7/30-day per-voter uptime and latency scorecard, a flap
count, and an alert for a voter unhealthy for more than 24h — lives in
[`docs/openbao-voter-health-spl.md`](../../../docs/openbao-voter-health-spl.md).

### Keep/demote evidence thresholds

These are **evidence guidelines for a human decision**, not automation — this
role never changes Raft membership itself. Treat a voter as safe to keep with
no action when it clears all of:

- 30-day uptime ≥ 99.5% (at a 5-minute sampling cadence, roughly ≤ 2h of
  cumulative down time over 30 days)
- flap count over the trailing 7 days ≤ 5 (occasional restarts/converges are
  expected; frequent state churn is not)
- p95 latency in family with its peers — no single voter should be a
  consistent multi-x outlier without an explained cause (undersized guest,
  contended host, network path)

Treat a voter as **demote-evidence-positive** — i.e. there is now enough
telemetry to justify an operator-gated Raft membership review — when either:

- the 24h-unhealthy alert (see the SPL doc) has fired and the voter has not
  recovered, or
- 30-day uptime drops below 99.5% AND flap count over the same window exceeds
  10, indicating a chronic rather than transient problem

A voter that is merely a latency outlier, with uptime and flap count both
within threshold, is not by itself evidence for demotion — investigate the
host/network cause first. Any actual membership change (removing a voter,
adding a replacement) remains a manually operator-run `bao operator raft`
action; nothing in this repo automates it.

### Known gap: raft apply-lag is not yet measured

`raft_lag_ms` always ships as `null` today. Computing real apply-lag needs
`sys/storage/raft/autopilot/state`, which requires a token with `sys/` read
capability — every existing AppRole here is KV-scoped (see
[Secret hierarchy & RBAC](secrets-and-rbac.md#secret-hierarchy--rbac)), and minting a new
least-privilege `voter-health` AppRole/policy was explicitly out of scope for
the change that introduced this telemetry (telemetry-only, no OpenBao
policy/AppRole edits). `openbao_voter_health_role_id` /
`openbao_voter_health_secret_id` are wired through the script already — once
that AppRole exists, the script will use it to include real lag figures.

## Apply order (important)

This role brings OpenBao live **before** anything that reads secrets from it.

1. Generate the seal key once (`openssl rand -base64 32`) and load it into
   Doppler tier-0 as `OPENBAO_STATIC_SEAL_KEY` (+ `OPENBAO_STATIC_SEAL_KEY_ID`).
2. `tofu-proxmox` — provision the 5 OpenBao LXCs (VMID/IP/firewall).
3. **this role** — install + init the cluster, mint the AppRoles.
4. Operator — transcribe recovery shares to paper (+ Bitwarden); publish each
   AppRole's `role_id`/`secret_id` to Doppler tier-0, consumed as ambient env
   under `doppler run` — except `public`, which needs no secret-zero at all
   (see [Secret hierarchy & RBAC](secrets-and-rbac.md#secret-hierarchy--rbac)).
5. `tofu-proxmox` `vault-secrets` — now able to authenticate as
   `terraform-apply` (read/write proof).

## Rolling expansion / migration (preserve a live cluster's data)

`bao operator init` creates a **brand-new empty cluster**. To grow or renumber a
cluster that already holds secrets **without losing them**, the new nodes must
JOIN the live cluster (retry_join), not init. The role enforces this:
`openbao_allow_fresh_init` defaults `false`, and before any init the bootstrap
host probes every peer — if one is already initialized it refuses to init and
fails loudly. Fresh init happens only on a genuine first bootstrap
(`-e openbao_allow_fresh_init=true`).

To expand the current 2-node cluster (`openbao-01`, `openbao-02`) into the
5-voter topology (`openbao-10/-20/-21/-30/-31` — one/two/two across the three
Proxmox hosts, each node's IP last octet matching its `NN` suffix), do it in two
phases so the data replicates to the new voters before the old ones leave:

**Phase 1 — add (interim 7-node cluster, zero downtime):**

1. In `deployment.json`, KEEP `openbao-01` + `openbao-02` AND add the five new
   nodes, so `openbao_group` has all seven. Every node's `retry_join` is the
   union, so the new nodes find the live leader and replicate the full store.
2. Pin the bootstrap/provisioning host to a **live, initialized** node for the
   migration: `-e openbao_bootstrap_host=openbao-02` (never a new node; and not a
   node whose host is currently unstable). `openbao_allow_fresh_init` stays
   `false`.
3. `tofu-proxmox` apply creates the five new LXCs; then run this role with
   `--limit openbao_group,localhost`.
4. **Verify before Phase 2:** `bao operator raft list-peers` shows all 7;
   `bao operator raft autopilot state` shows 7 healthy voters; a read of a known
   secret succeeds from a NEW node. Do not proceed until healthy.

**Phase 2 — remove the old nodes (shrink to the clean 5):**

1. `bao operator raft remove-peer openbao-01` then `... openbao-02`.
2. Drop `openbao-01`/`openbao-02` from `deployment.json`; `tofu-proxmox`
   apply destroys the two old LXCs. Final state: 5 voters, quorum 3 — survives
   any single node, and any single Proxmox host, going down.

**Leader preference** (first host > second > third): Raft does not natively pin a
leader — whichever voter wins the election leads; autopilot only handles
stabilization and dead-server cleanup. If keeping leadership off a specific host
matters, the real lever is making that host's nodes **non-voters** (they never
lead and never count toward quorum) — weigh that against the HA math (5 voters
tolerate 2 down; 3 voters + 2 non-voters tolerate 1). Do not claim hard
leader-pinning the engine can't do.

