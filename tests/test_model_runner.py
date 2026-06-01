from pathlib import Path

import pytest

from perspective_gap.model_runner import completed_tasks, dynamic_evaluations, parse_tasks


ROOT = Path(__file__).resolve().parents[1]


def test_parse_tasks_accepts_task_subset():
    assert parse_tasks("role_assignment") == ["role_assignment"]
    assert parse_tasks("prompt_writing") == ["prompt_writing"]
    assert parse_tasks("both") == ["role_assignment", "prompt_writing"]


def test_parse_tasks_rejects_unknown_task():
    with pytest.raises(ValueError, match="unknown task"):
        parse_tasks("role_assignment,unknown")


def test_dynamic_evaluations_defaults_to_seed_42_for_scenario_id():
    rows = dynamic_evaluations(
        ROOT / "data" / "scenarios",
        ROOT / "data" / "distractors",
        scenario_ids=["pg_006"],
        shuffle_seeds=[],
    )
    assert [row["evaluation_id"] for row in rows] == ["pg_006__seed_42"]


def test_dynamic_evaluations_seed_only_renders_all_scenarios():
    rows = dynamic_evaluations(
        ROOT / "data" / "scenarios",
        ROOT / "data" / "distractors",
        scenario_ids=[],
        shuffle_seeds=[7],
    )
    assert len(rows) == 110
    assert rows[0]["evaluation_id"] == "pg_000__seed_7"
    assert rows[-1]["evaluation_id"] == "pg_109__seed_7"


def test_completed_tasks_reads_partial_task_rows(tmp_path):
    path = tmp_path / "predictions.jsonl"
    path.write_text(
        '{"evaluation_id":"pg_000__seed_1","role_assignment_response":"{}"}\n'
        '{"evaluation_id":"pg_000__seed_1","prompt_writing_response":"# a"}\n'
    )
    assert completed_tasks(path) == {"pg_000__seed_1": {"role_assignment", "prompt_writing"}}
