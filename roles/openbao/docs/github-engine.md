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
| `github-admin` | admin | admin, repo-create, docs-publisher, ci-resolver, runner, exporter, dify-pr-automation-read, dify-pr-automation-write |
| `github-agents` | agents | public-read/write and five least-privilege fleet-agent sets, scoped to public dryvist repositories |
| `github-hermes` | hermes | `hermes-review-{public,private}`, `hermes-read-public`, `hermes-author-public`, split by repository visibility |
| `github-work` | work | a derived `read` set and the raw token endpoint for write; the App's grant is the only write ceiling |
| `github-personal` | user-owned App | `personal-write` and a raw token path, pinned to its configured installation |
| `github-openhands` | OpenHands | `openhands-pilot` (contents and pull requests write; checks and metadata read) |
| `github-pepper` | Pepper | `pepper-vault-read` (configured repository list; contents and metadata read) |
| `github-enterprise-read` | read-only Enterprise App | none: raw token endpoint, pinned to its installation |
| `github-enterprise` | admin Enterprise App | none: raw token endpoint, pinned to its installation |
| `github-runner` | runner App | none: raw token endpoint accepts only `org_name` |

The tier convention, followed by `github-work` and by any mount that moves to
it: read and write tiers list no permissions of their own. Read is a set derived
from the one standard read list (`derive_read` on the mount), and write is the
raw endpoint with the App's own grant. Single-purpose sets (repo-create,
docs-publisher, ci-resolver, runner, exporter and the like) keep their explicit
maps.

The Enterprise owner token is stored separately in the `github-enterprise-owner`
KV v2 mount. The human-unlock login can create or replace it; only the admin
tiers can read its data and metadata.

A key is required only for first configuration or an explicit rotation; routine
converges never rewrite it. Installation IDs come from the env document
(`secret/platform/ansible/env`).

Token access is tiered; the tier IS the privilege boundary:

- **read (`github-read`)** — the raw `github/token` endpoint, requiring an
  organization name and the fixed read permission map; installation IDs are
  denied. The App's installation determines which organizations are available.
  The `semaphore` AppRole also uses the raw endpoint with its own fixed read
  map so it can check out repositories and let the Cribl pack mirror look up
  releases without holding a stored token.
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
- **Personal write (`personal-write`)** — `github-personal/token/personal-write`:
  fixed to its installation with `contents`, `pull_requests`, and `workflows`
  write plus `checks`, `statuses`, and `metadata` read. The set has no
  repository list, so GitHub's installation selection is its repository
  boundary. The `github-write` policy also grants `github-personal/token` with
  `installation_id` pinned to the configured personal installation.
  `github-mint` remains limited to read-tier sets, and `ai-orchestrator`
  excludes write-tier sets.
- **publish (`docs-publisher`)** — `github-admin/token/docs-publisher`: one
  repository, `contents: write` + `pull_requests: write`, all three stored in
  the set. The repository list comes from the iac secret store; with none
  configured the set is not declared and the policy grants nothing. Excluded
  from `github-mint`, so no estate AI identity inherits it. Reached only
  through GitHub Actions OIDC (`auth/github-actions`, role `docs-publisher`),
  bound to one audience, one repository and one ref, with a 10m token. There
  is no AppRole and no secret_id for it: the workflow's own job identity is
  the credential, so the runner stores nothing.
- **PR reconcile (`pr-reconcile-sweep`)** — the raw `github/token` endpoint,
  requiring `org_name` from `openbao_pr_reconcile_owners` and the exact
  `contents`, `issues`, `pull_requests` and `statuses` write map;
  `installation_id` and `repository_ids` are denied. Set
  `OPENBAO_GITHUB_PR_RECONCILE_REPOSITORY` to the OIDC repository, for example
  `example-org/example-repo`, and `OPENBAO_GITHUB_PR_RECONCILE_OWNERS`
  to a comma-separated list of permitted owners. Both are required to declare
  the role and policy; while either is unset, the converge removes a live role
  and policy of that name. The OIDC role binds the configured repository and its
  `workflow_ref` (for example `example-org/example-repo/.github/workflows/pr-reconcile-sweep.yml@refs/heads/main`),
  plus the main ref, schedule/dispatch events, and self-hosted runners. The
  OpenBao batch token lasts 5m (10m max); GitHub's installation token keeps its
  one-hour lifetime.
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
  so unless the personal account becomes an organization, a personal
  repo-create set would mint a token with no reachable endpoint.

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
  `secrets-external/ai/saas/zai`, and the role IDs for its sandbox roles.
  Machine-class AppRole bound to one /32; 15m token, renewable to 60m.
- **fleet agent roles (`agent-code-simplifier`, `agent-ci-fixer`,
  `agent-vikunja-clerk`, `agent-vikunja-triage`, and `agent-docs-updater`)** —
  each role mints only its same-named set on `github-agents`, scoped to public
  dryvist repositories.
  The code simplifier gets `pull_requests: write` and `contents: read`; the CI
  fixer gets `contents` and `pull_requests` write with `checks` and `actions`
  read. The Vikunja clerk, Vikunja triage, and docs updater each get only
  `contents`, `pull_requests`, `issues`, and `checks` read. These roles have no
  KV grants, use the `service-runtime` identity class, and are created only when
  `OPENBAO_DIFY_AGENT_CIDR` is set. Their SecretIDs last 720h and are bound to
  the configured CIDR; OpenBao tokens are capped at 15m.
- **Dify PR automation (`agent-pr-keeper`, `agent-github-clerk`, and
  `agent-merge-steward`)** — the first two roles mint only
  `dify-pr-automation-read`; the merge steward mints only
  `dify-pr-automation-write`. Both sets use the JacobPEvans-ai installation
  and the repository names in `openbao_dify_pr_automation_repositories`.
  The read set grants `contents`, `pull_requests`, `checks`, `statuses`, and
  `metadata` read. The write set grants `contents` and `pull_requests` write
  while keeping the other permissions read-only. Each role receives one-use
  SecretIDs with the same 720h lifetime as the existing Dify agents; tokens
  are capped at 15m.
- **hermes (`hermes-public`, `hermes-private`)** — four sets on
  `github-hermes`. `hermes-review-*`: `pull_requests`/`issues` write,
  `contents`/`checks`/`metadata` read, over the organization's public (or
  private) repositories read at converge time. `hermes-author-public`:
  `contents`/`pull_requests` write, `metadata` read, over an explicit
  allowlist from the env document (`OPENBAO_GITHUB_HERMES_AUTHOR_PUBLIC_REPOS`);
  the converge fails when an entry is outside the public review set, and an
  unset list declares no set. `hermes-public` mints `hermes-review-public` and
  `hermes-author-public`; `hermes-private` mints `hermes-review-private` and
  `hermes-read-public`, and authors nothing. Both are machine-class AppRoles
  with a 15m token. The converge asserts each map verbatim. `hermes-private`
  reads the HMAC secret from `secrets-external/apps/hermes-webhook` and mints
  `aws/sts/hermes-webhook-consumer` when that role's ARN is configured. The
  `tofu-github` Terrakube workspace reads the HMAC secret from that path and
  the Function URL from `config/apps/hermes-webhook`.
- **work (`github-work-read`, `github-work-write`)** — one App, no declared
  sets. `github-work-read` mints only `github-work/token/read`, a set the
  converge derives on each run: the standard read list
  (`openbao_github_read_permissions`) cut to the permissions the installation
  actually grants, all at read. A set path ignores request bodies, so every read
  mint is read. `github-work-write` mints the raw `github-work/token` endpoint;
  it must name `org_name` and `repositories` and may not send `permissions` or
  `installation_id`, so a write token carries exactly the App's grant for the
  named repositories. Both AppRoles have a 1h token cap.
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

## Runner registration by organization

`github-runner/token` requires `org_name` and accepts no other request
parameters. Its App has only the organization-level `Self-hosted runners:
write` permission and no OpenBao permission sets. The mount and policy are
always declared; `OPENBAO_GITHUB_RUNNER_APP_ID` and
`OPENBAO_GITHUB_RUNNER_APP_PRIVATE_KEY` are one-time environment that configure
it. The App's GitHub installations determine the organizations available to
the request. The existing fixed base registration set remains on
`github-admin`.

Set `OPENBAO_GITHUB_RUNNER_REGISTER_OWNERS` in the platform env document to a
comma-separated list of additional owners, for example
`example-org,example-other`. Each listed owner must match a `name` in
`openbao_github_org_secrets_installations` and have a configured installation
ID; configured owners produce a `runner-register-<owner>` set with the fixed
runner permission map. Owners without a mapped installation ID are skipped and
warned individually. An unset or empty list adds no sets and emits one warning
that names the configuration key. The runner policy grants its runner-tier set
paths only.

Estate identities (`ai-apply-*`, `ai-orchestrator`) attach the `github-mint`
capability policy, which grants the read-tier sets only. Raw token endpoints
are limited to `github-write`, `github-write-scoped`, `open-llm`, the two
parameter-pinned Enterprise tier policies, break-glass `ai-admin`, and
`github-mount-config` on the declared per-App mounts. That last policy is
attached only to the human-gated `openbao-policy-sync` AppRole. It permits
metadata-read token requests with `org_name` or `installation_id` pinned to the
declared repository-enumeration inputs, exact declared permission-set writes,
and revocation only for leases under those mounts' token paths. It can list
permission sets and delete undeclared sets; deletion removes a set's minting
power. It does not permit repository selectors. The reconcile policy pins this
policy's body and the role's complete `token_policies` list; an existing
policy-sync token cannot use the new mount grants until the role is updated and
a fresh human-gated token is issued. The mount include remains capability-gated,
so unattended reconcile does not configure per-App mounts. AWS remains
separately mounted and authorized:
`terraform-apply` can mint `aws/sts/tf-proxmox`, but has no GitHub-engine grant.

First configuration requires `OPENBAO_GITHUB_APP_ID`,
`OPENBAO_GITHUB_APP_PRIVATE_KEY`, and the two account installation IDs. After
the sealed write succeeds, remove the temporary controller copy of the private
key. "Configured" means a non-zero `app_id` is stored — a virgin mount answers
the config read with `app_id: 0`, which must trigger first configuration, not
the drift refusal (issue #1079). A live acceptance run must issue and revoke
one token from each permission set — and prove an off-allowlist `github/token`
request is denied — before the engine is considered deployed.

## Key rotation

`openbao_github_app_key_rotate_mounts` is a list of mount names, empty by
default. A configured mount named in it has its App credentials rewritten from
the supplied App ID and private key on that run; it accepts `github-admin` and
any per-App mount. A mount not named in it is written only on first
configuration, so a supplied key alone does not replace a stored one.

Two asserts run before the write for a listed, configured mount:

- the supplied App ID must equal the stored one, so a rotation replaces the key
  and never the App;
- the supplied private key must be non-empty, and the run fails naming the
  mount and the variable otherwise.

First configuration and rotation share one write
(`tasks/init/github_app_config_write.yml`). Empty the list after the rotation
run; while a mount stays listed, each run with its key supplied writes it again.

The `github-personal` mount uses
`OPENBAO_GITHUB_PERSONAL_APP_ID` and
`OPENBAO_GITHUB_PERSONAL_APP_PRIVATE_KEY` from the one-time environment. Its
installation ID comes from `OPENBAO_GITHUB_PERSONAL_INSTALLATION_ID` in the
env document, and the installation owner must be present in
`OPENBAO_GITHUB_APP_INSTALL_ALLOWLIST`. The mount and `personal-write` set are
omitted while that installation ID is empty.

The `github-pepper` mount gives the local Pepper agent a short-lived token
for its configured repository list. Its `pepper-vault-read` set grants only
`contents: read` and `metadata: read`; the policy does not grant the raw token
endpoint. The mount and set are omitted unless the installation ID, App ID,
private key, and a non-empty list of valid repository names are present:

- `OPENBAO_GITHUB_PEPPER_APP_ID`
- `OPENBAO_GITHUB_PEPPER_APP_PRIVATE_KEY`
- `OPENBAO_GITHUB_PEPPER_INSTALLATION_ID`
- `OPENBAO_GITHUB_PEPPER_REPOSITORIES` (comma-separated repository names)
- `OPENBAO_GITHUB_PEPPER_REPOSITORY`

The App ID, private key, and repository list are environment inputs. Empty
list entries are dropped and duplicate names are removed while preserving
order. When the list is empty, `OPENBAO_GITHUB_PEPPER_REPOSITORY` supplies the
single repository for compatibility. Every name must match
`^[A-Za-z0-9_.-]+$`. The installation ID comes from the environment document.

The `github-openhands` mount gives OpenHands an installation-scoped
`openhands-pilot` set with `contents: write`, `pull_requests: write`,
`metadata: read`, and `checks: read`. Its `openhands` policy can mint only that
set on this mount and retains its existing OpenHands KV reads. The App ID and
private key come from `OPENBAO_GITHUB_OPENHANDS_APP_ID` and
`OPENBAO_GITHUB_OPENHANDS_APP_PRIVATE_KEY`; the installation ID comes from
`OPENBAO_GITHUB_OPENHANDS_DRYVIST_INSTALLATION_ID` in the env document. The
mount and set are omitted unless all three inputs are present. The `openhands`
AppRole token TTL and maximum TTL are both 1h.
