---
pretty_name: PerspectiveGap
license: mit
language:
- en
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
size_categories:
- n<1K
configs:
- config_name: default
  data_files:
  - split: test
    path: evaluations.jsonl
---

# PerspectiveGap

PerspectiveGap is a benchmark for evaluating LLMs' ability to compose orchestration prompts for multi-agent systems.

Paper: [PerspectiveGap: A Benchmark for Multi-Agent Orchestration Prompting](https://arxiv.org/abs/2606.08878)

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

## Loading

```python
from datasets import load_dataset

ds = load_dataset("sun1245/PerspectiveGap", split="test")
print(ds[0]["evaluation_id"])
```

If you mirror this dataset under another namespace, replace `sun1245/PerspectiveGap` with that dataset repository ID.

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
