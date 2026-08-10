# openbao

Installs and bootstraps [OpenBao](https://openbao.org/) — a native single Go
binary on Debian (no Docker) — as a **5-voter Raft HA cluster** with **on-prem
static-key auto-unseal** (no cloud KMS). After the cluster is live the role
provisions a KV v2 mount, the secret hierarchy, the RBAC policies, and one
AppRole per resource-domain identity (see
[Secret hierarchy and RBAC](docs/secrets-and-rbac.md)).

> **Before changing anything here, read
> [`.claude/rules/openbao-plugins-first.md`](../../.claude/rules/openbao-plugins-first.md).**
> Secrets engines are mandatory wherever one exists: GitHub tokens are minted
> from `github/token/<permission_set>` (estate identities attach the existing
> `github-mint` policy; the workstation tiers are `github-read` /
> `github-write` / `github-admin`) and AWS credentials from `aws/sts/<role>`.
> A static PAT or access key stored in KV is manual credential control and is
> rejected. KV is only for values no engine can mint.

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

## Docs

- [Architecture and resilience](docs/architecture-and-resilience.md) — the
  Raft/seal topology, voter health scoring, apply order, and rolling
  expansion/migration.
- [Installation and usage](docs/installation-and-usage.md) — how to reference
  the role and run it.
- [Secret hierarchy and RBAC](docs/secrets-and-rbac.md) — the KV mounts,
  policies, and AppRole-per-domain model.
- [Secrets engines](docs/secrets-engines.md) — AWS, GitHub, OAuthapp (Slack
  rotation), and SSH client-certificate signing.
- [Operations](docs/operations.md) — break-glass handling, idempotency,
  seal-key rotation, TLS, testing, contributing, and license.
