# Installation and usage

## Installation

The role lives in this repository under `roles/openbao/`. Reference it from a
play targeting `openbao_group` — no Galaxy install needed:

```yaml
- hosts: openbao_group
  become: true
  roles:
    - role: openbao
```

Host membership in `openbao_group` is driven by the Terraform-exported
inventory: an LXC tagged `openbao` is placed in `openbao_group` by
`inventory/load_tofu.yml`. The node's VLAN IP arrives as the `container_ip`
hostvar (also used to build the Raft peer list).

## Usage

Run through the credentialed wrapper so `OPENBAO_STATIC_SEAL_KEY` is present:

```sh
doppler run -- ansible-playbook playbooks/site.yml --tags openbao
```

On the **first** run the bootstrap node initializes the cluster and writes the
break-glass files to the controller (see below); the peers join + auto-unseal.
Every subsequent run is a no-op: install is skipped (version present) and the
bootstrap steps short-circuit on their existence checks.

