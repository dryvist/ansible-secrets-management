#
# Ansible managed
#
# OpenBao policy for the approle-secret-id-rotate AppRole — INERT (no
# standing secret_id; see the AppRole row in
# defaults/main/07e-rotation-approles.yml), same human-gated shape as
# ai-rotate/apps-rotate: an operator wraps a single-use secret_id, this
# identity's own login unwraps it, and the resulting token lives exactly one
# rotation run (playbooks/openbao-rotate-approles.yml).
#
# Narrower than approle-issuer on purpose: approle-issuer may MINT a
# secret-id for every issuable role in the cluster, but holds neither the
# destroy capability nor the env-document write below — minting a fresh
# credential and retiring the old one for the explicit rotation catalogs is
# a separate, smaller power from "can hand out a working credential for
# anything". Scoped by name, not a wildcard, so this identity cannot touch
# any other AppRole in the cluster.
#
# The scheduled identity renders this with scheduled_only (07c): it rotates the
# domain catalog only and never mints a host secret-zero identity, so a dead or
# missing one needs the human-gated identity.
path "auth/approle/role/observability/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/observability/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/observability/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/observability/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/local-cloud/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/local-cloud/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/local-cloud/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/local-cloud/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/monitoring/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/monitoring/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/monitoring/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/monitoring/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/media/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/media/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/media/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/media/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/ntfy/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/ntfy/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/ntfy/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/ntfy/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/apps/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/apps/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/apps/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/apps/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/local-llm/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/local-llm/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/local-llm/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/local-llm/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/clickhouse/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/clickhouse/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/clickhouse/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/clickhouse/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/clickhouse-ingest/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/clickhouse-ingest/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/clickhouse-ingest/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/clickhouse-ingest/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/clickhouse-wall/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/clickhouse-wall/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/clickhouse-wall/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/clickhouse-wall/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/local-llm-workstation/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/local-llm-workstation/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/local-llm-workstation/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/local-llm-workstation/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/cribl-edge-mac-a/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/cribl-edge-mac-a/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/cribl-edge-mac-a/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/cribl-edge-mac-a/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/cribl-edge-mac-b/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/cribl-edge-mac-b/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/cribl-edge-mac-b/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/cribl-edge-mac-b/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/agent-ssh-sign/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/agent-ssh-sign/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/agent-ssh-sign/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/agent-ssh-sign/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/agent-workstation/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/agent-workstation/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/agent-workstation/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/agent-workstation/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/herdr-hail/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/herdr-hail/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/herdr-hail/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/herdr-hail/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/slack-approvals/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/slack-approvals/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/slack-approvals/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/slack-approvals/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/claude-code-router-key/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/claude-code-router-key/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/claude-code-router-key/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/claude-code-router-key/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/bao-elevate-client/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/bao-elevate-client/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/bao-elevate-client/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/bao-elevate-client/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/hermes/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/hermes/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/hermes/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/hermes/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/ai-donna/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/ai-donna/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/ai-donna/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/ai-donna/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/open-llm/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/open-llm/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/open-llm/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/open-llm/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/ci-resolver/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/ci-resolver/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/ci-resolver/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/ci-resolver/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/openhands/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/openhands/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/openhands/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/openhands/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/ansible-converge-writer/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/ansible-converge-writer/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/ansible-converge-writer/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/ansible-converge-writer/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/slack-admin/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/slack-admin/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/slack-admin/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/slack-admin/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/slack-ops/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/slack-ops/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/slack-ops/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/slack-ops/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/terraform/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/terraform/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/terraform/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/terraform/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/approle-audit/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/approle-audit/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/approle-audit/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/approle-audit/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/approle-issuer/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/approle-issuer/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/approle-issuer/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/approle-issuer/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/github-exporter/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/github-exporter/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/github-exporter/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/github-exporter/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/hatchet-eval-status/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/hatchet-eval-status/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/hatchet-eval-status/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/hatchet-eval-status/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "auth/approle/role/iac-platform-deploy/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/iac-platform-deploy/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/iac-platform-deploy/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/iac-platform-deploy/secret-id-accessor/destroy" {
  capabilities = ["update"]
}

# The rotation play probes the two roster key readers by exact role-id read
# to decide whether the published inventory must be loaded before rotating.
path "auth/approle/role/llm-router-agent-keys/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/agentgateway-agent-keys/role-id" {
  capabilities = ["read"]
}

# The one KV document holding these domains' OPENBAO_APPROLE_<NAME>_{ROLE,
# SECRET}_ID pairs written to platform/ansible/env.
# read+update, CAS write only (the rotation playbook always reads the
# current version and writes back with `options.cas` pinned to it) -- no
# `create`, so this identity can never seed the document into existence,
# only rotate an entry that is already there.
path "secret/data/platform/ansible/env" {
  capabilities = ["read", "update"]
}

path "secret/metadata/platform/ansible/env" {
  capabilities = ["read"]
}

# The Doppler service token this identity presents to republish
# openbao_rotate_doppler_sync_domains' pairs into Doppler (see
# 08c-rotator-doppler-sync.yml). Read-only: this identity never writes or
# rotates that token itself.
path "secret/data/rotator/doppler-sync-token" {
  capabilities = ["read"]
}

# approle-secret-id-rotate-scheduled rotates its OWN secret_id last, each
# run, using this same policy's already-authenticated token, through the
# exact same tasks/openbao_rotate_one_domain.yml steps as a domain -- so it
# needs the same four grants, scoped to exactly its own role name, nothing
# wider. Its source-address CIDR binding is the control on a leaked pair,
# not this grant.
path "auth/approle/role/approle-secret-id-rotate-scheduled/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/approle-secret-id-rotate-scheduled/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/approle-secret-id-rotate-scheduled/secret-id/lookup" {
  capabilities = ["update"]
}
path "auth/approle/role/approle-secret-id-rotate-scheduled/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
