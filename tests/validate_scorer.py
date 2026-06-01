#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perspective_gap.scoring import score_prompt_writing


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the PerspectiveGap prompt-writing scorer.")
    parser.add_argument("--validation", type=Path, default=ROOT / "data" / "scorer_validation.jsonl")
    args = parser.parse_args()

    rows = load_jsonl(args.validation)
    total = 0
    correct = 0
    for row in rows:
        result = score_prompt_writing(
            row["response"],
            row["fragments"],
            row["reference_need_sets"],
            row.get("distractor_id"),
        )
        role_result = result["per_role"].get(row["role"], {"pass": False})
        total += 1
        correct += role_result["pass"] == row["label_pass"]
    print(f"scorer validation accuracy: {correct}/{total} ({correct / total * 100:.1f}%)")


if __name__ == "__main__":
    main()
