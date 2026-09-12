# Operations

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
  `openbao_provisioning_token` (env `OPENBAO_PROVISIONING_TOKEN`) to a privileged token so the role can
  authenticate without a fresh init; add rows to `openbao_policies` /
  `openbao_approles`; re-run. Missing or changed policies are written, only
  genuinely new AppRoles are created, and `role_id`/`secret_id` are surfaced
  **only for those** — existing identities and their credentials are never
  touched or re-emitted, so a routine converge without that variable set stays a
  complete no-op for this section.

## Seal-key rotation

Static-key rotation is n-1 → n: set `OPENBAO_STATIC_SEAL_PREVIOUS_KEY` (+
`_PREVIOUS_KEY_ID`) to the old key, re-render, and OpenBao rewraps to the new
`current_key`, then clear the previous-key vars.

## Rotating a secret on demand

`playbooks/rotate-key.yml` rotates one field of one KV v2 entry, writing under
that domain's own `<DOMAIN>-rotate` AppRole rather than the read-only identity
a converge uses. It never invents a field — the target field must already
exist — and it refuses a path whose `custom_metadata.rotation` is `exempt`.

Every `<DOMAIN>-rotate` AppRole except `media-rotate` is **inert**
(`manage_secret_id=false`, `secret_id_ttl=15m`, `num_uses=1`): there is no
standing secret_id to read from the environment. A human issues a wrapped,
single-use one and hands it to the playbook — that wrap IS the approval, the
same pattern as the `ai-apply-<svc>` tier:

```bash
bao write -wrap-ttl=5m -f auth/approle/role/ai-rotate/secret-id
# hand the wrapping_token from that output to the playbook:
ROTATE_WRAPPING_TOKEN=<wrapping_token> doppler run -- ansible-playbook playbooks/rotate-key.yml \
  -e rotate_mount=secret -e rotate_path=ai/mcp/splunk \
  -e rotate_field=SPLUNK_MCP_TOKEN -e rotate_domain=ai
```

`media-rotate` keeps its legacy standing Doppler pair
(`MEDIA_ROTATE_VAULT_ROLE_ID`/`_SECRET_ID`) — no wrap needed there:

```bash
doppler run -- ansible-playbook playbooks/rotate-key.yml \
  -e rotate_domain=media -e rotate_entry=prowlarr -e rotate_field=PROWLARR_API_KEY
```

Rotating a field this repo cannot mint itself (a third-party API issues the
value) — `rotate_mint` names an `openbao-rotate-<value>.service` unit already
deployed on the OpenBao cluster; the playbook only triggers it, waits for it
to finish, and proves the read-back:

```bash
bao write -wrap-ttl=5m -f auth/approle/role/ai-rotate/secret-id
ROTATE_WRAPPING_TOKEN=<wrapping_token> doppler run -- ansible-playbook playbooks/rotate-key.yml \
  -e rotate_domain=ai -e rotate_entry=some-api -e rotate_field=SOME_API_KEY \
  -e rotate_mint=some-api
```

**The re-converge is always a separate, later process.** Roles read secrets
with `lookup('env', ...)`, resolved once from the environment the ansible
process started with — a value written to OpenBao mid-run is invisible to the
run that wrote it. Chaining rotation and re-converge in one playbook would
appear to work and would silently leave every consumer on the old value:

```bash
doppler run -- scripts/fetch-openbao-secrets.sh media -- \
  scripts/run-ansible.sh playbooks/site.yml
```

## Publishing a generated app secret to GitHub Actions

Some `openbao_generated_app_secrets` values exist only to be read by a
GitHub Actions workflow in another repository — for example the
`github-actions` and `prometheus` router virtual keys, generated here and
registered by `ansible-proxmox-ai`'s `roles/llm_router` (`seed-keys.yml`).
Generating the value here does not make it reach GitHub: GitHub Actions
secrets in this org are Doppler-managed end to end, and no automation in any
repo writes to the GitHub secrets API directly — the GitHub App backing every
minted token deliberately holds no `secrets`/`variables` permission, so a
call against `/actions/secrets` 403s by design, not by accident.

Publishing a newly generated value is therefore a one-time, human step, never
an agent-reachable one:

1. Read the value: `bao kv get -field=<field> {{ openbao_kv_mount }}/apps/<app>`
   with the read-only AppRole; no write unlock needed.
2. Put it, masked, in the Doppler project/config that syncs to the target
   GitHub org or repo's Actions secrets:
   `doppler secrets set <NAME>="<value>" --project <proj> --config <cfg>`.
3. Let the existing Doppler → GitHub sync propagate it. Never set the value
   directly in the GitHub UI or API — the next sync overwrites it, which
   reads as unexplained drift.

This is why a virtual key can sit generated-and-unseeded for a while without
anything being broken: the router registers it once the OpenBao value exists,
and reaching GitHub Actions is a separate manual step against a different
secret store. An agent that finds a CI workflow failing on a missing secret
(`LLM_ROUTER_API_KEY`, `LLM_ROUTER_BASE_URL`, or any other Doppler-synced
value) should report which key is missing in which repo and stop — this step
has no agent-reachable path.

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
