# openbao

Installs and bootstraps [OpenBao](https://openbao.org/) — a native single Go
binary on Debian (no Docker) — as a **5-voter Raft HA cluster** with **on-prem
static-key auto-unseal** (no cloud KMS). After the cluster is live the role
provisions a KV v2 mount, the secret hierarchy, the RBAC policies, and one
AppRole per resource-domain identity (see
[Secret hierarchy and RBAC](docs/secrets-and-rbac.md)).

> **Before changing anything here, apply the plugins-first rule.**
> Secrets engines are mandatory wherever one exists: GitHub tokens are minted
> from a GitHub App mount (`github/token/<permission_set>` or a tier-scoped raw
> `/token` endpoint). Estate identities attach the existing `github-mint`
> policy; workstation tiers include `github-read`, `github-write`,
> `github-admin`, `github-enterprise-read`, and `github-enterprise-admin`.
> AWS credentials come from `aws/sts/<role>`.
> Static PATs and access keys in KV are rejected as substitutes for
> engine-minted credentials. The one stored-token exception is the GitHub
> Enterprise owner token: human-unlock can write it to a dedicated KV v2 mount,
> and only the admin tiers can read it.
>
> The human-gated GitHub tiers include `github-admin`,
> `github-enterprise-read`, and `github-enterprise-admin`; see the GitHub
> secrets-engine guide for their mount and token boundaries.
>
> The `ci-resolver` AppRole mints short-lived GitHub tokens from its explicit
> repository set and reads only its own `apps/ci-resolver` bucket.

## Installation

The role lives in this repository under `roles/openbao/`. Reference it from
`playbooks/site.yml` (or any play targeting `openbao_group`) — see
[Installation and usage](docs/installation-and-usage.md) for the full
walkthrough, including bootstrap-host selection and required environment.

## Usage

```yaml
- hosts: openbao_group
  become: true
  roles:
    - role: openbao
```

Bootstrap (init/unseal/RBAC/AppRoles) runs once, on the bootstrap host only;
every other Raft peer joins and self-unseals automatically. Full details,
including rolling expansion and seal-key rotation, are in
[Installation and usage](docs/installation-and-usage.md) and
[Operations](docs/operations.md).

### Single-object RBAC and AppRole config runs

The optional `openbao_rbac_policy_name` and `openbao_approle_config_name`
variables select one exact declared and manageable policy or AppRole. They are
empty by default, which keeps the full-set behavior. A selected run rejects an
unknown or ambiguous name and cannot run with `openbao_reconcile_mode: true`.
Policy templates and global collision/undeclared-role/CIDR checks still cover
the full declared set. AppRole config runs do not issue secret IDs.
Runs limited to `openbao_rbac` or `openbao_approle_config` use the existing
installation and running service. Package installation and upgrades use
`openbao_install`; server configuration and startup use `openbao_config`.
Full role and `openbao_bootstrap` runs include both phases.

Run one target per invocation through the approved runner and provisioning-token
path:

```sh
semaphore-run-ansible.sh --rail-sec=600 ./scripts/run-ansible.sh playbooks/site.yml \
  --tags openbao_rbac --limit openbao_group,localhost --diff \
  -e '{"openbao_rbac_policy_name":"<policy-name>"}'
```

```sh
semaphore-run-ansible.sh --rail-sec=600 ./scripts/run-ansible.sh playbooks/site.yml \
  --tags openbao_approle_config --limit openbao_group,localhost --diff \
  -e '{"openbao_approle_config_name":"<approle-name>"}'
```

A full-set RBAC run replaces the stored text of every existing policy whose
rendered text differs from live. Before any write, that run stops unless each
such policy is named in `openbao_policy_change_ack`. The failure message names
the policies and never their text. Creating a missing policy needs no ack, and
a single-object run (`openbao_rbac_policy_name`) is its own ack.

```sh
-e '{"openbao_policy_change_ack":["<policy-name>"]}'
```

When a config or unit change notifies a restart, only the voters that changed
restart. They restart one at a time, with the active voter last. Each voter
must report initialized, unsealed and joined before the next one restarts. If
a voter does not come back within the retry window, the play fails and no
other voter restarts.

## Docs

- [Architecture and resilience](docs/architecture-and-resilience.md) — the
  Raft/seal topology, voter health scoring, apply order, and rolling
  expansion/migration.
- [Installation and usage](docs/installation-and-usage.md) — how to reference
  the role and run it.
- [Secret hierarchy and RBAC](docs/secrets-and-rbac.md) — the KV mounts,
  policies, and AppRole-per-domain model.
- [Generated app secrets](docs/generated-app-secrets.md) — credential field
  ownership and app-path access boundaries for the generated-secret catalog.
- [Break-glass access](docs/break-glass-access.md) — the human-unlock login
  flow and TOTP enrolment order.
- [GitHub secrets engine](docs/github-engine.md) — App mounts, permission
  sets and token tiers.
- [Secrets engines](docs/secrets-engines.md) — AWS, OAuthapp, the
  table-driven credential rotation timers (Slack, Splunk MCP), and SSH
  client-certificate signing.
- [Operations](docs/operations.md) — break-glass handling, idempotency,
  seal-key rotation, TLS, testing, contributing, and license.
