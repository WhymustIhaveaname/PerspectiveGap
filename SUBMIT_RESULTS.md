# Submitting PerspectiveGap Results

Thank you for helping keep the PerspectiveGap leaderboard up to date. This document describes the preferred format for submitting model results for review.

## What counts as an official leaderboard submission?

For the main leaderboard, please run the full released evaluation grid:

- all 110 scenarios in `data/scenarios/`
- shuffle seeds `1` and `42`
- both tasks: `role_assignment` and `prompt_writing`

This produces:

- 220 rendered evaluations (`110 scenarios × 2 seeds`)
- 440 model requests (`220 evaluations × 2 tasks`)
- 440 score rows

Partial runs, smoke tests, ablations, and reruns with modified prompts are welcome for discussion, but they will be marked as non-official unless clearly comparable to the full released grid.

## Preferred run command

Use the repository runner whenever possible. `--model` should be the exact model identifier accepted by the selected provider or route. Do not add a `provider/` prefix unless that endpoint itself requires it; for example, many OpenRouter model IDs include a provider namespace.

```bash
uv sync
mkdir -p predictions scores

uv run python scripts/run_model_predictions.py \
  --provider <PROVIDER> \
  --model <API_MODEL_ID> \
  --shuffle-seed 1 \
  --shuffle-seed 42 \
  --tasks both \
  --out predictions/<api-model-id>.jsonl
```

Then score the predictions:

```bash
uv run python scripts/score_predictions.py \
  --predictions predictions/<api-model-id>.jsonl \
  --out scores/<api-model-id>.scores.jsonl \
  | tee scores/<api-model-id>.summary.txt
```

If you use an OpenAI-compatible endpoint, include the endpoint and API-key environment variable in the command:

```bash
uv run python scripts/run_model_predictions.py \
  --provider openai-compatible \
  --base-url <BASE_URL> \
  --api-key-env <ENV_VAR_NAME> \
  --model <API_MODEL_ID> \
  --shuffle-seed 1 \
  --shuffle-seed 42 \
  --tasks both \
  --out predictions/<api-model-id>.jsonl
```

## Required artifacts

Please provide all of the following, either attached to the GitHub issue/PR or linked from a stable public location:

1. **Raw prediction JSONL** from `scripts/run_model_predictions.py` or an equivalent runner.
2. **Score JSONL** from `scripts/score_predictions.py --out ...`.
3. **Score summary text** printed by `scripts/score_predictions.py`.
4. **Run metadata**, including:
   - exact API model ID and provider/route
   - model snapshot, version, or dated alias if the provider exposes one
   - date of run
   - PerspectiveGap Git commit SHA
   - Hugging Face dataset revision, if loaded from HF
   - command lines used for rendering/running/scoring
   - endpoint or route used, if not the provider's direct API
   - any non-default decoding parameters, system prompts, wrappers, retries, or post-processing
   - immutable artifact revision, commit SHA, release asset URL, or checksum when available

Do not include API keys, account IDs, billing data, private prompts, or other secrets in any artifact. Keep failed-request rows, but review `error.message` fields before submitting and redact API keys, account identifiers, private endpoints, billing/project/org IDs, and similar sensitive details. If you redact an error message, note that in the run metadata.

## Prediction JSONL schema

The preferred prediction row format is the format emitted by `scripts/run_model_predictions.py`:

```json
{
  "evaluation_id": "pg_000__seed_1__task_role_assignment",
  "base_evaluation_id": "pg_000__seed_1",
  "scenario_id": "pg_000",
  "shuffle_seed": 1,
  "task": "role_assignment",
  "model": "api-model-id",
  "provider": "provider",
  "response": "...",
  "status": "ok"
}
```

For failed model requests, keep the error row rather than silently dropping it:

```json
{
  "evaluation_id": "pg_000__seed_1__task_role_assignment",
  "base_evaluation_id": "pg_000__seed_1",
  "scenario_id": "pg_000",
  "shuffle_seed": 1,
  "task": "role_assignment",
  "model": "api-model-id",
  "provider": "provider",
  "response": null,
  "status": "error",
  "error": {"type": "...", "message": "..."}
}
```

The scorer also accepts the older two-response-per-row format used by early development artifacts, but new submissions should use one row per model request.

## Quick validation checks

Before submitting, please run:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

pred_path = Path("predictions/<api-model-id>.jsonl")
score_path = Path("scores/<api-model-id>.scores.jsonl")

preds = [json.loads(line) for line in pred_path.read_text().splitlines() if line.strip()]
scores = [json.loads(line) for line in score_path.read_text().splitlines() if line.strip()]

pred_keys = {
    (row.get("scenario_id"), row.get("shuffle_seed"), row.get("task"))
    for row in preds
}
score_keys = {
    (row.get("base_evaluation_id") or row.get("evaluation_id", "").split("__task_", 1)[0], row.get("task"))
    for row in scores
}

print("prediction rows:", len(preds))
print("score rows:", len(scores))
print("unique prediction keys:", len(pred_keys))
print("unique score keys:", len(score_keys))
print("tasks:", Counter(row.get("task") for row in preds))
print("status:", Counter(row.get("status", "missing") for row in preds))
print("models:", sorted({row.get("model") for row in preds}))
print("scenario count:", len({row.get("scenario_id") for row in preds}))
print("seeds:", sorted({row.get("shuffle_seed") for row in preds}))
PY
```

For a full official run, expected output should include:

- `prediction rows: 440`
- `score rows: 440`
- `unique prediction keys: 440`
- `unique score keys: 440`
- task counts: `role_assignment: 220`, `prompt_writing: 220`
- scenario count: `110`
- seeds: `[1, 42]`
- exactly one model ID

## Reporting metrics

The leaderboard's primary metric is:

```text
combined pass rate = (role_assignment strict passes + prompt_writing strict passes) / 440
```

Please include the printed summary from the scorer. Maintainers will recompute the combined score from the score JSONL; if you report it yourself, use the formula above rather than a rounded display value. The scorer reports, per task:

- `strict_pass`
- `net_match_score`
- `required_coverage`
- `boundary_precision`
- `distractor_leakage`

You can also compute the combined score from score JSONL:

```bash
python - <<'PY'
import json
from pathlib import Path

score_path = Path("scores/<api-model-id>.scores.jsonl")
rows = [json.loads(line) for line in score_path.read_text().splitlines() if line.strip()]
role_pass = sum(row.get("role_assignment", {}).get("pass", False) for row in rows)
prompt_pass = sum(row.get("prompt_writing", {}).get("pass", False) for row in rows)
total = len(rows)
print(f"role passes: {role_pass}")
print(f"prompt passes: {prompt_pass}")
print(f"combined: {role_pass + prompt_pass}/{total} ({(role_pass + prompt_pass) / total:.1%})")
PY
```

## How to submit

Open a GitHub issue using the **Submit PerspectiveGap result** template and provide the required metadata and artifact links.

If the artifacts are too large for a GitHub issue, upload them to a public Hugging Face dataset repo, gist, release asset, or other stable URL, then link them in the issue. Prefer immutable links such as a Hugging Face dataset commit, GitHub release asset, or checksum-pinned archive.

Maintainers may verify the submission by rerunning the scorer and checking row counts, model identity, dataset/scorer revision, and command-line compatibility before updating the leaderboard.
