from pathlib import Path
from argparse import Namespace
import json

import pytest

from perspective_gap import model_runner
from perspective_gap.model_runner import (
    completed_requests,
    dynamic_evaluations,
    parse_scenario_ids,
    parse_tasks,
    run_predictions,
    task_evaluation_id,
)


ROOT = Path(__file__).resolve().parents[1]


def test_parse_tasks_accepts_task_subset():
    assert parse_tasks("role_assignment") == ["role_assignment"]
    assert parse_tasks("prompt_writing") == ["prompt_writing"]
    assert parse_tasks("both") == ["role_assignment", "prompt_writing"]


def test_parse_tasks_rejects_unknown_task():
    with pytest.raises(ValueError, match="unknown task"):
        parse_tasks("role_assignment,unknown")


def test_parse_scenario_ids_accepts_comma_separated_and_repeated_values():
    assert parse_scenario_ids(["pg_006,pg_070", "pg_071"]) == ["pg_006", "pg_070", "pg_071"]


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


def test_dynamic_evaluations_accepts_comma_separated_scenario_ids():
    rows = dynamic_evaluations(
        ROOT / "data" / "scenarios",
        ROOT / "data" / "distractors",
        scenario_ids=["pg_006,pg_070"],
        shuffle_seeds=[1],
    )
    assert [row["evaluation_id"] for row in rows] == ["pg_006__seed_1", "pg_070__seed_1"]


def test_completed_requests_reads_request_rows_by_evaluation_and_model(tmp_path):
    path = tmp_path / "predictions.jsonl"
    path.write_text(
        '{"evaluation_id":"pg_000__seed_1__task_role_assignment","model":"m1","task":"role_assignment","response":"{}"}\n'
        '{"evaluation_id":"pg_000__seed_1__task_prompt_writing","model":"m1","task":"prompt_writing","response":"# a"}\n'
        '{"evaluation_id":"pg_000__seed_1__task_role_assignment","model":"m2","task":"role_assignment","response":"{}"}\n'
    )
    assert completed_requests(path) == {
        ("pg_000__seed_1__task_role_assignment", "m1"),
        ("pg_000__seed_1__task_prompt_writing", "m1"),
        ("pg_000__seed_1__task_role_assignment", "m2"),
    }


def test_completed_requests_supports_legacy_task_response_rows(tmp_path):
    path = tmp_path / "predictions.jsonl"
    path.write_text(
        '{"evaluation_id":"pg_000__seed_1","model":"m1","role_assignment_response":"{}"}\n'
        '{"evaluation_id":"pg_000__seed_1","model":"m1","prompt_writing_response":"# a"}\n'
    )
    assert completed_requests(path) == {
        (task_evaluation_id("pg_000__seed_1", "role_assignment"), "m1"),
        (task_evaluation_id("pg_000__seed_1", "prompt_writing"), "m1"),
    }


def test_run_predictions_writes_one_row_per_request_and_resumes_by_model(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self):
            self.calls = 0

        def generate(self, prompt: str, max_output_tokens: int) -> str:
            self.calls += 1
            return "{}" if "JSON object" in prompt else "# coder\n"

    fake_client = FakeClient()
    monkeypatch.setattr(model_runner, "build_client", lambda args: fake_client)

    out = tmp_path / "predictions.jsonl"
    args = Namespace(
        provider="openai",
        model="m1",
        out=out,
        tasks="both",
        shuffle_seed=[1],
        scenario_id=["pg_000"],
        base_url=None,
        api_key_env=None,
    )
    run_predictions(args)
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert fake_client.calls == 2
    assert [row["evaluation_id"] for row in rows] == [
        "pg_000__seed_1__task_role_assignment",
        "pg_000__seed_1__task_prompt_writing",
    ]
    assert [row["task"] for row in rows] == ["role_assignment", "prompt_writing"]
    assert all("response" in row for row in rows)
    assert not any("role_assignment_response" in row or "prompt_writing_response" in row for row in rows)

    run_predictions(args)
    assert fake_client.calls == 2
    assert len(out.read_text().splitlines()) == 2

    args.model = "m2"
    run_predictions(args)
    assert fake_client.calls == 4
    assert len(out.read_text().splitlines()) == 4
