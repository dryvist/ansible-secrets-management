# Installation and usage

## Installation and inputs

The role lives in `roles/openbao/` in this collection. Reference it from a play
that targets `openbao_group`; no Galaxy install is needed:

```yaml
- hosts: openbao_group
  become: true
  roles:
    - role: openbao
```

The environment for a full converge provides `OPENBAO_STATIC_SEAL_KEY`. A run
that adds policies or AppRoles to an initialized cluster also provides the
privileged `OPENBAO_PROVISIONING_TOKEN` and declares the resources in
`openbao_policies` or `openbao_approles`.

## Run

Run the full role with the `openbao` tag:

```sh
ansible-playbook playbooks/site.yml --tags openbao
```

`openbao` and `openbao_bootstrap` include the install and configuration phases.
`openbao_install` installs or upgrades the package. `openbao_config` configures
and starts the server. `openbao_rbac` and `openbao_approle_config` run against
the existing installation and service.

Run with `--check --diff` to preview supported changes.

## Selective runs

`openbao_select` maps object kinds to lists of exact names or shell globs
(`*`, `?`, and bracket ranges). Its default `{}` keeps full-set behavior. The
kinds are `policies`, `approles`, `ssh_roles`, `github_permission_sets`,
`rotation_exempt`, and `reconcile_policy`. Every selector must match a
declared, manageable object. The role prints the selected names before it
writes. `openbao_select_max` caps the combined selection at 25 by default; set
a larger positive integer for a larger reviewed batch.

```sh
ansible-playbook playbooks/site.yml --tags openbao_rbac,openbao_approle_config --diff \
  -e '{"openbao_select":{"policies":["read-apps"],"approles":["example-app"]}}'
```

With a nonempty selection:

- Omitted kinds are skipped, and so are retired-object deletes and credential
  issuance.
- Only selected policy templates render. Collision, undeclared-role and CIDR
  checks still use the full declared set.
- AppRole selection changes only configuration, policy attachments and bounds.
- In check mode, a `reconcile_policy` selection shows its diff, and a
  `github_permission_sets` selection lists only selected sets that are missing
  or differ from live.
- Reconcile mode requires a manageable declaration and a live capability grant
  for every selected write endpoint. A protected or ungranted selection fails
  with its name.

KV seeding, engine and auth setup, credential issuance, and SSH engine and CA
setup run only in full-set mode.

A full-set RBAC run replaces the text of every existing policy whose rendered
text differs from live. Before it writes, changed text stops the run and
prints a selection command that names those policies. Selecting them
acknowledges the change. Creating a missing policy needs no acknowledgement.

## Restarts

When a configuration or unit change notifies a restart, only the voters that
changed restart. They restart one at a time, with the active voter last. Each
voter must report initialized, unsealed and joined before the next one
restarts. If a voter does not return within the retry window, the play fails
and no other voter restarts.

## First and later runs

On the first run, the bootstrap host initializes the cluster, and the peers
join and auto-unseal. The role writes recovery material and credentials for
new AppRoles to mode `0600` files on the controller.

On later runs, the package step skips an already installed version, and
bootstrap checks leave present, unchanged objects alone. With
`OPENBAO_PROVISIONING_TOKEN` and updated declarations, the role writes missing
or changed policies and creates only new AppRoles. It emits AppRole credentials
only for new AppRoles; it does not re-emit credentials for existing AppRoles.
