#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perspective_gap.renderer import render_evaluation, write_jsonl
from perspective_gap.scoring import score_prediction


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def merge_prediction_rows(rows: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (row["evaluation_id"], row.get("provider", ""), row.get("model", ""))
        if key not in merged:
            merged[key] = dict(row)
        else:
            merged[key].update(row)
    return list(merged.values())


def split_evaluation_id(evaluation_id: str) -> tuple[str, int]:
    marker = "__seed_"
    if marker not in evaluation_id:
        raise SystemExit(f"prediction missing scenario_id/shuffle_seed and has invalid evaluation_id: {evaluation_id}")
    scenario_id, seed = evaluation_id.rsplit(marker, 1)
    return scenario_id, int(seed)


def resolve_evaluation(prediction: dict) -> dict:
    scenario_id = prediction.get("scenario_id")
    shuffle_seed = prediction.get("shuffle_seed")
    if scenario_id is None or shuffle_seed is None:
        scenario_id, shuffle_seed = split_evaluation_id(prediction["evaluation_id"])
    scenario_path = ROOT / "data" / "scenarios" / f"{scenario_id}.md"
    if not scenario_path.exists():
        raise SystemExit(f"prediction references unknown scenario_id: {scenario_id}")
    return render_evaluation(scenario_path, int(shuffle_seed), ROOT / "data" / "distractors")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score PerspectiveGap prediction JSONL.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    predictions = merge_prediction_rows(load_jsonl(args.predictions))
    results = []
    for prediction in predictions:
        evaluation = resolve_evaluation(prediction)
        results.append(score_prediction(evaluation, prediction))
    if args.out is None:
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
    else:
        write_jsonl(results, args.out)

    role_assignment_total = sum("role_assignment" in row for row in results)
    role_assignment_pass = sum(row.get("role_assignment", {}).get("pass", False) for row in results)
    prompt_writing_total = sum("prompt_writing" in row for row in results)
    prompt_writing_pass = sum(row.get("prompt_writing", {}).get("pass", False) for row in results)
    stream = sys.stderr if args.out is None else sys.stdout
    if args.out is not None:
        print(f"wrote {len(results)} score rows to {args.out}", file=stream)
    if role_assignment_total:
        print(f"role-fragment assignment: {role_assignment_pass}/{role_assignment_total}", file=stream)
    if prompt_writing_total:
        print(f"free-form prompt writing: {prompt_writing_pass}/{prompt_writing_total}", file=stream)


if __name__ == "__main__":
    main()
