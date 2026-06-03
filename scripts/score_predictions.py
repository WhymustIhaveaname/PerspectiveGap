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
    summary = summarize_scores(results)
    print(format_metric_summary(summary))
    if args.out is not None:
        write_jsonl(results, args.out)
        print(f"wrote {len(results)} score rows to {args.out}")


if __name__ == "__main__":
    main()
