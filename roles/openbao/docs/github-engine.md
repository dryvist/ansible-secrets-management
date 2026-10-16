# GitHub secrets engine (ephemeral GitHub App tokens)

Mounted independently at `github/` using
[`martinbaillie/vault-plugin-secrets-github`](https://github.com/martinbaillie/vault-plugin-secrets-github)
v2.3.2. It is a secrets engine, not the first-party `auth-github` login
plugin: callers authenticate to OpenBao through their existing AppRole and the
engine returns one-hour GitHub App installation tokens.

The release checksum manifest is verified with Martin Baillie's pinned signing
key before the Linux amd64 binary is checksum-verified and copied to every Raft
voter. Each mount stores one GitHub App ID/private key in its own encrypted
configuration, so each App's own grant caps every token its mount mints:

| Mount | App | Permission sets |
| --- | --- | --- |
| `github` | everyday | read sets and the raw `github/token` write endpoint |
| `github-admin` | admin | admin, repo-create, docs-publisher, ci-resolver, runner, exporter |
| `github-agents` | agents | none: `open-llm` uses the raw `github-agents/token` with caller-selected org and repository fields |
| `github-hermes` | hermes | `hermes-{review,author}-{public,private}`, split by repository visibility |
| `github-work` | work | `work-read`, `work-write` and operator-gated `work-admin`, all pinned to the work installation; no administration |
| `github-enterprise-read` | read-only Enterprise App | none: raw token endpoint, pinned to its installation |
| `github-enterprise` | admin Enterprise App | none: raw token endpoint, pinned to its installation |

The Enterprise owner token is stored separately in the `github-enterprise-owner`
KV v2 mount. The human-unlock login can create or replace it; only the admin
tiers can read its data and metadata.

A key is required only for first configuration or an explicit rotation; routine
converges never rewrite it. Installation IDs come from the env document
(`secret/platform/ansible/env`).

The everyday App accepts extra read installations through
`OPENBAO_GITHUB_EXTRA_READ_INSTALLATION_IDS`, as a comma-separated list of
`owner=id` entries. Read entries add named read sets and never grant write
access.

Token access is tiered; the tier IS the privilege boundary:

- **read (`github-read`)** — `github/token/read-dryvist-all` and
  `github/token/read-personal-all`: all repos, read-only permission map stored
  in the set itself (the set path ignores request bodies, so a holder cannot
  widen it). Standing ambient AppRole. The `semaphore` AppRole names the exact
  paths `github/token/read-dryvist-all` and `github/token/read-jpe-cribl-all`,
  with no wildcard, so the unattended Ansible execution plane can check out
  the repositories it runs and the Cribl pack mirror can look up releases
  without holding a stored token. Read only: these grants cannot write a
  repository.
- **write (`github-write`)** — the raw `github/token` endpoint; the policy
  requires `installation_id` and `repositories`, does not pin the
  installation, and GitHub's installation repository selection is the scope
  authority. `permissions` remains a narrowing map because GitHub only
  narrows a token below the App grant. The policy denies `org_name` and
  `repository_ids` outright. Standing ambient AppRole, plus the
  claim-before-work write lease under
  `secret/locks/github-write/` (KV-v2 CAS acquire, `delete_version_after`
  deadman).
  The helper requests one repository, but the policy also permits multiple repositories and full-installation
  selectors. Realm policies pin their own repository lists by name, not the
  installation, so a scoped identity can also mint for a same-named repository
  in any installation of the App.
- **publish (`docs-publisher`)** — `github-admin/token/docs-publisher`: one
  repository, `contents: write` + `pull_requests: write`, all three stored in
  the set. The repository list comes from the iac secret store; with none
  configured the set is not declared and the policy grants nothing. Excluded
  from `github-mint`, so no estate AI identity inherits it. Reached only
  through GitHub Actions OIDC (`auth/github-actions`, role `docs-publisher`),
  bound to one audience, one repository and one ref, with a 10m token. There
  is no AppRole and no secret_id for it: the workflow's own job identity is
  the credential, so the runner stores nothing.
- **CI resolver (`ci-resolver`)** — `github-admin/token/ci-resolver-dryvist`:
  `actions`, `checks`, `contents` and `pull_requests` write on the explicit
  repository list from `OPENBAO_GITHUB_CI_RESOLVER_REPOS`; an unset list omits
  the set and leaves the policy empty. Its machine-class AppRole reads only
  its own `apps/ci-resolver` bucket and mints 15m tokens renewable to 60m.
- **admin (`github-admin`)** — `github-admin/token/dryvist-full-automation` and
  `github-admin/token/personal-full-automation`: installation-wide, full App
  ceiling. INERT AppRole — a human response-wraps a single-use secret_id per
  elevation.
- **repo-create (`github-repo-create`)** — `github-admin/token/dryvist-repo-create`:
  `administration: write` only, nothing else — no `contents`, so this token
  can create a repository but never push to one. Standing ambient AppRole,
  like `github-write`, so repo creation needs no per-call human unlock.
  Excluded from `github-mint` for the same reason as the publish tier, and
  more sharply: `administration: write` is the one permission GitHub requires
  to create or delete a repository, so leaking it into every apply-tier actor
  is worse than leaking a per-repo write grant. Dryvist installation only —
  a `personal-repo-create` counterpart is not shipped: GitHub App installation
  tokens cannot call `POST /user/repos` (creating a repository under a user
  account needs a user-to-server OAuth token, not an App installation token),
  so unless the personal account becomes an organization, a personal set would
  mint a token with no reachable endpoint.

  Sequence to create a repository and then push to it: mint
  `github-admin/token/dryvist-repo-create`, `POST /orgs/dryvist/repos`, select the
  repository in the everyday App installation, then `github/token` (raw, `github-write`)
  mints the token that actually pushes. The repo-create token is never reused
  to push — its stored permission map has no `contents` grant to do so.
- **untrusted (`open-llm`)** — the raw `github-agents/token` endpoint accepts
  any `org_name` and `repositories` value, with `org_name` optional and
  `repositories` and `permissions` required. It denies `installation_id` and
  `repository_ids`, and accepts only the exact `contents: write` plus
  `pull_requests: write` map or the exact `contents: read` map. The App's grant
  remains the permission ceiling. The policy reaches no other GitHub mount and
  reads only `secret/apps/open-llm`,
  `secrets-external/zai-coding`, and the role IDs for its two sandbox roles.
  Machine-class AppRole bound to one /32; 15m token, renewable to 60m.
- **hermes (`hermes-public`, `hermes-private`)** — four sets on
  `github-hermes`. `hermes-review-*`: `pull_requests`/`issues` write,
  `contents`/`checks`/`metadata` read, over the organization's public (or
  private) repositories read at converge time. `hermes-author-*`: `contents`/
  `pull_requests` write, `metadata` read, over an explicit allowlist from the
  env document (`OPENBAO_GITHUB_HERMES_AUTHOR_{PUBLIC,PRIVATE}_REPOS`); the
  converge fails when an entry is not of that visibility, and an unset list
  declares no set. `hermes-public` mints only the two public sets,
  `hermes-private` only the two private sets; both are machine-class AppRoles
  with a 15m token. The converge asserts each map verbatim. `hermes-private`
  also reads `secret/apps/hermes-webhook` (written by the AWS Terrakube
  workspace) and mints `aws/sts/hermes-webhook-consumer` when that role's ARN
  is configured.
- **work (`github-work-read`, `github-work-write`, `github-work-admin`)** —
  `github-work/token/work-read`, `github-work/token/work-write` and
  `github-work/token/work-admin`, each pinned to the work installation and
  granted by its own policy and AppRole. `work-write` holds
  `contents: write`, `pull_requests: write` and `issues: write`, with
  `actions`, `checks` and `metadata` read; it has no `workflows` or
  `repository_creation` permission.
  `work-admin` has that exact map plus `workflows: write` and
  `repository_creation: write` (forking into the work organisation), with no
  `administration` or `secrets`; it is operator-gated with a response-wrapped,
  single-use secret_id with a 15m TTL and a one-hour token maximum. No work
  policy grants another set or the raw `github-work/token` endpoint. The read
  and write AppRoles have a 1h token cap.
- **Enterprise read (`github-enterprise-read`)** — the raw
  `github-enterprise-read/token` endpoint, pinned to the one configured
  installation ID. Its App has no permission sets; the App grant supplies the
  read-only ceiling. The AppRole is inert, workstation-class and human-gated,
  with a single-use secret_id and a 1h token.
- **Enterprise admin (`github-enterprise-admin`)** — the raw
  `github-enterprise/token` endpoint, pinned to the one configured installation
  ID. Its App has no permission sets; the App grant supplies the token ceiling.
  The AppRole is inert, workstation-class and human-gated, with a single-use
  secret_id and a 1h token. While an installation ID is unset, its mount and
  policy are not declared; both AppRoles stay declared. An installation ID must
  be a number; any other value renders an empty policy, and the converge fails.
  Clearing an ID later stops declaring the mount and policy but doesn't delete
  them from the store. The break-glass `ai-admin` policy also reaches both
  mounts.

Enterprise App IDs and private keys come from `OPENBAO_GITHUB_ENTERPRISE_APP_ID`,
`OPENBAO_GITHUB_ENTERPRISE_PRIVATE_KEY`, `OPENBAO_GITHUB_ENTERPRISE_READ_APP_ID`,
and `OPENBAO_GITHUB_ENTERPRISE_READ_PRIVATE_KEY`. Their installation IDs come
from the env document keys `OPENBAO_GITHUB_ENTERPRISE_INSTALLATION_ID` and
`OPENBAO_GITHUB_ENTERPRISE_READ_INSTALLATION_ID`.

Estate identities (`ai-apply-*`, `ai-orchestrator`) attach the `github-mint`
capability policy, which grants the read-tier sets only. Raw token endpoints
are limited to `github-write`, `github-write-scoped`, `open-llm`, the two
parameter-pinned Enterprise tier policies, and break-glass `ai-admin`. Nothing
but the converge edits permission sets or
engine configuration. AWS remains separately mounted and authorized:
`terraform-apply` can mint `aws/sts/tf-proxmox`, but has no GitHub-engine grant.

First configuration requires `OPENBAO_GITHUB_APP_ID`,
`OPENBAO_GITHUB_APP_PRIVATE_KEY`, and the two account installation IDs. After
the sealed write succeeds, remove the temporary controller copy of the private
key. "Configured" means a non-zero `app_id` is stored — a virgin mount answers
the config read with `app_id: 0`, which must trigger first configuration, not
the drift refusal (issue #1079). A live acceptance run must issue and revoke
one token from each permission set — and prove an off-allowlist `github/token`
request is denied — before the engine is considered deployed.
