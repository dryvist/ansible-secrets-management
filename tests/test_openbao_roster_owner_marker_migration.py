"""Roster ownership markers migrate only to the same caller identity."""

import json
from pathlib import Path

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main/05k-roster-agents.yml"
OWNER_TASKS = ROOT / "roles/openbao/tasks/seed_roster_agent_leaf_owner.yml"


def _render(expression, variables):
    templar = Templar(loader=DataLoader())
    templar.available_variables = variables
    return templar.template(trust_as_template("{{ " + expression + " }}"))


def _owner_state(expected_owner, stored_owner):
    metadata = {"custom_metadata": {}}
    if stored_owner is not None:
        metadata["custom_metadata"]["managed-by"] = stored_owner
    defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
    variables = {
        "openbao_seed_leaf_metadata": {
            "rc": 0,
            "stdout": json.dumps({"data": metadata}),
        },
        "openbao_seed_owner_metadata": {"managed-by": expected_owner},
    }
    variables.update(
        {
            name: trust_as_template(defaults[name])
            for name in (
                "openbao_seed_leaf_exists",
                "openbao_seed_leaf_stored_metadata",
                "openbao_seed_leaf_owner_migrate",
                "openbao_seed_leaf_owner_conflict",
            )
        }
    )
    return {
        name: _render(f"{name} | bool", variables)
        for name in (
            "openbao_seed_leaf_owner_migrate",
            "openbao_seed_leaf_owner_conflict",
        )
    }


def test_owner_marker_migrates_only_for_the_same_agent_caller():
    assert _owner_state("agent-caller:X", "roster-agent:X") == {
        "openbao_seed_leaf_owner_migrate": True,
        "openbao_seed_leaf_owner_conflict": False,
    }

    for stored_owner in ("roster-agent:Y", None, "some-other:X"):
        assert _owner_state("agent-caller:X", stored_owner) == {
            "openbao_seed_leaf_owner_migrate": False,
            "openbao_seed_leaf_owner_conflict": True,
        }

    assert _owner_state("roster-agent:X", "roster-agent:X") == {
        "openbao_seed_leaf_owner_migrate": False,
        "openbao_seed_leaf_owner_conflict": False,
    }


def test_owner_marker_patch_runs_for_migration():
    tasks = yaml.safe_load(OWNER_TASKS.read_text(encoding="utf-8"))
    task = next(
        task
        for task in tasks
        if task["name"] == "Mark the absent roster key leaf with its owner"
    )
    condition = task["when"]
    assert "openbao_seed_leaf_owner_migrate" in condition
    assert _render(
        condition,
        {
            "openbao_seed_leaf_exists": True,
            "openbao_seed_leaf_owner_migrate": True,
        },
    ) is True
    assert _render(
        condition,
        {
            "openbao_seed_leaf_exists": True,
            "openbao_seed_leaf_owner_migrate": False,
        },
    ) is False
