# Break-glass access

Split out of [Secret hierarchy and RBAC](secrets-and-rbac.md) to stay under
this repo's per-file token budget — a documentation split, no behavior
change.

## How a human gets break-glass now

`admin` used to be standing: `role_id` plus a non-expiring, unlimited-use
`secret_id` in a personal keychain. It is now inert and bounded like every other
break-glass tier (1h token, 2h ceiling, 15m single-use `secret_id`), which only
works because there is a way to mint the next one without holding a standing
credential. That way is the `human-unlock` policy, attached to the operator's
own `userpass` user rather than to an AppRole — a person is not a workload, so
there is no secret-zero pair to store anywhere.

1. The operator logs in: `bao login -method=userpass username=<user>`, plus a
   TOTP passcode (enforced on the whole userpass mount).
2. They wrap a single-use `secret_id` for the tier they need:
   `bao write -wrap-ttl=90s -f auth/approle/role/admin/secret-id`.
3. They hand the wrapping token to the session, which unwraps it and logs in as
   `admin` — one login, then the token lives its 15m window (renewable to 30m).
4. Nothing persists. The `secret_id` was single-use and is spent; the token
   expires on its own.

`human-unlock` is the exact complement of `approle-issuer`: the issuer mints the
automatable roles (`manage_secret_id` unset), human-unlock mints the human-gated
tiers (`manage_secret_id: false`). Both derive their lists from that one marker,
so every role is mintable by exactly one of them and a new tier cannot be
forgotten by either. Neither can mint the other's set, and neither can write a
policy.

**Enrolment is a one-time human step and is deliberately not automated.** The
role declares the TOTP method (`identity/mfa/method/totp`) and the enforcement
(`identity/mfa/login-enforcement/<name>`, scoped to the userpass mount
accessor), but a converge that could enrol the second factor would be holding
it, which would make it not a second factor. Enrol once, as a human:

```bash
bao write identity/mfa/method/totp/admin-generate \
  method_id=<id> entity_id=<the operator's entity id>
```

**Order matters.** Enrol, then verify a full userpass+TOTP login, and only then
destroy the standing `admin` secret_id — the enforcement is live as soon as the
converge applies it, so an unenrolled user cannot log in.

The role never sets or reads the password. It updates only the `token_*` fields
on an existing user (OpenBao writes the password only when that parameter is
explicitly present), and if the user does not exist the converge fails with an
instruction rather than creating a passwordless administrator.

The policy/AppRole set is driven by `openbao_policies` / `openbao_approles` in
`defaults/main.yml` — add a row to grow the RBAC surface (a new policy template
goes beside the others in `templates/`). Adding a row **after** the cluster is
already initialized needs a privileged token supplied via `BAO_TOKEN` (see
[Idempotency](operations.md#idempotency)) — only the newly-added identities get created and
get fresh credentials; existing ones are untouched.
