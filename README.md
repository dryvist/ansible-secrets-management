# ansible-secrets-management

Ansible collection `dryvist.secrets_management` for OpenBao server install and Raft cluster
bootstrap, AppRole and policy sync, secret rotation, TOTP and admin-group bootstrap, the
Authelia role, and the OpenBao voter-health role.

[![CI Gate][ci-badge]][ci-workflow] [![License: Apache-2.0][license-badge]][license]

## Installation

`requirements.yml` lists the collection dependencies. The `openbao` role consumes the
`llm_router_key_catalog` role from the `dryvist.homelab` collection, pinned by commit.

```sh
ansible-galaxy install -r requirements.yml
```

## Usage

Consume a role by its fully qualified name, for example `dryvist.secrets_management.openbao`.
Each role's README and defaults files list the inputs that the role reads.

## Roles

| Role | Purpose |
| --- | --- |
| `openbao` | Installs and configures an OpenBao Raft cluster member, then provisions the KV mount, secret hierarchy, policies, and AppRoles. |
| `authelia` | Configures the Authelia SSO provider. |
| `openbao_secrets` | Reads each resource-domain KV subtree into a per-domain fact through that domain's AppRole. |
| `openbao_voter_health` | Samples each Raft voter's health endpoints and sends one event per voter per cycle. |

## Layout

The collection root is the repository root: `galaxy.yml`, `roles/`, `playbooks/`,
`molecule/`, and `tests/` sit at the top level.

## Checks

- `pre-commit run --all-files` runs ansible-lint (production profile), yamllint,
  markdownlint, and gitleaks.
- `molecule test -s openbao` runs the openbao scenario in a privileged Debian container.
  CI runs it.
- `pytest` runs the test modules under `tests/`.
- `ansible-playbook -e render_tmp=<dir> tests/template_render/verify/<file>.yml` runs one
  template-render check.

## Releases

release-please (simple type) maintains `CHANGELOG.md`. `VERSION` and the `version` key in
`galaxy.yml` move together; the `x-release-please-version` marker on that line lets
release-please update it.

## Contributing

Open a pull request against `develop`. Run `pre-commit run --all-files` before pushing.

## License

Apache-2.0. See [LICENSE][license].

---

[docs.jacobpevans.com](https://docs.jacobpevans.com)

[ci-badge]: https://github.com/dryvist/ansible-secrets-management/actions/workflows/ci-gate.yml/badge.svg
[ci-workflow]: https://github.com/dryvist/ansible-secrets-management/actions/workflows/ci-gate.yml
[license-badge]: https://img.shields.io/badge/license-Apache--2.0-blue.svg
[license]: LICENSE
