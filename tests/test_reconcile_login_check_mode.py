"""The per-call reconcile credential chain runs under --check so the preview reads hold a real token."""

from pathlib import Path

import yaml


TASKS = Path(__file__).resolve().parents[1] / "roles" / "openbao" / "tasks" / "init" / "02-initialize-cluster.yml"


def test_reconcile_credential_chain_runs_in_check_mode():
    chain = [t for t in yaml.safe_load(TASKS.read_text()) if str(t.get("register", "")).startswith("openbao_reconcile_")]
    assert len(chain) == 5
    assert [t["name"] for t in chain if t.get("check_mode") is not False] == []
