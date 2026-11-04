# Secret hierarchy and RBAC

## Secret hierarchy & RBAC

Three KV v2 mounts, split by what a leak would cost. The split is a **mount**
and never a path prefix: a prefix shares one policy namespace, so every
wildcard already granted on `secret/` would reach across it.

| Mount | Holds | A leak costs |
| --- | --- | --- |
| `secret/` | Credentials for services reachable only inside the network | Bounded by network access |
| `secrets-external/` | Credentials for internet-reachable vendor APIs | Critical — exploitable by anyone, anywhere |
| `config/` | Non-secret configuration: operator selections, tunables, thresholds, coordination facts | Nothing exploitable by construction |

The `sandbox-agent-read` AppRole reads `secret/apps/sandbox-agent` and
`secret/apps/sandbox-agent-router`, then mints from the `public-read` GitHub
permission set. `sandbox-agent-write` reads both leaves and mints from
`public-write`. These roles read no other KV paths. Both require
`OPENBAO_SANDBOX_AGENT_CIDRS`, use 15-minute token limits, and have one-use
15-minute SecretIDs. The `open-llm` dispatcher can mint wrapped SecretIDs for
either role and reads the exact `secrets-external/ai/saas/zai` leaf. Its internal
leaf no longer carries the sandbox service tokens.

The `sandbox-zcode-read` and `sandbox-zcode-write` roles read only the Z.ai
provider leaf; `sandbox-opencode-read` and `sandbox-opencode-write` read only
`secret/apps/sandbox-agent-router`. Each mints the matching public GitHub token.
They share the sandbox CIDR, token lifetime, and one-use SecretID settings.
The dispatcher can read each role ID and mint wrapped SecretIDs for each role.

The Dify fleet `agent-code-simplifier`, `agent-ci-fixer`,
`agent-vikunja-clerk`, `agent-vikunja-triage`, and `agent-docs-updater`
AppRoles each mint only their matching named set on `github-agents`. All five
sets are scoped to public dryvist repositories. The code simplifier can write
pull-request reviews and read contents; the CI fixer can write contents and
pull requests, and read checks and actions; the Vikunja clerk, Vikunja triage,
and docs updater can read contents, pull requests, issues, and checks. These
roles read no KV paths; they use the `service-runtime` identity class and are
created only when `OPENBAO_DIFY_AGENT_CIDR` is set. Their SecretIDs last 720
hours, use the configured CIDR binding, and produce OpenBao tokens capped at
15 minutes.

`roles/openbao/defaults/main/08d-approle-taxonomy.yml` maps declared AppRoles
to the six identity classes. The AppRole initialization fails if any declared
role lacks a class. `ai-orchestrator` remains a `trusted-agent-write` migration
exception.

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
secret/core/       client                    # one shared client document
secret/ai/         hermes/ agents/          # LLM stack + AI-agent creds
secret/locks/      global                   # cross-repo apply lock state
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
| `apps` | Enumerated `secret/apps/*`; `secret/core/client` | — | The core path uses a separate exact policy |
| `bao-elevate-client` | `secret/core/client` | — | Workstation-bound; finite SecretID with Doppler-only rotation |
| `flow-lock` | `secret/locks/global`, `secret/infra/*` | `secret/locks/global` | Cross-repo apply lock; releases the lock via metadata delete |
| `azure-iac-admin` | `azure/creds/openbao-iac-admin` | — | Dynamic Azure client secret for the IaC admin application; per-call, workstation-only |
| `terrakube-<workspace>` JWT | Only that workspace's native paths | Workspace-specific | Short-lived; exact organization/workspace subject and audience |
| `ansible-converge` | Platform, apps, MCP secrets, `platform/ansible/env` per mount | Exact MCP secrets | Config pulls, MCP publishers; no broad AI access |
| `ansible-converge-writer` | Same as `ansible-converge` | Exact MCP secrets | Seed-play login; machine-bound batch token; 12h rotation |
| `observability` | `secret/platform/{splunk,cribl}`, `secret/ai/mcp/splunk` | — | Ingest pipeline and read-only Splunk MCP queries |
| `local-cloud` | `secret/platform/{object-storage,compute}` | — | RustFS + compute creds |
| `monitoring` | `secret/apps/monitoring` | — | netmon/unifi_metrics/prometheus_stack |
| `media` | `secret/apps/media` | — | *arr/qBittorrent/Plex stack |
| `local-llm` | `secret/ai/*` | — | The LLM serving stack itself |
| `clickhouse` | `secret/ai/clickhouse` data + metadata | — | Dedicated reader for the application and integration passwords |
| `clickhouse-ingest` | `secret/ai/clickhouse-ingest` data + metadata | — | Dedicated reader for the ClickHouse ingest writer password |
| `clickhouse-wall` | `secret/ai/clickhouse-wall` data + metadata | — | Dedicated reader for the ClickHouse wall reader password |
| `hatchet-killtest` | `secret/killtest/hatchet` | — | Power-only PVE token; per-call one-use secret_id; machine CIDR; 15m[^hatchet-killtest] |
| `hermes` | `secret/ai/hermes`, `secret/ai/mcp/splunk` | — | Dedicated least-privilege reader for Hermes; NO broad `secret/ai/*` |
| `hermes-write` | `secret/ai/hermes` | `secret/ai/hermes` | Narrow one-time credential seed writer; shared MCP publication belongs to `ansible-converge` |
| `agent-code-simplifier` | — | — | No KV grants; GitHub public repo `contents: read`, `pull_requests: write`; `service-runtime`; 15m token |
| `agent-ci-fixer` | — | — | No KV grants; GitHub public repo `contents`/`pull_requests: write`, `checks`/`actions: read`; `service-runtime`; 15m token |
| `agent-vikunja-clerk` | — | — | No KV grants; GitHub public repo `contents`/`pull_requests`/`issues`/`checks: read`; `service-runtime`; 15m token |
| `agent-vikunja-triage` | — | — | No KV grants; GitHub public repo `contents`/`pull_requests`/`issues`/`checks: read`; `service-runtime`; 15m token |
| `agent-docs-updater` | — | — | No KV grants; GitHub public repo `contents`/`pull_requests`/`issues`/`checks: read`; `service-runtime`; 15m token |
| `config-read` | all of `config/` | — | **Default** reader; mount-wide wildcard is correct here; shipped ambiently |
| `config-write` *(policy, no AppRole)* | all of `config/` | `config/` values: create/update/patch/soft-delete | Attached to the 3 IaC authors[^config-write] |
| `ai-orchestrator` | `secret/ai/{hermes,agents}` | `secret/ai/{hermes,agents}` (create/update) | WRITE; Doppler tier-0; narrowed + 30m TTL at Phase-3 |
| `ai-readonly` | `read-all` (= `read-<svc>` ∀ services) | — | **default AI agent; NO `secret/infra/*`**[^ai-tiers] |
| `ai-elevated` | `read-all` + `read-platform` | — | trusted infra-touching agents; no write[^ai-tiers] |
| `ai-apply-<svc>` | `read-<svc>` | `write-<svc>` + `github-mint` | Task-scoped WRITE, one service; no standing secret_id; ≤1h[^ai-tiers] |
| `ai-apply-all` | `read-write-all` | `read-write-all` + `github-mint` | Cross-domain WRITE rollup; no standing secret_id; ≤1h[^ai-tiers] |
| `ai-admin` | all KV + policy/auth admin | policy/AppRole/token, all KV, AWS STS | Break-glass; human-gated; alerted[^ai-tiers] |
| `ai-admin-session` | `ai-admin` | `ai-admin` + `tofu-state-admin` | Human-gated service-token session; 1h renewal / 12h explicit maximum; alerted[^ai-tiers] |
| `elevate-trusted` (`auth/authelia`) | `human-unlock` | secret_id mint, human-gated tiers | Phone-approved; 5m[^elevate] |
| `elevate-untrusted` (`auth/authelia`) | `human-unlock-untrusted` | secret_id mint, `ai-apply-<svc>` | Phone-approved, untrusted; 5m[^elevate] |
| `snapshot` | `sys/storage/raft/snapshot` | — | least-priv backup identity |

The `ai-admin-session` role also attaches `ai-admin-guard`, which
denies orphan and role-based token creation, edits or secret_id minting for
human-gated AppRoles, reads of or changes to `ai-admin`, `ai-admin-guard`, or either
human-unlock policy, enabling, disabling or tuning auth methods and audit
devices, userpass or MFA settings, and
moving or retuning the Enterprise owner-token mount. Plain child-token creation
and listing auth methods and audit devices remain allowed. The one-shot
`ai-admin` role stays unguarded; provisioning runs that change these objects use it.
The separate `tofu-state-admin` policy grants `update` only on the configured
Transit data-key plaintext and decrypt paths for the OpenTofu state key. The
reconcile policy pins its rendered body and attaches it to `ai-admin-session`
through the role's `token_policies` field.

### Identity and credential lifecycle

See [Identity and credential lifecycle](identity-and-credential-lifecycle.md) for
policy composition, workload identities, SecretID lifetime, source binding, and
reconciliation.

[^config-write]: A capability policy, not an identity — attached to
    `terraform-apply` (OpenTofu), `ansible-converge` (Ansible), and the
    per-workspace Terrakube JWT roles. It withholds `destroy` and `delete` on
    `metadata/*`, the two capabilities that permanently erase version history.

[^hatchet-killtest]: Its policy reads only the `secret/data/killtest/hatchet`
    leaf, outside `secret/apps/*`, so no standing AI reader reaches it.
    `approle-issuer` mints its one-use secret_id per Semaphore run; the issuer
    itself is `machine_or_workstation`, so a workstation can mint one, while
    redemption stays bound to the machine CIDR class; init refuses to create the
    role with an empty secret_id or token CIDR, even with the unbound escape
    hatch set. Four other policies reach the leaf: `ansible-converge`, which
    publishes the token; `openbao-reconcile` and the `ai-admin` break-glass
    policy, through `secret/*`; and `operator-human`, read only. AppRoles
    carrying them: `ansible-converge`, `ansible-converge-writer`, `semaphore`,
    `openbao-reconcile`, `openbao-policy-sync`, and break-glass `ai-admin`,
    `ai-admin-session`, `admin`. `secret-age-audit` reads only metadata.
    `tests/test_openbao_hatchet_killtest_policy_reach.py` asks an OpenBao dev
    server and fails on any other holder or AppRole.

[^ai-tiers]: Task-scoped AI actor roles. Authorization is by task/blast-radius
    and human-gated, never by model capability (model is an audit claim). Every
    apply/admin role is inert (`manage_secret_id: false`) — a token exists only
    after a human response-wraps a single-use `secret_id`. Self-escalation is
    excluded **by construction**: the `read-<svc>`/`write-<svc>` base policies each
    grant EXACTLY one `secret/{data,metadata}/<svc>/*` path, so any union of them
    (`read-all`, `read-write-all`, any `ai-apply-*` role) can only widen KV reach —
    it can never name `sys/policies*`, `auth/*` (incl. `.../secret-id`),
    `auth/token/create`, or the IaC kernel (`secret/infra/*`). A bootstrap guard
    refuses to render a leaf for a forbidden subtree. Only human-gated
    administrator roles attach the self-modify policy; both are alerted, and
    the session role has an explicit 12h hard maximum.
    The operator runbook covers the full grant/redeem flow.

[^elevate]: JWT roles on the `authelia` mount. Each binds one client audience
    and the operator `sub`, both from the environment, plus the workstation
    source class. A token carries only the listed policy, lasts 5m, and cannot
    renew.

[^aws-sts]: Also grants `read`+`update` on `aws/sts/tf-proxmox` and
    `aws/sts/openbao-iac-admin` — dynamic AWS STS creds (assumed_role) for
    `role/tf-proxmox` and the broader, permissions-boundary-capped
    `role/openbao-iac-admin`, replacing static aws-vault base keys. See the
    AWS secrets engine section below.

### How a human gets break-glass now

See [Break-glass access](break-glass-access.md) — the `human-unlock` login
flow, TOTP enrolment order, and how the policy/AppRole set grows.
