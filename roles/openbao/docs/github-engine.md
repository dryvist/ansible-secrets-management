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
| `github-admin` | admin | admin, repo-create, docs-publisher, runner, exporter |
| `github-agents` | agents | none: `open-llm` mints from the raw `github-agents/token`, pinned to the App's installation |
| `github-hermes` | hermes | `hermes-{review,author}-{public,private}`, split by repository visibility |

A key is required only for first configuration or an explicit rotation; routine
converges never rewrite it. Installation IDs come from the env document
(`secret/platform/ansible/env`).

Token access is tiered; the tier IS the privilege boundary:

- **read (`github-read`)** — `github/token/read-dryvist-all` and
  `github/token/read-personal-all`: all repos, read-only permission map stored
  in the set itself (the set path ignores request bodies, so a holder cannot
  widen it). Standing ambient AppRole. The `semaphore` AppRole also names
  `github/token/read-dryvist-all` — exact path, no wildcard — so the
  unattended Ansible execution plane can check out the repositories it runs,
  including one with a private submodule, without holding a stored token. Read
  only: a checkout can never write a repository.
- **write (`github-write`)** — the raw `github/token` endpoint, limited to
  the configured App installations. The policy requires
  `installation_id` + `repositories`, pins the installation IDs, accepts any
  repository selector and
  `permissions` map (GitHub only narrows a token below the App grant), and
  denies `org_name` and `repository_ids` outright. Standing ambient
  AppRole, plus the claim-before-work write lease under
  `secret/locks/github-write/` (KV-v2 CAS acquire, `delete_version_after`
  deadman).
  GitHub's installation repository selection is the scope authority. The
  helper requests one repository, but the policy also permits multiple
  repositories and full-installation selectors. Realm policies restrict their
  own identities only; repositories shared with the general App installation
  remain available to the general write identity.
- **publish (`docs-publisher`)** — `github-admin/token/docs-publisher`: one
  repository, `contents: write` + `pull_requests: write`, all three stored in
  the set. The repository list comes from the iac secret store; with none
  configured the set is not declared and the policy grants nothing. Excluded
  from `github-mint`, so no estate AI identity inherits it. Reached only
  through GitHub Actions OIDC (`auth/github-actions`, role `docs-publisher`),
  bound to one audience, one repository and one ref, with a 10m token. There
  is no AppRole and no secret_id for it: the workflow's own job identity is
  the credential, so the runner stores nothing.
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
- **untrusted (`open-llm`)** — the raw `github-agents/token` endpoint with
  `installation_id` pinned to the agents App's one installation and
  `repositories` required; `org_name` and `repository_ids` are denied. The
  installation's repository list is the scope and the App's grant the
  ceiling, so a request naming any other repository fails at GitHub. The
  policy reaches no other GitHub mount and reads only `secret/apps/open-llm`.
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
