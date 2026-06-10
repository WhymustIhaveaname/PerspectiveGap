---
pretty_name: PerspectiveGap
license: mit
language:
- en
annotations_creators:
- expert-generated
language_creators:
- expert-generated
multilinguality:
- monolingual
source_datasets:
- original
task_categories:
- text-generation
tags:
- benchmark
- theory-of-mind
- multi-agent
- information-management
- orchestration
- prompt-engineering
- arxiv:2606.08878
- text
- jsonl
- datasets
size_categories:
- n<1K
configs:
- config_name: default
  data_files:
  - split: test
    path: evaluations.jsonl
---

# Dataset Card for PerspectiveGap

PerspectiveGap is a benchmark for evaluating LLMs' ability to compose orchestration prompts for multi-agent systems.
It tests whether a model can decide what each sub-agent in a multi-agent workflow needs to know, without leaking irrelevant context.

Paper: [PerspectiveGap: A Benchmark for Multi-Agent Orchestration Prompting](https://arxiv.org/abs/2606.08878)

Code and scorers: [WhymustIhaveaname/PerspectiveGap](https://github.com/WhymustIhaveaname/PerspectiveGap)

Interactive leaderboard: [sun1245/PerspectiveGap-Leaderboard](https://huggingface.co/spaces/sun1245/PerspectiveGap-Leaderboard)

Project collection: [PerspectiveGap Benchmark](https://huggingface.co/collections/sun1245/perspectivegap-benchmark-6a29cc320b94890356c60dd7)

This Hugging Face dataset contains the released rendered set: 220 rows from 110 scenarios rendered with seeds 1 and 42. Each row includes the two task prompts, visible fragments, distractor ID, and answer key.

## Dataset Details

### Dataset Description

- Curated by: the PerspectiveGap paper authors
- Language: English
- License: MIT
- Repository: <https://github.com/WhymustIhaveaname/PerspectiveGap>
- Paper: <https://arxiv.org/abs/2606.08878>
- Leaderboard: <https://huggingface.co/spaces/sun1245/PerspectiveGap-Leaderboard>
- Project collection: <https://huggingface.co/collections/sun1245/perspectivegap-benchmark-6a29cc320b94890356c60dd7>

The dataset is released as a single `test` split. It is intended for benchmarking prompt composition and context filtering in multi-agent orchestration settings.

### Dataset Sources

The released JSONL is deterministically rendered from the source scenarios in the GitHub repository. Three generic prompt-engineering distractor fragments are included in the source repository with source URLs recorded in their markdown frontmatter; preserve those attributions if you redistribute modified source files.

## Uses

### Direct Use

Use PerspectiveGap to evaluate models or prompting systems on two tasks:

1. **Role-fragment assignment**: select the visible fragment IDs that belong in each sub-agent prompt.
2. **Prompt writing**: write one prompt per sub-agent while including only the needed fragments.

The accompanying GitHub repository contains scripts for rendering model requests and scoring predictions.

### Out-of-Scope Use

Do not use this test set, including `reference_need_sets` or `distractor_id`, as model training data or as an in-context demonstration set when reporting benchmark results. The dataset is not designed to represent all possible multi-agent architectures, application domains, or safety requirements.

## Dataset Structure

### Data Splits

| split | rows | scenarios | shuffle seeds |
|---|---:|---:|---|
| `test` | 220 | 110 | 1, 42 |

### Data Fields

| field | meaning |
|---|---|
| `evaluation_id` | stable row ID |
| `scenario_id` | source scenario ID |
| `shuffle_seed` | seed used for distractor sampling and fragment order |
| `roles` | roles that need prompts |
| `fragments` | visible fragments shown to the model |
| `distractor_id` | visible fragment ID of the distractor |
| `reference_need_sets` | answer key in visible fragment IDs |
| `role_assignment_prompt` | prompt for the JSON assignment task |
| `prompt_writing_prompt` | prompt for the free-form writing task |

`distractor_id` is already in the visible ID space, so no relabel map is needed.
Each dataset row contains both task prompts. The reference runner in the GitHub repository sends one model request per selected task.

## Loading

```python
from datasets import load_dataset

ds = load_dataset("sun1245/PerspectiveGap", split="test")
print(ds[0]["evaluation_id"])
```

If you mirror this dataset under another namespace, replace `sun1245/PerspectiveGap` with that dataset repository ID.

## Evaluation

```bash
git clone https://github.com/WhymustIhaveaname/PerspectiveGap.git
cd PerspectiveGap
uv sync

# Score the bundled example without any API key.
uv run python scripts/score_predictions.py --predictions tests/fixtures/example_predictions.jsonl
```

To run a model, set the relevant provider API key and use `scripts/run_model_predictions.py`; see the GitHub README for provider names and environment variables.

## Dataset Creation

The benchmark scenarios were curated to test information routing decisions in multi-agent workflows. For the released Hugging Face file, each source scenario is rendered with two deterministic shuffle seeds. Rendering injects one generic distractor fragment, shuffles the visible fragments, relabels them into the visible `f1`, `f2`, ... ID space, and emits both task prompts plus the answer key.

## Evaluation Notes

- PerspectiveGap is an answer-keyed benchmark for multi-agent orchestration prompting and context routing.
- The released scenarios are curated to stress role-specific information selection, distractor resistance, and prompt composition across diverse orchestration topologies.
- The included answer keys make scoring transparent and auditable.
- The prompt-writing scorer in the GitHub repository is deterministic, fast, and reproducible; it measures whether generated prompts include the needed fragments while excluding irrelevant ones.
- For benchmark reporting, use the dataset as a held-out evaluation set and follow the rendering and scoring scripts in the GitHub repository.

## More Information

- GitHub repository: <https://github.com/WhymustIhaveaname/PerspectiveGap>
- arXiv paper: <https://arxiv.org/abs/2606.08878>
- Interactive leaderboard: <https://huggingface.co/spaces/sun1245/PerspectiveGap-Leaderboard>
- Hugging Face collection: <https://huggingface.co/collections/sun1245/perspectivegap-benchmark-6a29cc320b94890356c60dd7>

## Citation

```bibtex
@misc{sun2026perspectivegapbenchmarkmultiagentorchestration,
      title={PerspectiveGap: A Benchmark for Multi-Agent Orchestration Prompting}, 
      author={Youran Sun and Xingyu Ren and Kejia Zhang and Xinpeng Liu and Jiaxuan Guo},
      year={2026},
      eprint={2606.08878},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2606.08878}, 
}
```
