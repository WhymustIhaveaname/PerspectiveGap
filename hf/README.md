---
task_categories:
- text-generation
tags:
- benchmark
- theory-of-mind
- multi-agent
- information-management
configs:
- config_name: default
  data_files:
  - split: test
    path: evaluations.jsonl
---

# PerspectiveGap

PerspectiveGap is a benchmark for evaluating LLMs' ability to compose prompts for multi-agent systems.

This Hugging Face dataset contains the released rendered set: 220 rows from 110 scenarios rendered with seeds 1 and 42. Each row includes the two task prompts, visible fragments, distractor ID, and answer key. Use the GitHub repository for running models and scoring predictions.

## Fields

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
