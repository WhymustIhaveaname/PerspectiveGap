#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perspective_gap.renderer import render_evaluation, write_jsonl
from perspective_gap.scoring import format_metric_summary, score_prediction, summarize_scores
from perspective_gap.model_runner import TASK_EVALUATION_ID_MARKER, task_evaluation_id


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def normalize_prediction_rows(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        if row.get("task") in {"role_assignment", "prompt_writing"} and "response" in row:
            normalized.append(dict(row))
            continue
        if "role_assignment_response" in row:
            converted = dict(row)
            converted["task"] = "role_assignment"
            converted["response"] = row["role_assignment_response"]
            converted.setdefault("base_evaluation_id", row["evaluation_id"])
            converted["evaluation_id"] = task_evaluation_id(row["evaluation_id"], "role_assignment")
            converted.pop("role_assignment_response", None)
            converted.pop("prompt_writing_response", None)
            normalized.append(converted)
        if "prompt_writing_response" in row:
            converted = dict(row)
            converted["task"] = "prompt_writing"
            converted["response"] = row["prompt_writing_response"]
            converted.setdefault("base_evaluation_id", row["evaluation_id"])
            converted["evaluation_id"] = task_evaluation_id(row["evaluation_id"], "prompt_writing")
            converted.pop("role_assignment_response", None)
            converted.pop("prompt_writing_response", None)
            normalized.append(converted)
    return normalized


def split_evaluation_id(evaluation_id: str) -> tuple[str, int]:
    if TASK_EVALUATION_ID_MARKER in evaluation_id:
        evaluation_id, _task = evaluation_id.rsplit(TASK_EVALUATION_ID_MARKER, 1)
    marker = "__seed_"
    if marker not in evaluation_id:
        raise SystemExit(f"prediction missing scenario_id/shuffle_seed and has invalid evaluation_id: {evaluation_id}")
    scenario_id, seed = evaluation_id.rsplit(marker, 1)
    return scenario_id, int(seed)


def resolve_evaluation(prediction: dict) -> dict:
    scenario_id = prediction.get("scenario_id")
    shuffle_seed = prediction.get("shuffle_seed")
    if scenario_id is None or shuffle_seed is None:
        scenario_id, shuffle_seed = split_evaluation_id(prediction.get("base_evaluation_id") or prediction["evaluation_id"])
    scenario_path = ROOT / "data" / "scenarios" / f"{scenario_id}.md"
    if not scenario_path.exists():
        raise SystemExit(f"prediction references unknown scenario_id: {scenario_id}")
    return render_evaluation(scenario_path, int(shuffle_seed), ROOT / "data" / "distractors")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score PerspectiveGap prediction JSONL.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    predictions = normalize_prediction_rows(load_jsonl(args.predictions))
    results = []
    for prediction in predictions:
        evaluation = resolve_evaluation(prediction)
        results.append(score_prediction(evaluation, prediction))
    summary = summarize_scores(results)
    print(format_metric_summary(summary))
    if args.out is not None:
        write_jsonl(results, args.out)
        print(f"wrote {len(results)} score rows to {args.out}")


if __name__ == "__main__":
    main()
