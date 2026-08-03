# openbao

Installs and bootstraps [OpenBao](https://openbao.org/) — a native single Go
binary on Debian (no Docker) — as a **5-voter Raft HA cluster** with **on-prem
static-key auto-unseal** (no cloud KMS). After the cluster is live the role
provisions a KV v2 mount, the secret hierarchy, the RBAC policies, and one
AppRole per resource-domain identity (see [Secret hierarchy & RBAC](#secret-hierarchy--rbac)).

> **Before changing anything here, read
> [`.claude/rules/openbao-plugins-first.md`](../../.claude/rules/openbao-plugins-first.md).**
> Secrets engines are mandatory wherever one exists: GitHub tokens are minted
> from `github/token/<permission_set>` (estate identities attach the existing
> `github-mint` policy; the workstation tiers are `github-read` /
> `github-write` / `github-admin`) and AWS credentials from `aws/sts/<role>`.
> A static PAT or access key stored in KV is manual credential control and is
> rejected. KV is only for values no engine can mint.

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
`000` (see [`.claude/rules/ip-addressing.md`](../../.claude/rules/ip-addressing.md)).
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
[`docs/openbao-voter-health-spl.md`](../../docs/openbao-voter-health-spl.md).

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
[Secret hierarchy & RBAC](#secret-hierarchy--rbac)), and minting a new
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
   (see [Secret hierarchy & RBAC](#secret-hierarchy--rbac)).
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

## Installation

The role lives in this repository under `roles/openbao/`. Reference it from a
play targeting `openbao_group` — no Galaxy install needed:

```yaml
- hosts: openbao_group
  become: true
  roles:
    - role: openbao
```

Host membership in `openbao_group` is driven by the Terraform-exported
inventory: an LXC tagged `openbao` is placed in `openbao_group` by
`inventory/load_tofu.yml`. The node's VLAN IP arrives as the `container_ip`
hostvar (also used to build the Raft peer list).

## Usage

Run through the credentialed wrapper so `OPENBAO_STATIC_SEAL_KEY` is present:

```sh
doppler run -- ansible-playbook playbooks/site.yml --tags openbao
```

On the **first** run the bootstrap node initializes the cluster and writes the
break-glass files to the controller (see below); the peers join + auto-unseal.
Every subsequent run is a no-op: install is skipped (version present) and the
bootstrap steps short-circuit on their existence checks.

## Secret hierarchy & RBAC

Three KV v2 mounts, split by what a leak would cost. The split is a **mount**
and never a path prefix: a prefix shares one policy namespace, so every
wildcard already granted on `secret/` would reach across it.

| Mount | Holds | A leak costs |
| --- | --- | --- |
| `secret/` | Credentials for services reachable only inside the network | Bounded by network access |
| `secrets-external/` | Credentials for internet-reachable vendor APIs | Critical — exploitable by anyone, anywhere |
| `config/` | Non-secret configuration: operator selections, tunables, thresholds, coordination facts | Nothing exploitable by construction |

`config/` KV v2 retention is set explicitly
(`openbao_config_mount_max_versions`, default 30) so version history and
rollback are actually available. `delete_version_after` is left at its default
of 0 — versions never time-expire, because history that silently ages out
cannot be rolled back to.

Nothing in this mount is a secret, so neither policy carves paths up: per-path
least privilege would buy nothing and cost churn on every new key. Access is
split by **verb**, not by path.

- **`config-read` is the default.** One AppRole, mount-wide read + list,
  nothing outside the mount. Everything that only *consumes* config uses it.
- **`config-write` is a capability policy, not an identity.** It is attached to
  the three IaC systems that *author* config, exactly the way
  `ansible-converge` already composes `ssh-sign-automation-ansible`:

  | Author | Identity | How it attaches |
  | --- | --- | --- |
  | OpenTofu | `terraform-apply` AppRole | `token_policies` |
  | Ansible | `ansible-converge` AppRole | `token_policies` |
  | Terrakube | per-workspace JWT roles | `policies` on each JWT role |

  There is no `config-write` AppRole. Minting one would hand OpenTofu and
  Ansible a *second* secret-zero to carry for a mount holding no secrets, and
  would still not serve Terrakube, which authenticates by JWT workload identity
  and has no AppRole at all. Attach `config-write` only to a system that
  genuinely authors config — a consumer that attaches it gains a write path it
  will never use.

**What `config-write` deliberately cannot do.** It gets `create`/`read`/
`update`/`patch` plus KV v2's *soft* `delete` on `data/*`, and `update` on
`undelete/*` so the identity that made a mistake can reverse it. It does **not**
get `destroy` (permanent removal of specific versions) or `delete` on
`metadata/*` (which permanently removes a key *and* its whole history in one
call). Both erase the audit trail this mount exists to provide; erasing history
should require reaching for an admin credential.

`patch` is granted on purpose. A whole-object `kv put` silently drops fields the
writer did not know about — a bug this repo has already hit (see the
merge-preserving app-secret seed in `tasks/init.yml`). With three independent
authors on one mount, partial update is what lets them share a key instead of
clobbering each other.

Terrakube's grant covers every declared workspace by default
(`openbao_config_write_terrakube_workspaces`; narrowing it is one edit). Worth
revisiting: Terrakube runs VCS-driven, potentially untrusted plans, so it is the
one `config-write` holder whose blast radius is non-obvious. It cannot reach a
credential mount, but it can rewrite config other systems read.

The KV v2 mount `secret/` is organized by category (canonical doc:
`tofu-proxmox` `docs/SECRETS_HIERARCHY.md`):

```text
secret/infra/      proxmox/ aws/ network/   # IaC kernel — terraform-apply writes
secret/platform/   dns/ traefik/ terrakube/ splunk/ cribl/ object-storage/ compute/
secret/apps/       media/ monitoring/ home-automation/
secret/ai/         hermes/ agents/          # LLM stack + AI-agent creds
secret/locks/      global                   # cross-repo apply lock state
secret/public/     domain/ ...              # non-secret, non-exploitable facts
secret/ci/         github/ doppler-sync/
```

One AppRole per resource-domain identity, each bound to a least-privilege
policy — split so no identity spans both an infra-writing role and an
untrusted execution surface (Terrakube runs VCS-driven, potentially untrusted
plans):

| AppRole | Reads | Writes | Notes |
| --- | --- | --- | --- |
| `terraform-apply` | `secret/infra/*`, `secret/platform/{dns,traefik}`, `secret/apps/nautobot/*`, `homelab/*` | (same) | Human-triggered IaC apply[^aws-sts] |
| `apps-seed` | `secret/apps/*` | `secret/apps/*` create/update | Doppler-published writer; Terraform `vault-secrets` seeds `secret/apps/<app>` at source |
| `flow-lock` | `secret/locks/global`, `secret/infra/*` | `secret/locks/global` | Cross-repo apply lock; releases the lock via metadata delete |
| `terrakube-<workspace>` JWT | Only that workspace's native paths | Workspace-specific | Short-lived; exact organization/workspace subject and audience |
| `ansible-converge` | Platform, apps, exact MCP secrets | Exact MCP secrets | Config pulls and transitional MCP publishers; no broad AI access |
| `observability` | `secret/platform/{splunk,cribl}` | — | Ingest pipeline (shared HEC tokens) |
| `local-cloud` | `secret/platform/{object-storage,compute}` | — | RustFS + compute creds |
| `monitoring` | `secret/apps/monitoring` | — | netmon/unifi_metrics/prometheus_stack |
| `media` | `secret/apps/media` | — | *arr/qBittorrent/Plex stack |
| `local-llm` | `secret/ai/*` | — | The LLM serving stack itself |
| `hermes` | `secret/ai/hermes`, `secret/ai/mcp/splunk` | — | Dedicated least-privilege reader for Hermes; NO broad `secret/ai/*` |
| `hermes-write` | `secret/ai/hermes` | `secret/ai/hermes` | Narrow one-time credential seed writer; shared MCP publication belongs to `ansible-converge` |
| `public` | `secret/public/*` | — | **Anonymous** — no secret-zero; shipped ambiently |
| `config-read` | all of `config/` | — | **Default** reader; mount-wide wildcard is correct here; shipped ambiently |
| `config-write` *(policy, no AppRole)* | all of `config/` | `config/` values: create/update/patch/soft-delete | Attached to the 3 IaC authors[^config-write] |
| `ai-orchestrator` | `secret/ai/{hermes,agents}` | `secret/ai/{hermes,agents}` (create/update) | WRITE; Doppler tier-0; narrowed + 30m TTL at Phase-3 |
| `ai-readonly` | `read-all` (= `read-<svc>` ∀ services) | — | **default AI agent; NO `secret/infra/*`**[^ai-tiers] |
| `ai-elevated` | `read-all` + `read-platform` | — | trusted infra-touching agents; no write[^ai-tiers] |
| `ai-apply-<svc>` | `read-<svc>` | `write-<svc>` + `github-mint` | Task-scoped WRITE, one service; no standing secret_id; ≤1h[^ai-tiers] |
| `ai-apply-all` | `read-write-all` | `read-write-all` + `github-mint` | Cross-domain WRITE rollup; no standing secret_id; ≤1h[^ai-tiers] |
| `ai-admin` | all KV + policy/auth admin | policy/AppRole/token, all KV, AWS STS | Break-glass; **sole self-modify role**; ≤10m; alerted[^ai-tiers] |
| `snapshot` | `sys/storage/raft/snapshot` | — | least-priv backup identity |

The AI rows above are **actor roles**: they carry no path rules themselves, only
attach **actor-agnostic base capability policies** — `read-<svc>` / `write-<svc>`
(one pair per entry in `openbao_ai_domains`), plus `github-mint`. The rollups
`read-all` / `read-write-all` are lists of those base policy names (composition at
the token layer, no duplicated path rules). Adding a writable service is **one
entry** in `openbao_ai_domains`: it renders a new `read-<svc>`/`write-<svc>` pair,
auto-joins the rollups, mints an `ai-apply-<svc>` role, and becomes available to
any future actor (`human-*`, `ci-*`) that attaches the same base names. "Broad on
services, specific on users."

### Terrakube workload identity

The role enables JWT auth at `auth/terrakube` using the internal Terrakube API
as both OIDC discovery URL and bound issuer. Each fleet workspace in
`openbao_terrakube_workspaces` has its own `terrakube-<workspace>` role and
policy. The role binds audience
`openbao.workload.identity` and the exact subject
`organization:<openbao_terrakube_organization>:workspace:<workspace>`; a token from one workspace cannot
select another workspace's policy. Terrakube stores only the non-secret dynamic
credential controls. Provider credentials remain in their native OpenBao KV or
secrets-engine paths and are returned through a short-lived OpenBao token.

[^config-write]: A capability policy, not an identity — attached to
    `terraform-apply` (OpenTofu), `ansible-converge` (Ansible), and the
    per-workspace Terrakube JWT roles. It withholds `destroy` and `delete` on
    `metadata/*`, the two capabilities that permanently erase version history.

[^ai-tiers]: Task-scoped AI actor roles. Authorization is by task/blast-radius
    and human-gated, never by model capability (model is an audit claim). Every
    apply/admin role is inert (`manage_secret_id: false`) — a token exists only
    after a human response-wraps a single-use `secret_id`. Self-escalation is
    excluded **by construction**: the `read-<svc>`/`write-<svc>` base policies each
    grant EXACTLY one `secret/{data,metadata}/<svc>/*` path, so any union of them
    (`read-all`, `read-write-all`, any `ai-apply-*` role) can only widen KV reach —
    it can never name `sys/policies*`, `auth/*` (incl. `.../secret-id`),
    `auth/token/create`, or the IaC kernel (`secret/infra/*`). A bootstrap guard
    refuses to render a leaf for a forbidden subtree. `ai-admin` is the sole role
    that attaches a self-modify policy, and it is break-glass (≤10m, alerted).
    Full grant/redeem runbook: docs.dryvist.com "AI Agent Access (OpenBao)".

[^aws-sts]: Also grants `read`+`update` on `aws/sts/tf-proxmox` and
    `aws/sts/openbao-iac-admin` — dynamic AWS STS creds (assumed_role) for
    `role/tf-proxmox` and the broader, permissions-boundary-capped
    `role/openbao-iac-admin`, replacing static aws-vault base keys. See the
    AWS secrets engine section below.

**Secret-zero model**: each AppRole's `role_id`/`secret_id` is published to
Doppler tier-0 and reaches its consumer as ambient environment under
`doppler run` — access to Doppler tier-0 is the entire access boundary, not
the AppRole's own TTL (`secret_id_ttl=0` is intentional here, not an
oversight). The one exception is `public`: it needs no secret-zero at all,
since it only unlocks non-exploitable facts.

The policy/AppRole set is driven by `openbao_policies` / `openbao_approles` in
`defaults/main.yml` — add a row to grow the RBAC surface (a new policy template
goes beside the others in `templates/`). Adding a row **after** the cluster is
already initialized needs a privileged token supplied via `BAO_TOKEN` (see
[Idempotency](#idempotency)) — only the newly-added identities get created and
get fresh credentials; existing ones are untouched.

## AWS secrets engine (dynamic STS creds)

Mounted at `aws/` (add-if-missing, in `tasks/init.yml`) alongside the KV
engine. Purpose: eliminate the last static AWS key on the workstation — the
`terraform` IAM base user's aws-vault key, used only for
`sts:AssumeRole` into `role/tf-proxmox`.

**The AWS engine is NOT builtin to OpenBao** (dropped at the Vault fork; the
builtin secrets plugins are kv/pki/ssh/transit/totp/rabbitmq/ldap/kubernetes).
It ships as an external plugin from
[openbao/openbao-plugins](https://github.com/openbao/openbao-plugins) with
prebuilt, checksum-verified release binaries. The role therefore:

1. Stages the release tarball from the controller (same WAN-firewall staging
   pattern as the server .deb) and extracts the binary into
   `openbao_plugin_dir` on **every** node — the catalog is cluster-replicated
   but each node execs its own copy, which must match the registered sha256.
2. Points `plugin_directory` at it in `openbao.hcl` (always set; the dir
   always exists).
3. Verifies the publisher signature, archive hash, and extracted executable
   hash; installs an immutable version-qualified command on every voter.
4. Registers the semantic version in the catalog, mounts/tunes `aws/` to that
   version, and globally reloads the plugin after an upgrade. Previous
   commands/catalog versions remain available for rollback.

- `aws/config/root` holds the ONE long-lived base-user key OpenBao itself uses
  to call `sts:AssumeRole`. Seeded from `OPENBAO_AWS_ROOT_ACCESS_KEY_ID` /
  `OPENBAO_AWS_ROOT_SECRET_ACCESS_KEY` (Doppler tier-0). **Write-once**: a
  routine converge with root already configured never overwrites it — treat
  key rotation as a deliberate, separate operator action, same as the seal key.
  If the engine is mounted with no root config and no env key, the converge
  **fails loudly** rather than leaving a silently-dead engine.
- `aws/roles/tf-proxmox` (`credential_type=assumed_role`,
  `role_arns=arn:aws:iam::<acct>:role/tf-proxmox`,
  `default_sts_ttl=1h`, `max_sts_ttl=2h`) — declares the assumable role.
  Add-if-missing; bumping the TTLs on an existing role needs a manual
  `bao write` (not re-driven by a routine converge).
- `aws/roles/openbao-iac-admin` — a second, independent assumed_role broker
  for a broader IaC/admin identity capped by its own AWS permissions
  boundary (not tf-proxmox-scoped). Same shape as the role above
  (`default_sts_ttl=1h`, `max_sts_ttl=1h` — this role's AWS
  `MaxSessionDuration` is 3600s), same add-if-missing semantics.
- The `terraform-apply` AppRole reads `aws/sts/tf-proxmox` and
  `aws/sts/openbao-iac-admin` to mint a session — see the [^aws-sts] policy
  footnote above.
- The laptop side (nix-darwin `credential_process` wrapper reading
  `terraform-apply`'s `role_id`/`secret_id` secret-zero) is documented in the
  nix-darwin repo, not here.

## GitHub secrets engine (ephemeral GitHub App tokens)

Mounted independently at `github/` using
[`martinbaillie/vault-plugin-secrets-github`](https://github.com/martinbaillie/vault-plugin-secrets-github)
v2.3.2. It is a secrets engine, not the first-party `auth-github` login
plugin: callers authenticate to OpenBao through their existing AppRole and the
engine returns one-hour GitHub App installation tokens.

The release checksum manifest is verified with Martin Baillie's pinned signing
key before the Linux amd64 binary is checksum-verified and copied to every Raft
voter. The engine stores one dedicated GitHub App ID/private key in its own
encrypted mount configuration. The key is required only for first configuration
or an explicit rotation; routine converges never rewrite it.

Token access is tiered; the tier IS the privilege boundary:

- **read (`github-read`)** — `github/token/read-dryvist-all` and
  `github/token/read-personal-all`: all repos, read-only permission map stored
  in the set itself (the set path ignores request bodies, so a holder cannot
  widen it). Standing ambient AppRole.
- **write (`github-write`)** — the raw `github/token` endpoint, pinned to
  exactly ONE allowlisted repository per request: the policy requires
  `installation_id` + `repositories`, allowlists their values
  (`openbao_github_write_repo_allowlist`, value globs honored), and denies
  `permissions`, `org_name`, and `repository_ids` outright. Standing ambient
  AppRole, plus the claim-before-work write lease under
  `secret/locks/github-write/` (KV-v2 CAS acquire, `delete_version_after`
  deadman).
- **admin (`github-admin`)** — `github/token/dryvist-full-automation` and
  `github/token/personal-full-automation`: installation-wide, full App
  ceiling. INERT AppRole — a human response-wraps a single-use secret_id per
  elevation.

Estate identities (`ai-apply-*`, `ai-orchestrator`) attach the `github-mint`
capability policy, which grants the read-tier sets only. No policy except
`github-write` touches raw `github/token`; nothing but the converge edits
permission sets or engine configuration. AWS remains separately mounted and
authorized: `terraform-apply` can mint `aws/sts/tf-proxmox`, but has no
GitHub-engine grant.

First configuration requires `OPENBAO_GITHUB_APP_ID`,
`OPENBAO_GITHUB_APP_PRIVATE_KEY`, and the two account installation IDs. After
the sealed write succeeds, remove the temporary controller copy of the private
key. "Configured" means a non-zero `app_id` is stored — a virgin mount answers
the config read with `app_id: 0`, which must trigger first configuration, not
the drift refusal (issue #1079). A live acceptance run must issue and revoke
one token from each permission set — and prove an off-allowlist `github/token`
request is denied — before the engine is considered deployed.

## OAuthapp Slack workspace credential broker (OAuth V2 token rotation)

The `oauthapp/` mount brokers a short-lived JacobPEvans Slack workspace bot
token without storing it in KV. It is enabled by default. OAuthapp v3.3.0 is
pinned to its published archive SHA-256; upstream did not publish signed
provenance for this release, so the hash detects transport corruption but does
not authenticate the publisher. Treat an OAuthapp upgrade as a reviewed
supply-chain event.

The server uses `provider: custom`, not OAuthapp's built-in Slack provider:
the custom configuration targets Slack OAuth V2 (`oauth/v2/authorize` and
`api/oauth.v2.access`) and supports Slack token rotation. The Slack app must be
a dedicated development app with these exact settings:

- Redirect URL: `https://openbao.${PROXMOX_SUBDOMAIN}/oauth/slack/callback`
- Token rotation: enabled
- Bot scopes: `chat:write`, `chat:write.public`, `channels:read`,
  `channels:history`, `channels:join`, and `channels:manage`

This grants public-channel inventory, public-channel posting, joining existing
public channels, reading the public channels it has joined, and public-channel
management for channels it has joined or created. It does not grant access to
private channels, workspace administration, or user administration.

The Traefik callback route is an exact, high-priority `noop@internal` route:
it returns a fixed 418 and persists no query parameters. Traefik also drops all
query parameters from access logs. The browser URL still carries the one-time
`code` and `state`, which the operator transfers only after checking the exact
state value OpenBao generated. Do not put the callback behind Authelia; an SSO
redirect would break the OAuth return.

Initial server configuration needs `SLACK_OPENBAO_CLIENT_ID` and
`SLACK_OPENBAO_CLIENT_SECRET` during one privileged convergence. They are
written into OAuthapp's encrypted configuration and are deliberately not
rewritten by routine converges. The upstream firewall owner must allow every
OpenBao voter egress to `slack.com:443`; this role does not own that policy.

After the engine is converged and the Slack app is configured, an operator
performs the one-time authorization from a secure, no-history session:

```sh
callback="https://openbao.${PROXMOX_SUBDOMAIN}/oauth/slack/callback"
bao write -format=json oauthapp/auth-code-url \
  server=slack-poc redirect_url="$callback" \
  scopes=chat:write,chat:write.public,channels:read,channels:history,channels:join,channels:manage
```

First add the same six scopes under **Bot Token Scopes** in the existing Slack
app's **OAuth & Permissions** page, then reinstall it to the JacobPEvans
workspace. Open the returned URL, authorize the app, and verify the
browser-returned `state` is exactly the generated value. Then submit the
one-time code without recording it in shell history or logs:

```sh
bao write oauthapp/creds/slack-poc \
  server=slack-poc code="$CODE" redirect_url="$callback"
```

The workspace consumer policy can only read `oauthapp/creds/slack-poc`; it
cannot list credentials, configure a provider, or replace a refresh token. Its
OpenBao AppRole and secret ID are each limited to 15 minutes and the secret ID
is single-use. Slack access tokens themselves remain valid for Slack's 12-hour
rotation period, so revoking the OpenBao token only prevents future reads—not
use of a token already returned. Reauthorizing the same credential replaces its
stored Slack refresh state. Revoke the app/token in Slack first when retiring
access; do not rely on OpenBao lease revocation to invalidate an already-issued
Slack token.

## SSH secrets engine (signed client certificates — the SSH CA)

Mounted at `ssh-client-ca/` (add-if-missing, in `tasks/init.yml`). Implements
the `ssh-certificate-authority` ADR (docs site): automation authenticates to
estate hosts with **short-TTL SSH certificates** signed by an OpenBao CA;
humans stay on static `authorized_keys` so a CA outage can never lock a human
out. **SSH is a builtin engine** — no plugin staging, registration, or reload
apparatus; the block is enable + write-once CA + add-if-missing roles.

- `config/ca` is generated **inside OpenBao on first configuration**
  (`generate_signing_key=true`, `key_type` from `openbao_ssh_ca_key_type`,
  ed25519 per the ADR) and the private key is **never exported**. Write-once:
  a routine converge never regenerates it; rotation is a deliberate operator
  action via the multi-issuer API (append the new CA public key to hosts'
  trust file, re-sign via the new issuer, drop the old after cert TTL drain).
- The converge prints the CA public-key **fingerprint** — that value is the
  trusted-ceremony input pinned in `ansible-proxmox`'s `ssh_ca_trust` role
  (committed, human-reviewed) so host trust distribution can never
  trust-on-first-use a substituted endpoint.
- Signing roles are the ADR's per-principal-class table
  (`openbao_ssh_roles`): `automation-ai` (principal `ai-agent`, 1h,
  `permit-pty`), `automation-ansible` (`ansible`, 1h, no extensions),
  `ci-runner` (`ci`, 30m, no extensions). `ttl == max_ttl`; a sign request
  may shorten a cert's life, never extend it. Principals are always explicit
  — never `*`.
- One `ssh-sign-<role>` policy leaf per role grants exactly that role's
  `sign/` endpoint. Attachment follows the security decisions:
  `ssh-sign-automation-ai` → `ai-elevated` (standing, a documented tradeoff:
  friction-free agent SSH bounded by 1h certs, non-root principals,
  default-deny host opt-in, audit) + every `ai-apply-*`;
  `ssh-sign-automation-ansible` → `ansible-converge` only;
  `ssh-sign-ci-runner` → unattached until a CI identity exists.
- `OPENBAO_SSH_SOURCE_CIDRS` (Doppler) adds a `source-address` critical
  option restricting where certs are valid from; unset ⇒ loud warning and
  the guest-firewall default-deny layer is the compensating control.
- **ai-agent is never a hypervisor root principal** — PVE nodes map
  `root: [ansible]` only; `ai-agent` reaches guest-level accounts on hosts
  that opt in (see `ssh_ca_trust`).

## Break-glass handling (read this)

`bao operator init` produces **recovery** shares plus an initial **root token**.
With static-key auto-unseal the recovery shares are the only break-glass path if
the seal key is ever lost, so they are treated as paper secrets:

- On the initializing run, the role writes recovery shares + root token to
  `.openbao-recovery-<host>.json`. Every AppRole created THIS run — whether
  that's the initial bootstrap (all of them) or a later run against an
  already-live cluster that only grows the RBAC surface (just the new ones) —
  has its `role_id`/`secret_id` written to
  `.openbao-approle-<role>-<host>.json`, **all `0600`, on the controller,
  under `playbook_dir`**. Existing AppRoles' credentials are never re-emitted.
- Every `bao` invocation that touches this material runs with `no_log: true`.
- A **loud warning** names exactly which AppRoles were newly created and tells
  the operator to transcribe recovery shares to paper (+ Bitwarden), publish
  each new AppRole's creds to Doppler tier-0 (consumed as ambient env under
  `doppler run`), then **securely delete** the files.
- Nothing secret is ever written into the repo or onto a target host.

These controller files are gitignored (`.openbao-recovery-*.json` /
`.openbao-approle-*.json`). After transcription:

```sh
# Publish secret-zero to Doppler tier-0 (consumed as ambient env via `doppler run`).
doppler secrets set OPENBAO_APPROLE_<ROLE>_ROLE_ID="<role_id>" --project <proj> --config <cfg>
doppler secrets set OPENBAO_APPROLE_<ROLE>_SECRET_ID="<secret_id>" --project <proj> --config <cfg>
# `public` needs no secret-zero — it ships ambiently.
shred -u <playbook_dir>/.openbao-recovery-<host>.json
shred -u <playbook_dir>/.openbao-approle-*-<host>.json
```

## Idempotency

- The `.deb` is checksum-verified against the upstream `checksums-linux.txt`;
  `apt` skips re-install when the version is present.
- `tasks/init.yml` runs **only on the bootstrap host**. The very first
  `bao operator init` happens once (`initialized == false`); the KV mount,
  each policy, the AppRole auth method, and each AppRole are guarded so re-runs
  are no-ops for anything already present and unchanged.
- **Growing the RBAC surface on an already-live cluster is supported**: set
  `openbao_admin_token` (env `BAO_TOKEN`) to a privileged token so the role can
  authenticate without a fresh init; add rows to `openbao_policies` /
  `openbao_approles`; re-run. Missing or changed policies are written, only
  genuinely new AppRoles are created, and `role_id`/`secret_id` are surfaced
  **only for those** — existing identities and their credentials are never
  touched or re-emitted, so a routine converge without `BAO_TOKEN` set stays a
  complete no-op for this section.

## Seal-key rotation

Static-key rotation is n-1 → n: set `OPENBAO_STATIC_SEAL_PREVIOUS_KEY` (+
`_PREVIOUS_KEY_ID`) to the old key, re-render, and OpenBao rewraps to the new
`current_key`, then clear the previous-key vars.

## TLS

`tls_disable = 1` today: TLS terminates at Traefik on the internal VLAN in front
of OpenBao. End-to-end TLS (listener-native certs, `api_addr` → `https://`) is a
later hardening step noted inline in `templates/openbao.hcl.j2`.

## Testing

`molecule/openbao/` scaffolds a converge + verify scenario. Molecule is a
**CI-only gate** here (known-broken for local runs). The systemd-dependent tasks
(enable/start, health wait, and the entire bootstrap phase) are gated on
`ansible_virtualization_type != 'docker'`, so the container converge exercises
install + templating only — it asserts the rendered config carries `seal
"static"` + `retry_join` (not `awskms`) and binds the VLAN IP, never `0.0.0.0`.
The live HA join + init are verified against the real cluster
(`bao operator raft list-peers` shows 3 voters).

## Contributing

Pair any change with a `molecule test` run in CI (the local gate is
known-broken). Update this README and the variable table whenever a variable is
added, removed, or changes default. Keep the OpenBao version bump flowing through
`openbao_version` + Renovate — never scatter the version across files.

## License

Apache-2.0 — same as the parent repository.
