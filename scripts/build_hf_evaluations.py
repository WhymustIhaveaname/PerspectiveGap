#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perspective_gap.renderer import build_evaluations, write_jsonl


def parse_seeds(text: str) -> list[int]:
    return [int(part.strip()) for part in text.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the rendered PerspectiveGap HF JSONL.")
    parser.add_argument("--shuffle-seeds", default="1,42")
    parser.add_argument("--out", type=Path, default=Path("hf/evaluations.jsonl"))
    args = parser.parse_args()

    rows = build_evaluations(
        scenarios_dir=ROOT / "data" / "scenarios",
        distractor_pool_dir=ROOT / "data" / "distractors",
        shuffle_seeds=parse_seeds(args.shuffle_seeds),
    )
    write_jsonl(rows, args.out)
    print(f"wrote {len(rows)} evaluations to {args.out}")


if __name__ == "__main__":
    main()
