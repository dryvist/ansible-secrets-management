# openbao_secrets

A controller-side **pre-play** that logs in to OpenBao with the **ai-readonly**
AppRole and reads the AI KV subtree into a single `bao_ai_secrets` fact. AI roles
then resolve their secrets **bao-first with an env fallback**:

```yaml
some_secret: "{{ bao_ai_secrets.SOME_SECRET | default(lookup('env', 'SOME_SECRET'), true) }}"
```

It runs **once** on the controller (`delegate_to: localhost`, `run_once`), leaving
the merged result as `openbao_secrets_merged` on the controller; the `site.yml`
play then copies it into the shared, un-prefixed `bao_ai_secrets` fact per host (the
publish lives at the playbook layer — like `tofu_data` in `load_tofu.yml` — so the
role's own facts stay role-prefixed). It **skips cleanly** when `VAULT_ADDR` is
unset, so converges keep working on env/SOPS secrets before the KV is seeded (the
`group_vars/all.yml` default `bao_ai_secrets: {}` guarantees the fallback resolves).

## Alignment with `roles/openbao` (RBAC)

The layout is aligned to what `roles/openbao` bootstraps — do not invent paths the
policy can't read:

- **KV mount**: `secret` (KV v2).
- **AppRole**: `ai-readonly` (role_id/secret_id).
- **Policy grant**: the `ai-readonly` policy grants `read` on `secret/data/ai/*`
  (and `secret/data/apps/*`) — a wildcard, so every path under `ai/` is readable.
- **Seeding**: `roles/openbao` seeds **no** values; it creates only the mount +
  policies + AppRoles. So the paths below yield keys only once a writer populates
  them; until then every read is empty and the env fallback wins.

## Inputs (env)

| Env var | Purpose |
| --- | --- |
| `VAULT_ADDR` | OpenBao ingress URL (`https://openbao.<subdomain>`). Unset ⇒ skip. |
| `AI_VAULT_ROLE_ID` | ai-readonly AppRole role_id |
| `AI_VAULT_SECRET_ID` | ai-readonly AppRole secret_id |

## KV paths read (`openbao_secrets_paths`)

| Path (mount-relative) | Expected keys |
| --- | --- |
| `ai/router` | `LLM_ROUTER_MASTER_KEY` (+ `LANGFUSE_*` project keys) |
| `ai/llm-large` | `LLM_LARGE_BEARER_TOKEN` |
| `ai/qdrant` | `QDRANT_API_KEY` |
| `ai/open-webui` | `OPEN_WEBUI_SECRET_KEY`, `OPEN_WEBUI_OPENAI_API_KEY` |
| `ai/hermes` | `HERMES_AGENT_MODEL_API_KEY` |

All readable path keys are merged flat into `bao_ai_secrets`, keyed by the field
name, so a consumer default reads `bao_ai_secrets.<FIELD_NAME>`.

## Wiring

Runs as the first AI-phase play in `playbooks/site.yml` (before any AI/vectordb
role), against the union of AI-consuming groups, so `bao_ai_secrets` exists before
those roles evaluate their secret defaults.

## Dependencies

- `community.hashi_vault` (added to `requirements.yml`) and its Python `hvac`
  dependency in the controller environment (provided by the Nix dev shell —
  `nix-devenv#ansible-apps`; see the PR for the companion change).

## Not yet live-validated

Verify at the first bao-backed converge: the ai-readonly AppRole login against the
Traefik ingress, and that `vault_kv2_get` returns the expected field names once the
`secret/ai/*` paths are seeded.
