# PerspectiveGap

PerspectiveGap is a benchmark for evaluating LLMs' ability to compose prompts for multi-agent systems.

## Quick start

Score the bundled example without any API key.

```bash
uv run python scripts/score_predictions.py --predictions tests/fixtures/example_predictions.jsonl
```

Set your provider API key, then run one rendered evaluation and score it.

```bash
uv run python scripts/run_model_predictions.py \
  --provider openai --model gpt-5.5 \
  --scenario-id pg_006 --shuffle-seed 1 \
  --out predictions/smoke.jsonl
uv run python scripts/score_predictions.py --predictions predictions/smoke.jsonl
```

## Scripts and parameters

`scripts/run_model_predictions.py` renders evaluations from `data/scenarios` and `data/distractors`, calls the model, and writes prediction JSONL.
Each JSONL row is one model API request for one task. Its `evaluation_id` includes the scenario, seed, and task, for example `pg_006__seed_1__task_role_assignment`.
Resume uses `(evaluation_id, model)`, so the same output file can contain different model IDs without skipping the wrong model.
Failed API requests are also written as JSONL rows with `status: "error"`, `response: null`, and an `error` object. These rows are counted as completed for resume and scored as failures.

| Parameter | Default | Meaning |
|---|---:|---|
| `--provider` | required | Model provider: `openai`, `anthropic`, `deepseek`, `kimi`, `nvidia`, `openrouter`, or `openai-compatible`. |
| `--model` | required | Provider model ID. |
| `--out` | required | Prediction JSONL path. Existing rows are used for resume; completed `(evaluation_id, model)` requests are skipped. |
| `--tasks` | `both` | Which task to run: `role_assignment`, `prompt_writing`, or `both`. |
| `--shuffle-seed` | `42` | Integer render seed. Can be repeated to run multiple seeds. |
| `--scenario-id` | all scenarios | Source scenario ID, e.g. `pg_006`. Can be comma-separated (`pg_006,pg_070`) or repeated. |
| `--base-url` | provider endpoint | Override the API endpoint. Required for `openai-compatible`. |
| `--api-key-env` | provider key env | Override the API-key environment variable. |

`scripts/score_predictions.py`

The scorer writes one score JSONL row per prediction row/API request.

| Parameter | Default | Meaning |
|---|---:|---|
| `--predictions` | required | Prediction JSONL from the model runner or another system. |
| `--out` | stdout | Optional score JSONL path. |
