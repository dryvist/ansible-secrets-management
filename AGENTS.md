# AI Agents Configuration

Ansible collection `dryvist.secrets_management`. README.md describes the roles, the layout,
and the checks.

## Working rules

- Role defaults hold the version pins. The `openbao_version` pin in
  `roles/openbao/defaults/main/00-install-and-node.yml` is tracked by `renovate.json`. Change
  a pin in one place only.
- Run `pre-commit run --all-files` before pushing. Fix a failing hook. Do not skip it.
- Commits are signed. Use one fix or feature per commit, with a conventional-commit subject.
- The openbao molecule scenario converges only the `openbao` role. CI runs it.
