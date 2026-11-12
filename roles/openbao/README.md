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

### Selective object runs

`openbao_select` maps object kinds to lists of exact names or shell globs
(`*`, `?`, and bracket ranges). Its default `{}` keeps full-set behavior.
The retired `openbao_rbac_policy_name` and `openbao_approle_config_name` inputs still
select one object. Passing either beside `openbao_select` fails the run.
Supported kinds are `policies`, `approles`, `ssh_roles`,
`github_permission_sets`, `rotation_exempt`, and `reconcile_policy`.
The singleton `reconcile_policy` kind selects the declared
`openbao_reconcile_policy_name`, syncs only that policy, and shows its diff in check mode.
GitHub permission-set names come from `openbao_github_admin_permission_sets`
on `openbao_github_mount`. Rotation-exempt names use the declared `mount:path`
form. Every selector must
match a declared, manageable object. Names are printed before phase writes.
`openbao_select_max` caps the combined resolved set across kinds at 25 by
default; set a larger positive integer for a larger reviewed batch.

With a nonempty selection, omitted kinds are skipped, and retired-object
deletes and credential issuance are skipped. Policy templates render only for
selected policies. Global collision, undeclared-role, and CIDR checks retain the
full declared set.
AppRole selection changes only config, policy attachments, and bounds.
GitHub permission-set selection runs with `openbao_rbac` or `openbao` tags and
uses the run's own identity. In check mode, `Would write GitHub permission sets:`
lists only selected sets that are missing or differ from live. A real run writes
those selected changes.
Reconcile mode requires both a manageable declaration and a live capability
grant for every selected write endpoint before phase writes. A protected or
ungranted selection fails with its name and requires the human-gated path.

KV seeding also writes a separate policy, so selective runs skip that phase.
Engine and auth setup also write mounts, keys, and shared configuration;
credential issuance also publishes credentials. Those phases, human-gated
AppRole attachment updates, and the singleton disclosure metadata declaration
run only in full-set mode. SSH engine and CA setup likewise stay
in full-set mode; SSH signing-role and GitHub permission-set objects remain
selectable.

Roster collision checks compare AppRole policy attachments through per-field
reads with the declared policy parameter; reconcile retains the write bounds.
Runs limited to `openbao_rbac` or `openbao_approle_config` use the existing
installation and running service. Package installation and upgrades use
`openbao_install`; server configuration and startup use `openbao_config`.
Full role and `openbao_bootstrap` runs include both phases.

Select a batch across kinds through the approved runner:

```sh
semaphore-run-ansible.sh --rail-sec=600 ./scripts/run-ansible.sh playbooks/site.yml \
  --tags openbao_rbac,openbao_approle_config --limit openbao_group,localhost --diff \
  -e '{"openbao_select":{"policies":["read-apps","terrakube-*"],"approles":["ai-sessions-backup"]}}'
```

A full-set RBAC run replaces the stored text of every existing policy whose
rendered text differs from live. Before the RBAC write loop, changed existing
text stops the run and prints an exact selection command naming those policies.
Selection acknowledges text changes only for the selected objects. Creating
missing policies requires no text-change acknowledgement.

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
