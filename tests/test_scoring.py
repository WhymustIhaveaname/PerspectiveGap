import json

from perspective_gap import scoring
from perspective_gap.scoring import score_prompt_writing, score_role_assignment


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
