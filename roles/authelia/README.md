# authelia

Authelia SSO portal / Traefik forwardAuth provider — a criticality-1 core
service (auth plane, beside ingress/DNS). One passkey login at the portal
opens every Traefik route whose tofu ingress row carries `sso = true`; the
`remember_me` session means roughly one login per week per browser.

## How it fits

- **Gate**: the `traefik` role renders an `authelia` forwardAuth middleware
  and attaches it to every ingress route with `sso: true` (the flag is set in
  tofu-proxmox `ingress.tf` and published through the inventory). Machine/API
  endpoints and apps with native client auth opt out there.
- **Login**: passkey-first (`webauthn.enable_passkey_login`) — Touch ID on the
  registering Mac, synced to other devices via the platform keychain. The
  bootstrap password exists only to create the account and register the first
  passkey.
- **State**: local SQLite on the persistent `/var/lib/authelia` mount
  (passkey registrations survive rebuilds). Sessions are in-memory: a service
  restart just re-prompts the browser.
- **Mail**: identity-verification mails go to the internal SMTP relay
  (Mailpit) — open its UI to click verification links.

## Secrets — generated at the source, no shared store

Per the workspace generate-at-source rule, NONE of Authelia's secrets live in
Doppler, SOPS, or OpenBao — they have no second consumer:

- **JWT / session / storage-encryption secrets**: generated-if-absent on the
  guest's persistent secrets directory and fed to the process via
  `AUTHELIA_*_FILE` env vars in the systemd unit. Never rendered into config.
  The storage encryption key is immutable once the database exists — the
  create-if-absent write can never clobber it.
- **Bootstrap password**: generated on first converge (same pattern as the
  traefik dashboard credentials), persisted root-only at
  `/etc/authelia/.bootstrap_password` for one-time retrieval. Read it once,
  optionally keep it in your personal password manager (Bitwarden), and it
  effectively retires after passkey registration. AI agents never need it —
  machine endpoints are excluded from the SSO gate and keep their own tokens.

## Installation

Nothing manual — the role installs everything: the checksum-pinned release
tarball is downloaded and verified on the controller (LXCs are firewalled
outbound-internal-only), and the extracted binary is copied to
`/opt/authelia` under systemd. Provisioning of the guest itself (VMID, static
IP, firewall, ingress row) is owned by tofu-proxmox.

## Usage

```bash
# Converge the portal + the gate (loader needs localhost in --limit)
doppler run -- ansible-playbook -i inventory/hosts.yml playbooks/site.yml \
  --tags authelia,traefik --limit authelia_group,traefik_group,localhost
```

Then complete [First-time setup](#first-time-setup). Gating is controlled
per-route by the tofu-owned `sso` flag, not in this repo.

## Password rotation

`users.yml` is seeded once (create-if-absent — the salted hash would differ
every render). To rotate: delete `/etc/authelia/users.yml` and
`/etc/authelia/.bootstrap_password` on the guest and re-converge; a fresh
password is generated and persisted.

## First-time setup

1. Converge (`--tags authelia` + `traefik`, with `localhost` in `--limit`).
2. Retrieve the bootstrap password from the root-only file on the guest.
3. Browse to the portal, log in, register a WebAuthn credential (Touch ID).
4. Subsequent logins: passkey only, "Remember me" checked.
