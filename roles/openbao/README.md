# openbao

Installs and bootstraps [OpenBao](https://openbao.org/) — a native single Go
binary on Debian (no Docker). Storage is integrated **Raft**; the master key is
sealed/unsealed automatically via **AWS KMS**. After the service is live the
role enables a KV v2 mount, writes a Terraform policy, and creates a Terraform
AppRole.

This node is **Raft node 1 of a planned 3-node cluster**. Additional nodes join
later via `bao operator raft join <api_addr of node 1>`; this role establishes
the leader and the bootstrap state the other nodes replicate.

## Apply order (important)

This role brings OpenBao live **before** anything that reads secrets from it.
In particular, the `terraform-proxmox` `vault-secrets` unit (which authenticates
with the Terraform AppRole created here) cannot run until this role has
initialized OpenBao and the operator has loaded `VAULT_ROLE_ID` /
`VAULT_SECRET_ID` into the tier-0 store. Sequence:

1. `aws-infra` — provision the KMS CMK + scoped unseal IAM user (out of band).
2. `terraform-proxmox` — provision the OpenBao LXC (VMID/IP/firewall).
3. **this role** — install + init OpenBao, mint the Terraform AppRole.
4. Operator — transcribe recovery shares to paper; load AppRole creds into
   Doppler.
5. `terraform-proxmox` `vault-secrets` — now able to authenticate.

## Installation

The role lives in this repository under `roles/openbao/`. Reference it from a
playbook in the `roles:` block — no Galaxy install needed:

```yaml
- hosts: openbao_group
  become: true
  roles:
    - role: openbao
```

Host membership in `openbao_group` is driven by the Terraform-exported
inventory: an LXC container tagged `openbao` is placed in `openbao_group` by
`inventory/load_tofu.yml` (add the tag-to-group mapping there alongside the
existing ones). The node's VLAN IP arrives as the `container_ip` hostvar.

## Usage

Wire the role into a play targeting `openbao_group`, with the KMS key and unseal
credentials injected from Doppler/SOPS at runtime:

```yaml
- name: Deploy OpenBao
  hosts: openbao_group
  become: true
  roles:
    - role: openbao
```

Run it through the repo's credentialed wrapper so the `OPENBAO_*` env vars are
present:

```sh
doppler run -- ansible-playbook playbooks/openbao.yml
```

On the **first** run the play initializes OpenBao and writes the break-glass
files to the controller (see below). On every subsequent run it is a no-op:
install is skipped (version already present) and the bootstrap steps short-
circuit on their existence checks.

## API

The role is variable-driven; see `defaults/main.yml` for the authoritative list
and the table above for the common knobs. There are no other entry points — the
two-file task split (`tasks/main.yml` install/config, `tasks/init.yml`
bootstrap) is internal. `init.yml` is gated on a non-Docker
`ansible_virtualization_type` so molecule converge exercises install + templating
without a live OpenBao.

## How it reads the inventory

- **`openbao_bind_address`** resolves to `container_ip` (LXC) → `ansible_host`
  (VM) → `ansible_default_ipv4.address`. The listener binds to this VLAN IP,
  never `0.0.0.0`.
- **`openbao_node_id`** defaults to `inventory_hostname` (stable Raft id).
- **`openbao_api_addr` / `openbao_cluster_addr`** are built from the bind
  address and the API/cluster ports.

## Variables

See `defaults/main.yml` for the authoritative list and inline rationale.
Highlights:

| Variable | Default | Purpose |
| --- | --- | --- |
| `openbao_version` | `2.5.4` | Pinned upstream release. Bumps follow the repo pinning/Renovate convention — change it here only, never hardcode elsewhere. |
| `openbao_user` / `openbao_group` | `openbao` | System account the service runs as. |
| `openbao_data_dir` | `/opt/openbao/data` | Raft data, `0700`, owned by `openbao`. |
| `openbao_config_dir` | `/etc/openbao` | Config + env file. |
| `openbao_api_port` | `8200` | API listener port. |
| `openbao_cluster_port` | `8201` | Raft cluster port. |
| `openbao_kv_mount` | `secret` | KV v2 mount path. |
| `openbao_homelab_path` | `homelab` | Subtree the Terraform policy may read/write. |
| `openbao_kms_key_id` | env `OPENBAO_KMS_KEY_ID` | CMK for auto-unseal. |
| `openbao_kms_region` | env `OPENBAO_KMS_REGION` (→ `us-east-1`) | KMS region. |
| `openbao_unseal_aws_access_key_id` | env | Scoped unseal IAM key (runtime only). |
| `openbao_unseal_aws_secret_access_key` | env | Scoped unseal IAM secret (runtime only). |
| `openbao_recovery_shares` / `_threshold` | `5` / `3` | Recovery-key split for `operator init`. |
| `openbao_enable_mlock` | `true` | mlock secrets out of swap (needs `CAP_IPC_LOCK`). |

AWS unseal credentials and the KMS key id are **never hardcoded or committed**.
They are injected at runtime from Doppler (`iac-conf-mgmt`) or SOPS into the
environment, read via `lookup('env', ...)`, and land in the `0600`
`openbao.env` systemd `EnvironmentFile` (root:openbao).

## Break-glass handling (read this)

With AWS-KMS auto-unseal, `bao operator init` produces **recovery** shares plus
an initial **root token**. These are the only break-glass path if KMS ever
becomes unavailable, so they are treated as paper secrets:

- On the run that initializes OpenBao, the role writes the recovery shares +
  root token to `.openbao-recovery-<host>.json` and the Terraform AppRole
  `role_id`/`secret_id` to `.openbao-approle-<host>.json`, **both `0600`, on the
  Ansible controller, under `playbook_dir`**.
- Every `bao` invocation that touches this material runs with `no_log: true`.
- The role prints a **loud warning** telling the operator to transcribe the
  recovery shares to paper (split across custodians, stored offline), load the
  AppRole creds into Doppler, then **securely delete** both files.
- Nothing secret is ever written into the repo or onto the target host.

**Gitignore these controller files.** The repo `.gitignore` already excludes
`.env*` and `*.secrets.yml`; add the break-glass globs if not covered:

```gitignore
.openbao-recovery-*.json
.openbao-approle-*.json
```

After transcription:

```sh
doppler secrets set VAULT_ADDR=http://<node-vlan-ip>:8200
doppler secrets set VAULT_ROLE_ID=<role_id>
doppler secrets set VAULT_SECRET_ID=<secret_id>
shred -u <playbook_dir>/.openbao-recovery-<host>.json
shred -u <playbook_dir>/.openbao-approle-<host>.json
```

## Idempotency

- The `.deb` is checksum-verified against the upstream `checksums-linux.txt`
  before install; `apt` skips a re-install when the version is already present.
- `tasks/init.yml` parses `bao status -format=json` and **only initializes when
  `initialized == false`**. The KV mount, policy, AppRole auth method, and the
  AppRole itself are each guarded by an existence check, so re-runs are no-ops.
- AppRole `role_id`/`secret_id` are surfaced **only on the initializing run**,
  so re-running never silently mints new credentials.

## TLS

`tls_disable = 1` today: TLS terminates at Traefik on the internal VLAN in front
of OpenBao. End-to-end TLS (listener-native certs, `api_addr` → `https://`) is a
later hardening step noted inline in `templates/openbao.hcl.j2`.

## Testing

`molecule/openbao/` scaffolds a converge + verify scenario matching the repo
convention. Molecule is a **CI-only gate** here and is known-broken for local
runs — do not run it locally. The systemd-dependent tasks (enable/start, health
wait, and the entire bootstrap phase) are gated on
`ansible_virtualization_type != 'docker'` so the container converge exercises
install + templating without needing a live OpenBao.

## Contributing

Pair any change to this role with a `molecule test` run in CI (the local gate is
known-broken). Update this README and the variable table whenever a variable is
added, removed, or changes default. Keep the OpenBao version bump flowing through
`openbao_version` + Renovate — never scatter the version across files.

## License

Apache-2.0 — same as the parent repository.
