#!/usr/bin/env bash
# Ansible runner for this collection's controller-side playbooks (rotate,
# seed). They run on localhost with connection: local, so there is no
# inventory to load and no SSH identity to mint.
#   scripts/run-ansible.sh playbooks/openbao-rotate-approles.yml [args...]
# Reads SECRET_STORE_ADDR (preferred over BAO_ADDR) from the environment.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <playbook> [ansible-playbook args...]" >&2
  exit 1
fi

PLAYBOOK="$1"
shift

# Refuse to run from a checkout that differs from its remote branch or has
# uncommitted edits to tracked files: either runs content nobody reviewed and
# still ends with a green recap. Detached HEAD (a pinned CI or release
# checkout) has no branch to compare and is skipped. ALLOW_STALE_CHECKOUT=1
# is the deliberate override for a pinned replay.
REPO_ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git -C "$REPO_ROOT" symbolic-ref -q --short HEAD || true)
if [[ -z ${ALLOW_STALE_CHECKOUT:-} ]]; then
  if [[ -n $BRANCH ]]; then
    git -C "$REPO_ROOT" fetch --quiet origin "$BRANCH"
    LOCAL_SHA=$(git -C "$REPO_ROOT" rev-parse HEAD)
    REMOTE_SHA=$(git -C "$REPO_ROOT" rev-parse "origin/$BRANCH")
    if [[ $LOCAL_SHA != "$REMOTE_SHA" ]]; then
      echo "ERROR: checkout $LOCAL_SHA does not match origin/$BRANCH $REMOTE_SHA; refusing to run." >&2
      exit 1
    fi
  fi
  if [[ -n $(git -C "$REPO_ROOT" status --porcelain --untracked-files=no) ]]; then
    echo "ERROR: working tree has uncommitted changes to tracked files; refusing to run." >&2
    exit 1
  fi
fi

if [[ -n ${SECRET_STORE_ADDR:-} ]]; then
  export BAO_ADDR=$SECRET_STORE_ADDR
fi

LOG_DIR="$REPO_ROOT/.ansible-run-logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date -u +%Y%m%dT%H%M%SZ)-$(basename "$PLAYBOOK" .yml).log"
echo "Logging this run to $LOG_FILE"
set +e
ansible-playbook -i localhost, "$PLAYBOOK" "$@" 2>&1 | tee "$LOG_FILE"
STATUS=${PIPESTATUS[0]}
set -e

# The exit code alone is not a verdict: a run that ends without a recap was
# interrupted, and a recap can report failures behind a rescued block.
if ! grep -q '^PLAY RECAP' "$LOG_FILE"; then
  echo "ERROR: the run ended before Ansible printed a play recap; read the log before concluding it did nothing." >&2
  [[ $STATUS -eq 0 ]] && STATUS=1
elif grep -A50 '^PLAY RECAP' "$LOG_FILE" | grep -qE 'failed=[1-9]|unreachable=[1-9]'; then
  echo "ERROR: the play recap reports failed or unreachable hosts (ansible exited $STATUS)." >&2
  STATUS=1
fi

echo "Run log: $LOG_FILE"
exit "$STATUS"
