# PerspectiveGap

PerspectiveGap is a benchmark for evaluating LLMs' ability to compose prompts for multi-agent systems.

This repository provides the benchmark data and minimal scripts for rendering, evaluation, and metric computation.
For readability and ease of inspection, production-oriented features such as Batch API submission are intentionally not included.

## Links

- Paper: <https://arxiv.org/abs/2606.08878>
- Hugging Face dataset: <https://huggingface.co/datasets/sun1245/PerspectiveGap>
- Interactive leaderboard: <https://huggingface.co/spaces/sun1245/PerspectiveGap-Leaderboard>
- Hugging Face collection: <https://huggingface.co/collections/sun1245/perspectivegap-benchmark-6a29cc320b94890356c60dd7>

## Setup

PerspectiveGap uses Python 3.13+ and [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
git clone https://github.com/WhymustIhaveaname/PerspectiveGap.git
cd PerspectiveGap
uv sync
```

Most local inspection and scoring commands below do not require any model API key.
Model-calling commands require the corresponding provider environment variable:

| Provider | Environment variable |
|---|---|
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |
| `kimi` | `KIMI_API_KEY` |
| `nvidia` | `NVIDIA_API_KEY` |
| `openrouter` | `OPENROUTER_API_KEY` |

## Quick start

Score the bundled example without any API key.

```bash
uv run python scripts/score_predictions.py --predictions tests/fixtures/example_predictions.jsonl
```

Render the Hugging Face release JSONL locally without any API key.

```bash
uv run python scripts/build_hf_evaluations.py --out /tmp/perspectivegap-evaluations.jsonl
```

Set your provider API key, then run one minimal model-calling smoke test and score it.
This example sends one API request by restricting the task to `role_assignment`; omit `--tasks role_assignment` to run both released tasks.

```bash
uv run python scripts/run_model_predictions.py \
  --provider openai --model <MODEL_YOU_HAVE_ACCESS_TO> \
  --scenario-id pg_006 --shuffle-seed 1 --tasks role_assignment \
  --out predictions/smoke.jsonl
uv run python scripts/score_predictions.py --predictions predictions/smoke.jsonl
```

## Scripts and parameters

`scripts/run_model_predictions.py` renders evaluations from `data/scenarios` and `data/distractors`, calls the model, and writes prediction JSONL.
Each JSONL row is one model API request for one task. Its `evaluation_id` includes the scenario, seed, and task, for example `pg_006__seed_1__task_role_assignment`.
Resume uses `(evaluation_id, model)`, so the same output file can contain different model IDs without skipping the wrong model.
Failed API requests are also written as JSONL rows with `status: "error"`, `response: null`, and an `error` object.

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
