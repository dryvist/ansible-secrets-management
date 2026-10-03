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

## GitHub secrets engine

See [GitHub secrets engine](github-engine.md).

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

## Credential rotation (on-box timers, table-driven)

`openbao_rotators` (`defaults/main/09-snapshots-and-rotation.yml`) is a
declaration table, not a set of one-off timers: every entry becomes an
identically-shaped systemd service+timer pair (rendered by
`tasks/rotate.yml` from the generic `templates/openbao-rotate.*.j2`
templates), differing only in which upstream mint the rendered script
delegates to (`mint:`, resolved to `templates/rotators/<mint>.sh.j2`) and
which KV entry it rotates (`target:`). Deployed on **every** node — each
mint owns its own concurrency story rather than the deploying task
leader-gating anything. A rotator whose AppRole creds are not yet present is
skipped for that run, the same pre-provisioning-skip pattern as the snapshot
timer above, so a first-bootstrap converge stays green. Adding a rotator is
one table row plus a least-privilege AppRole/policy pair, and — if the mint
doesn't exist yet — one new `templates/rotators/<mint>.sh.j2` fragment.

After every successful rotation, the generic wrapper stamps
`custom_metadata.rotated_<FIELD>` (UTC ISO-8601) on the target KV entry —
the per-field rotation clock a sibling auditor (`secret-age-audit`) reads.

### `slack-admin` — Slack app-config token rotation

Keeps the Slack **app-configuration** token pair
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

No leader-gate needed — the single-use refresh token is already the mutex. A
macOS wrapper (`nix-darwin` `openbao-slack-creds`) also rotates on-demand if a
consumer sees a stale pair between fires; this timer is the primary, scheduled
rotator — the two are safe to run concurrently because of the CAS-adopt logic.

### `splunk-mcp` — Splunk MCP token rotation

Keeps the shared Splunk MCP bearer token (`secret/ai/mcp/splunk`, field
`SPLUNK_MCP_TOKEN`) fresh for AI agents/MCP clients. Mirrors the mint/probe/
publish/reconcile invariants of `ansible-splunk`'s
`roles/splunk_docker/tasks/manage_one_user.yml`, run here from the OpenBao
side on a schedule instead of at Splunk-converge time:

- authenticates with the least-privilege **`splunk-mcp-rotate` AppRole**
  (read its own minter credentials at `secret/apps/splunk-rotator`; read+
  update `secret/ai/mcp/splunk`; read+patch its metadata);
- decides freshness from the `rotated_SPLUNK_MCP_TOKEN` stamp (falling back
  to the KV entry's `updated_time` on first run) against
  `openbao_rotation_target_days` (default 30d);
- mints via `GET .../services/mcp_token` and **proves the new token works**
  against the MCP JSON-RPC `initialize` endpoint *before* it ever reaches
  OpenBao — a failed probe leaves the published field untouched;
- CAS-writes **only** the `SPLUNK_MCP_TOKEN` field, preserving every sibling
  field in the secret — a CAS conflict here **fails loud** rather than
  adopting (unlike Slack, this mint has no single-use-token mutex to make an
  adopt safe);
- once published, revokes every *other* eligible MCP-audience token for the
  user so exactly one canonical token exists.

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
- `host-cert` (`cert_type: host`) signs HOST certs under the same CA instead:
  `allow_host_certificates`, `allowed_domains` (the apex zone guest FQDNs
  live under), `allow_subdomains`, no bare domains, 90d `ttl`/`max_ttl`, no
  principal/extensions. `openbao_ssh_user_roles` is the derived,
  user-cert-only view for consumers that read `principal`/`extensions`
  unconditionally.
- One `ssh-sign-<role>` policy leaf per **user-cert** role
  (`openbao_ssh_user_roles`; host-cert gets no leaf of its own) grants
  exactly that role's `sign/` endpoint: `automation-ai` → `ai-elevated` +
  every `ai-apply-*`; `automation-ansible` → `ansible-converge` only;
  `automation-semaphore` → `semaphore` only; `ci-runner` unattached. Host
  certs get no `ssh-sign-host-cert` policy (a new name needs a privileged
  provisioning run) — `openbao_ssh_host_cert_signer_roles`
  (`automation-{ansible,semaphore}`) instead folds an update-only grant on
  every host-cert `sign/` endpoint into those two leaves' own content.
- `OPENBAO_SSH_SOURCE_CIDRS` (Doppler) adds a `source-address` critical
  option restricting where certs are valid from; unset ⇒ loud warning and
  the guest-firewall default-deny layer is the compensating control.
- **ai-agent is never a hypervisor root principal** — PVE nodes map
  `root: [ansible, semaphore]` only; `ai-agent` reaches guest-level accounts on hosts
  that opt in (see `ssh_ca_trust`).
