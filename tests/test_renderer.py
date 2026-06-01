from pathlib import Path

from perspective_gap.renderer import build_evaluations


ROOT = Path(__file__).resolve().parents[1]


def test_builds_official_220_rows():
    rows = build_evaluations(
        ROOT / "data" / "scenarios",
        ROOT / "data" / "distractors",
        [1, 42],
    )
    assert len(rows) == 220
    assert rows[0]["evaluation_id"] == "pg_000__seed_1"
    assert rows[1]["evaluation_id"] == "pg_000__seed_42"


def test_distractor_id_is_visible_fragment_id():
    row = build_evaluations(
        ROOT / "data" / "scenarios",
        ROOT / "data" / "distractors",
        [1],
    )[0]
    fragment_ids = {fragment["id"] for fragment in row["fragments"]}
    distractor_fragments = [fragment for fragment in row["fragments"] if fragment["is_distractor"]]
    assert row["distractor_id"] in fragment_ids
    assert [fragment["id"] for fragment in distractor_fragments] == [row["distractor_id"]]
    assert "relabel_map" not in row
