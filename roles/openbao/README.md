# openbao

Installs and bootstraps [OpenBao](https://openbao.org/) — a native single Go
binary on Debian (no Docker) — as a **5-voter Raft HA cluster** with **on-prem
static-key auto-unseal** (no cloud KMS). After the cluster is live the role
provisions a KV v2 mount, the secret hierarchy, the RBAC policies, and one
AppRole per resource-domain identity (see [Secret hierarchy & RBAC](#secret-hierarchy--rbac)).

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

## Apply order (important)

This role brings OpenBao live **before** anything that reads secrets from it.

1. Generate the seal key once (`openssl rand -base64 32`) and load it into
   Doppler tier-0 as `OPENBAO_STATIC_SEAL_KEY` (+ `OPENBAO_STATIC_SEAL_KEY_ID`).
2. `terraform-proxmox` — provision the 5 OpenBao LXCs (VMID/IP/firewall).
3. **this role** — install + init the cluster, mint the AppRoles.
4. Operator — transcribe recovery shares to paper (+ Bitwarden); load each
   AppRole's `role_id`/`secret_id` into its own item in the dedicated
   `openbao.keychain-db` keychain — except `public`, which is NOT
   keychain-gated (see [Secret hierarchy & RBAC](#secret-hierarchy--rbac)).
5. `terraform-proxmox` `vault-secrets` — now able to authenticate as
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
3. `terraform-proxmox` apply creates the five new LXCs; then run this role with
   `--limit openbao_group,localhost`.
4. **Verify before Phase 2:** `bao operator raft list-peers` shows all 7;
   `bao operator raft autopilot state` shows 7 healthy voters; a read of a known
   secret succeeds from a NEW node. Do not proceed until healthy.

**Phase 2 — remove the old nodes (shrink to the clean 5):**

1. `bao operator raft remove-peer openbao-01` then `... openbao-02`.
2. Drop `openbao-01`/`openbao-02` from `deployment.json`; `terraform-proxmox`
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

The KV v2 mount `secret/` is organized by category (canonical doc:
`terraform-proxmox` `docs/SECRETS_HIERARCHY.md`):

```text
secret/infra/      proxmox/ aws/ network/   # IaC kernel — terraform-apply writes
secret/platform/   dns/ traefik/ terrakube/ splunk/ cribl/ object-storage/ compute/
secret/apps/       media/ monitoring/ home-automation/
secret/ai/         hermes/ agents/          # LLM stack + AI-agent creds
secret/public/     domain/ ...              # non-secret, non-exploitable facts
secret/ci/         github/ doppler-sync/
```

One AppRole per resource-domain identity, each bound to a least-privilege
policy — split so no identity spans both an infra-writing role and an
untrusted execution surface (Terrakube runs VCS-driven, potentially untrusted
plans):

| AppRole | Reads | Writes | Notes |
| --- | --- | --- | --- |
| `terraform-apply` | `secret/infra/*`, `secret/platform/{dns,traefik}`, legacy `homelab/*` | same | Human-triggered IaC apply |
| `terrakube-plan` | `secret/platform/terrakube` only | — | Terrakube VCS-driven runs; deliberately walled off from `secret/infra/*` |
| `ansible-converge` | `secret/platform/*`, `secret/apps/*` | — | Config-management pulls |
| `observability` | `secret/platform/{splunk,cribl}` | — | Ingest pipeline (shared HEC tokens) |
| `local-cloud` | `secret/platform/{object-storage,compute}` | — | RustFS + compute creds |
| `monitoring` | `secret/apps/monitoring` | — | netmon/unifi_metrics/prometheus_stack |
| `media` | `secret/apps/media` | — | *arr/qBittorrent/Plex stack |
| `local-llm` | `secret/ai/*` | — | The LLM serving stack itself |
| `hermes` | `secret/ai/hermes` only | — | Dedicated least-privilege reader for the Hermes agent; NO broad `secret/ai/*` |
| `public` | `secret/public/*` | — | **Anonymous** — creds NOT keychain-gated; shipped ambiently |
| `ai-orchestrator` | `secret/ai/*` | `secret/ai/*` (create/update) | AI agent/orchestrator WRITE identity; role_id/secret_id **operator-held in the macOS keychain**, not Doppler-managed |
| `ai-readonly` | `secret/ai/*`, `secret/apps/*` | — | **default AI agent; NO `secret/infra/*`** |
| `ai-elevated` | `ai-readonly` + `secret/platform/*` | — | trusted infra-touching agents; no write |
| `snapshot` | `sys/storage/raft/snapshot` | — | least-priv backup identity |

**Secret-zero model**: each AppRole's `role_id`/`secret_id` lives as its own
item in a dedicated macOS keychain (`openbao.keychain-db`, 72h auto-lock) —
the keychain's LOCK STATE is the entire access boundary, not the AppRole's own
TTL (`secret_id_ttl=0` is intentional here, not an oversight). The one
exception is `public`: its credential is deliberately NOT keychain-gated,
since it only unlocks non-exploitable facts.

The policy/AppRole set is driven by `openbao_policies` / `openbao_approles` in
`defaults/main.yml` — add a row to grow the RBAC surface (a new policy template
goes beside the others in `templates/`). Adding a row **after** the cluster is
already initialized needs a privileged token supplied via `BAO_TOKEN` (see
[Idempotency](#idempotency)) — only the newly-added identities get created and
get fresh credentials; existing ones are untouched.

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
  the operator to transcribe recovery shares to paper (+ Bitwarden), load each
  new AppRole's creds into its own item in the `openbao.keychain-db` keychain,
  then **securely delete** the files.
- Nothing secret is ever written into the repo or onto a target host.

These controller files are gitignored (`.openbao-recovery-*.json` /
`.openbao-approle-*.json`). After transcription:

```sh
security add-generic-password -s "openbao/<domain>" -a role_id -w <role_id> \
  ~/Library/Keychains/openbao.keychain-db
security add-generic-password -s "openbao/<domain>" -a secret_id -w <secret_id> \
  ~/Library/Keychains/openbao.keychain-db
# `public` is the one exception — ships ambiently, never keychain-gated.
shred -u <playbook_dir>/.openbao-recovery-<host>.json
shred -u <playbook_dir>/.openbao-approle-*-<host>.json
```

## Idempotency

- The `.deb` is checksum-verified against the upstream `checksums-linux.txt`;
  `apt` skips re-install when the version is present.
- `tasks/init.yml` runs **only on the bootstrap host**. The very first
  `bao operator init` happens once (`initialized == false`); the KV mount,
  each policy, the AppRole auth method, and each AppRole are guarded by
  existence checks, so re-runs are no-ops for anything already present.
- **Growing the RBAC surface on an already-live cluster is supported**: set
  `openbao_admin_token` (env `BAO_TOKEN`) to a privileged token so the role can
  authenticate without a fresh init; add rows to `openbao_policies` /
  `openbao_approles`; re-run. Only the genuinely new policies/AppRoles are
  created, and `role_id`/`secret_id` are surfaced **only for those** — existing
  identities and their credentials are never touched or re-emitted, so a
  routine converge without `BAO_TOKEN` set stays a complete no-op for this
  section.

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
