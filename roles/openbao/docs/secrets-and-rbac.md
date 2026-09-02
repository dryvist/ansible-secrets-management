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
`doppler run`. Access to Doppler tier-0 is the primary access boundary, but it
is no longer the only one: a `secret_id` also carries a finite lifetime and a
redemption cap, and is bound to the network segment its holder is supposed to
sit on.

`secret_id_ttl: 0` used to be the standing default and was described here as
intentional. It was not defensible: it made every published credential
permanent, so any copy that escaped Doppler — a drop file left on a controller,
a value in a shell history — stayed a working credential until somebody noticed.
Nothing rotated them, so "rotate manually" never happened. The defaults are now
finite (`openbao_approle_secret_id_ttl`, `openbao_approle_secret_id_num_uses`
in `defaults/main/08-admin-and-ttls.yml`), with per-role overrides and a
documented reason required for any remaining `0`.

Source binding uses named CIDR classes (`machine` / `workstation` / `ci`), whose
values arrive by environment and are never committed. A class that a declared
role uses but which was never supplied **fails the converge** rather than
quietly creating the unbound role the binding exists to prevent.

The one exception throughout is `public`: it needs no secret-zero, no
redemption cap and no source binding, since it only unlocks non-exploitable
facts.

### How a human gets break-glass now

`admin` used to be standing: `role_id` plus a non-expiring, unlimited-use
`secret_id` in a personal keychain. It is now inert and bounded like every other
break-glass tier (1h token, 2h ceiling, 15m single-use `secret_id`), which only
works because there is a way to mint the next one without holding a standing
credential. That way is the `human-unlock` policy, attached to the operator's
own `userpass` user rather than to an AppRole — a person is not a workload, so
there is no secret-zero pair to store anywhere.

1. The operator logs in: `bao login -method=userpass username=<user>`, plus a
   TOTP passcode (enforced on the whole userpass mount).
2. They wrap a single-use `secret_id` for the tier they need:
   `bao write -wrap-ttl=90s -f auth/approle/role/admin/secret-id`.
3. They hand the wrapping token to the session, which unwraps it and logs in as
   `admin` — one login, then the token lives its 1h window.
4. Nothing persists. The `secret_id` was single-use and is spent; the token
   expires on its own.

`human-unlock` is the exact complement of `approle-issuer`: the issuer mints the
automatable roles (`manage_secret_id` unset), human-unlock mints the human-gated
tiers (`manage_secret_id: false`). Both derive their lists from that one marker,
so every role is mintable by exactly one of them and a new tier cannot be
forgotten by either. Neither can mint the other's set, and neither can write a
policy.

**Enrolment is a one-time human step and is deliberately not automated.** The
role declares the TOTP method (`identity/mfa/method/totp`) and the enforcement
(`identity/mfa/login-enforcement/<name>`, scoped to the userpass mount
accessor), but a converge that could enrol the second factor would be holding
it, which would make it not a second factor. Enrol once, as a human:

```
bao write identity/mfa/method/totp/admin-generate \
  method_id=<id> entity_id=<the operator's entity id>
```

**Order matters.** Enrol, then verify a full userpass+TOTP login, and only then
destroy the standing `admin` secret_id — the enforcement is live as soon as the
converge applies it, so an unenrolled user cannot log in.

The role never sets or reads the password. It updates only the `token_*` fields
on an existing user (OpenBao writes the password only when that parameter is
explicitly present), and if the user does not exist the converge fails with an
instruction rather than creating a passwordless administrator.

The policy/AppRole set is driven by `openbao_policies` / `openbao_approles` in
`defaults/main.yml` — add a row to grow the RBAC surface (a new policy template
goes beside the others in `templates/`). Adding a row **after** the cluster is
already initialized needs a privileged token supplied via `BAO_TOKEN` (see
[Idempotency](operations.md#idempotency)) — only the newly-added identities get created and
get fresh credentials; existing ones are untouched.

