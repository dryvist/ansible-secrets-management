# OpenBao identity and credential lifecycle

## AI policy composition

The `ai-*` rows in [Secret hierarchy and RBAC](secrets-and-rbac.md) are actor
roles: they carry no path rules themselves, only attach actor-agnostic base
capability policies — `read-<svc>` / `write-<svc>` (one pair per entry in
`openbao_ai_domains`), plus `github-mint`. The rollups `read-all` /
`read-write-all` are lists of those base policy names (composition at the token
layer, no duplicated path rules). Adding a writable service is one entry in
`openbao_ai_domains`: it renders a new `read-<svc>`/`write-<svc>` pair, joins the
rollups, mints an `ai-apply-<svc>` role, and becomes available to any future
actor (`human-*`, `ci-*`) that attaches the same base names.

## Terrakube workload identity

The role enables JWT auth at `auth/terrakube` using the internal Terrakube API
as both OIDC discovery URL and bound issuer. Each entry in
`openbao_terrakube_workspaces` has a `terrakube-<workspace>` role and policy.
Roles bind audience `openbao.workload.identity` and the exact string subject
`organization:<openbao_terrakube_organization>:workspace:<workspace>`; a token
from one workspace cannot select another workspace's policy. The converge
deletes live roles and policies under `openbao_retired_terrakube_prefix`.
Terrakube stores only the non-secret dynamic credential controls. Provider
credentials remain in their native OpenBao KV or secrets-engine paths and are
returned through a short-lived OpenBao token.

## AppRole credential lifecycle

**Secret-zero model**: each AppRole's `role_id`/`secret_id` is published to
Doppler tier-0 and reaches its consumer as ambient environment under
`doppler run`. Access to Doppler tier-0 is the primary access boundary, but it
is no longer the only one: a `secret_id` also carries a finite lifetime and a
redemption cap, and is bound to the network segment its holder is supposed to
sit on.

`secret_id_ttl: 0` used to be the standing default and was described here as
intentional. It was not defensible: it made every published credential
permanent, so any copy that escaped Doppler — a drop file left on a controller,
a value in a shell history — stayed a working credential until somebody noticed.
Nothing rotated them, so "rotate manually" never happened. The defaults are now
finite (`openbao_approle_secret_id_ttl`, `openbao_approle_secret_id_num_uses`
in `defaults/main/08-admin-and-ttls.yml`), with per-role overrides and a
documented reason required for any remaining `0`.

The workstation per-call path uses `approle-issuer` for `flow-lock`,
`openbao-reconcile`, `azure-iac-admin`, and five workstation-only aliases for
the domain prefetch roles. Each target secret_id is limited to 15 minutes and one use; the shared
`flow-lock approle-token ROLE` command logs in, destroys that secret_id by its
accessor, and prints only the client token. Issuer grants are generated only
for roles explicitly marked `secret_id_issuance: per_call`; stored and
scheduled-rotation identities are not eligible. Domain machine callers retain
their existing rotated credentials. Per-call role IDs and secret IDs are
excluded from stored-credential probes, rotation catalogs, controller files,
and Doppler publication. Human-gated roles and the issuer's own bootstrap
identity remain outside that mint set.

The OpenBao role's routine reconciliation uses the same issuer directly through
`community.hashi_vault`: it reads the declared `openbao-reconcile` role ID,
mints one secret_id, logs in with it, then revokes it by accessor. Its issuer
liveness probe runs for every initialized cluster, including provisioning-token
runs, after RBAC and AppRole declarations have been applied. A first scoped
converge selects `openbao_rbac` and `openbao_approle` so grants precede the
probe.

Source binding uses named CIDR classes (`machine` / `workstation` / `ci`), whose
values arrive by environment and are never committed. A class that a declared
role uses but which was never supplied **fails the converge** rather than
quietly creating the unbound role the binding exists to prevent. A role that
explicitly declares an empty `secret_id_bound_cidrs` also fails the converge.
Omitting that key resolves the configured CIDR class (the default is
`machine`); omission never selects `unbound`.

Identities that authenticate through the node-local loopback listener and then
use the resulting token from the same source are enumerated once in
`openbao_loopback_client_approles`: every enabled `openbao_rotators` entry plus
the snapshot, secret-age-audit and scheduled AppRole secret-id rotation
identities. Both bind lists of each listed identity (`secret_id_bound_cidrs`
and `token_bound_cidrs`) accept the node-local loopback source, so a credential
redeemed over loopback is also usable from loopback.

Two sibling asserts cover the class *assignment* rather than the class values.
Every AppRole the converge loops must resolve to a class, so a role declared
outside `openbao_approles` fails the run by name instead of dying on an
undefined variable inside a `no_log` loop. And every key of
`openbao_approle_cidr_class_overrides` must name a declared role, because an
override that matches nothing is a silent no-op that leaves its role on the
machine default while the file says otherwise. `unbound` stays a decision that
is written down with a reason, never something a role arrives at by omission.

The one exception throughout is `public`: it needs no secret-zero, no
redemption cap and no source binding, since it only unlocks non-exploitable
facts.

Every check above assumes the declared list is the complete truth. It is not,
by construction: reconciliation only ever loops what code declares, so an
identity created by any other path — a rename that left the old name live, a
manual break-glass create nobody backfilled — is invisible to every one of
them and keeps whatever bounds it was created with forever. The converge
closes that by listing what actually exists in the store (`bao list
auth/approle/role`, granted read-only to the reconcile identity) and failing
by name on anything live that is declared nowhere. A genuine, deliberate
exception is named in `openbao_approle_undeclared_exceptions`, next to the
declarations themselves, with a reason — never a silent allowlist elsewhere.
The reverse direction (declared but not yet live) only warns: that is the
ordinary shape of a role about to be created, not a leak.
