import json

from perspective_gap import scoring
from perspective_gap.scoring import score_prediction, score_prompt_writing, score_role_assignment, summarize_scores


def test_role_assignment_scores_exact_visible_sets():
    response = json.dumps({"coder": ["f1", "f3"], "reviewer": ["f2"]})
    result = score_role_assignment(response, {"coder": ["f3", "f1"], "reviewer": ["f2"]})
    assert result["pass"] is True


def test_role_assignment_rejects_extra_fragment():
    response = json.dumps({"coder": ["f1", "f3", "f4"], "reviewer": ["f2"]})
    result = score_role_assignment(response, {"coder": ["f3", "f1"], "reviewer": ["f2"]})
    assert result["pass"] is False
    assert result["per_role"] == {"coder": False, "reviewer": True}


def test_prompt_writing_flags_visible_distractor_leak(monkeypatch):
    monkeypatch.setattr(scoring, "token_sequence", lambda text: text.lower().split())
    fragments = [
        {"id": "f1", "text": "alpha coder only"},
        {"id": "f2", "text": "beta reviewer only"},
        {"id": "f3", "text": "gamma distractor advice"},
    ]
    response = "# coder\nalpha coder only gamma distractor advice\n\n# reviewer\nbeta reviewer only"
    result = score_prompt_writing(
        response,
        fragments,
        {"coder": ["f1"], "reviewer": ["f2"]},
        distractor_id="f3",
        include_threshold=0.7,
        exclude_threshold=0.3,
    )
    assert result["pass"] is False
    assert result["per_role"]["coder"]["distractor_leak"] == ["f3"]


def test_role_assignment_reports_five_metrics():
    response = json.dumps({"coder": ["f1", "f3"], "reviewer": ["f2"]})
    result = score_role_assignment(response, {"coder": ["f1", "f2"], "reviewer": ["f2"]}, distractor_id="f3")
    assert result["counts"] == {"tp": 2, "fp": 1, "fn": 1, "distractor_leak": 1}
    assert result["metrics"] == {
        "strict_pass": 0.0,
        "net_match_score": 0.0,
        "required_coverage": 2 / 3,
        "boundary_precision": 2 / 3,
        "distractor_leakage": 1.0,
    }


def test_score_prediction_scores_task_failure_row_as_failure():
    evaluation = {
        "evaluation_id": "pg_x__seed_1",
        "reference_need_sets": {"coder": ["f1"]},
        "fragments": [{"id": "f1", "text": "alpha"}],
    }
    prediction = {
        "evaluation_id": "pg_x__seed_1__task_role_assignment",
        "base_evaluation_id": "pg_x__seed_1",
        "task": "role_assignment",
        "status": "error",
        "response": None,
        "error": {"type": "RuntimeError", "message": "blocked"},
    }
    result = score_prediction(evaluation, prediction)
    assert result["status"] == "error"
    assert result["error"] == {"type": "RuntimeError", "message": "blocked"}
    assert result["role_assignment"]["pass"] is False
    assert result["role_assignment"]["counts"] == {"tp": 0, "fp": 0, "fn": 1, "distractor_leak": 0}


def test_summarize_scores_reports_paper_metrics():
    rows = [
        {
            "evaluation_id": "ok",
            "role_assignment": {
                "pass": True,
                "counts": {"tp": 2, "fp": 0, "fn": 0, "distractor_leak": 0},
                "metrics": {
                    "strict_pass": 1.0,
                    "net_match_score": 1.0,
                    "required_coverage": 1.0,
                    "boundary_precision": 1.0,
                    "distractor_leakage": 0.0,
                },
            },
        },
        {
            "evaluation_id": "bad",
            "role_assignment": {
                "pass": False,
                "counts": {"tp": 1, "fp": 1, "fn": 1, "distractor_leak": 1},
                "metrics": {
                    "strict_pass": 0.0,
                    "net_match_score": 0.0,
                    "required_coverage": 0.5,
                    "boundary_precision": 0.5,
                    "distractor_leakage": 1.0,
                },
            },
        },
    ]
    metrics = summarize_scores(rows)["role_assignment"]["metrics"]
    assert metrics["strict_pass"] == 0.5
    assert metrics["net_match_score"] == 0.5
    assert metrics["required_coverage"] == 3 / 4
    assert metrics["boundary_precision"] == 3 / 4
    assert metrics["distractor_leakage"] == 0.5
