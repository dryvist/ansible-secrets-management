# Secrets engines

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

## OAuthapp secrets engine (mounted, no credential configured)

The `oauthapp/` mount brokers OAuth-based credentials without storing them in
KV. It is enabled by default and currently holds no configured server or
credential. OAuthapp v3.3.0 is pinned to its published archive SHA-256;
upstream did not publish signed provenance for this release, so the hash
detects transport corruption but does not authenticate the publisher. Treat
an OAuthapp upgrade as a reviewed supply-chain event.

Adding the first OAuth-brokered credential means adding its server
configuration, consumer AppRole/policy, and drift assertions to
`tasks/init.yml` and `defaults/main.yml` — see
`.claude/rules/openbao-plugins-first.md` for the engine-first policy this
mount exists to satisfy.

## Slack app-config token rotation (on-box timer)

An on-box `openbao-slack-rotate.timer` (every `openbao_slack_rotate_interval`,
default `6h`, jittered) keeps the Slack **app-configuration** token pair
(`secrets-external/platform/slack-admin` — distinct from the OAuthapp
workspace bot token above; this one authorizes `apps.manifest.create`/`.validate`)
rotated ahead of its ~12-hour expiry. It:

- authenticates with the least-privilege **`slack-admin` AppRole** (read+update
  on exactly that one KV-v2 entry);
- rotates only when the stored token is within `openbao_slack_rotate_safety_margin`
  (default 4h) of `expires_at` — every run logs its decision either way, including
  the no-op case;
- writes the new pair back with a CAS (check-and-set) request; on a CAS conflict
  or a rejected (already-consumed) refresh token, it re-reads and **adopts**
  whichever pair is newer instead of retrying — the refresh token is single-use,
  so that is the only coordination two writers need.

Deployed on **every** openbao node (no leader-gate needed — the single-use
refresh token is already the mutex) and gated on the AppRole creds being
present, same pre-provisioning-skip pattern as the snapshot timer above. A
macOS wrapper (`nix-darwin` `openbao-slack-creds`) also rotates on-demand if a
consumer sees a stale pair between fires; this timer is the primary, scheduled
rotator — the two are safe to run concurrently because of the CAS-adopt logic.

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
  (`openbao_ssh_roles`): `automation-ai` (principal `ai-agent`, 2h,
  `permit-pty`), `automation-ansible` (`ansible`, 2h, no extensions),
  `automation-semaphore` (`semaphore`, 2h, no extensions),
  `ci-runner` (`ci`, 30m, no extensions). TTLs are declared in seconds so the
  reconcile can compare them against the API without normalizing.
  `ttl == max_ttl`; a sign request may shorten a cert's life, never extend it.
  Principals are always explicit — never `*`.
- One `ssh-sign-<role>` policy leaf per role grants exactly that role's
  `sign/` endpoint. Attachment follows the security decisions:
  `ssh-sign-automation-ai` → `ai-elevated` (standing, a documented tradeoff:
  friction-free agent SSH bounded by 1h certs, non-root principals,
  default-deny host opt-in, audit) + every `ai-apply-*`;
  `ssh-sign-automation-ansible` → `ansible-converge` only;
  `ssh-sign-automation-semaphore` → `semaphore` only, so a certificate's
  principal identifies which caller ran a converge;
  `ssh-sign-ci-runner` → unattached until a CI identity exists.
- `OPENBAO_SSH_SOURCE_CIDRS` (Doppler) adds a `source-address` critical
  option restricting where certs are valid from; unset ⇒ loud warning and
  the guest-firewall default-deny layer is the compensating control.
- **ai-agent is never a hypervisor root principal** — PVE nodes map
  `root: [ansible, semaphore]` only; `ai-agent` reaches guest-level accounts on hosts
  that opt in (see `ssh_ca_trust`).
