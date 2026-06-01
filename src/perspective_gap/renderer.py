from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

import yaml

ROLE_ASSIGNMENT_TEMPLATE = """\
{background}

I'm providing the following information:

{items_block}

Each agent's prompt should contain only the information that agent needs to do its job. For each sub-agent ({role_list}), which items should go in its prompt? Respond with a JSON object like {example}. No other output.
"""

PROMPT_WRITING_TEMPLATE = """\
{background}

I'm providing the following prompt fragments:

{items_block}

Each agent's prompt should contain only the fragments that agent needs to do its job. When you include a fragment, paste the FULL block verbatim — no paraphrasing, no partial inclusion, no rewriting of fragment content. Brief connective text between fragments (e.g., "Then: ...", "Note: ...") is fine. Format: one markdown section per role, with the role name as an h1 header (e.g. `# {first_role}`). Output only the headered prompts, no preamble.
"""


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
    if not match:
        raise ValueError(f"cannot parse frontmatter in {path}")
    return yaml.safe_load(match.group(1)), match.group(2)


def parse_scenario(path: Path) -> tuple[dict[str, Any], dict[str, str], dict[str, str | None]]:
    metadata, body = parse_frontmatter(path)
    sections: dict[str, str] = {}
    labels: dict[str, str | None] = {}
    pattern = re.compile(r"^# (\S+?)(?::\s*(.+))?$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    for index, match in enumerate(matches):
        section_id = match.group(1)
        labels[section_id] = match.group(2)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[section_id] = body[start:end].strip()
    return metadata, sections, labels


def load_distractor_pool(pool_dir: Path) -> dict[str, str]:
    pool: dict[str, str] = {}
    for path in sorted(pool_dir.glob("*.md")):
        metadata, body = parse_frontmatter(path)
        pool[metadata["id"]] = body.strip()
    if not pool:
        raise RuntimeError(f"distractor pool is empty: {pool_dir}")
    return pool


def inject_distractor(
    sections: dict[str, str],
    shuffle_seed: int,
    pool_dir: Path,
) -> tuple[dict[str, str], str, str]:
    pool = load_distractor_pool(pool_dir)
    pool_id = random.Random(shuffle_seed).choice(sorted(pool.keys()))
    existing_nums = [int(k[1:]) for k in sections if k.startswith("f") and k[1:].isdigit()]
    original_id = f"f{max(existing_nums, default=0) + 1}"
    rendered_sections = dict(sections)
    rendered_sections[original_id] = pool[pool_id]
    return rendered_sections, pool_id, original_id


def shuffle_relabel_map(sections: dict[str, str], shuffle_seed: int) -> dict[str, str]:
    original_ids = sorted(k for k in sections if k.startswith("f"))
    random.Random(shuffle_seed).shuffle(original_ids)
    return {f"f{i}": original_id for i, original_id in enumerate(original_ids, start=1)}


def render_items_block(sections: dict[str, str], relabel_map: dict[str, str]) -> str:
    return "\n\n".join(
        f"<{visible_id}>\n{sections[original_id]}\n</{visible_id}>"
        for visible_id, original_id in relabel_map.items()
    )


def render_role_assignment_prompt(
    sections: dict[str, str],
    roles: list[str],
    relabel_map: dict[str, str],
) -> str:
    example = json.dumps({role: ["f?"] for role in roles})
    return ROLE_ASSIGNMENT_TEMPLATE.format(
        background=sections["background"],
        items_block=render_items_block(sections, relabel_map),
        role_list=", ".join(roles),
        example=example,
    )


def render_prompt_writing_prompt(
    sections: dict[str, str],
    roles: list[str],
    relabel_map: dict[str, str],
) -> str:
    return PROMPT_WRITING_TEMPLATE.format(
        background=sections["background"],
        items_block=render_items_block(sections, relabel_map),
        role_list=", ".join(roles),
        first_role=roles[0],
    )


def render_evaluation(
    scenario_path: Path,
    shuffle_seed: int,
    distractor_pool_dir: Path,
) -> dict[str, Any]:
    metadata, sections, _labels = parse_scenario(scenario_path)
    roles = list(metadata["reference_need_sets"].keys())
    sections, _pool_id, distractor_original_id = inject_distractor(
        sections,
        shuffle_seed,
        distractor_pool_dir,
    )
    relabel_map = shuffle_relabel_map(sections, shuffle_seed)
    original_to_visible = {original_id: visible_id for visible_id, original_id in relabel_map.items()}
    fragments = [
        {
            "id": visible_id,
            "text": sections[original_id],
            "is_distractor": original_id == distractor_original_id,
        }
        for visible_id, original_id in relabel_map.items()
    ]
    reference_need_sets = {
        role: [original_to_visible[original_id] for original_id in original_ids]
        for role, original_ids in metadata["reference_need_sets"].items()
    }
    scenario_id = metadata["scenario_id"]
    return {
        "evaluation_id": f"{scenario_id}__seed_{shuffle_seed}",
        "scenario_id": scenario_id,
        "shuffle_seed": shuffle_seed,
        "roles": roles,
        "fragments": fragments,
        "distractor_id": original_to_visible[distractor_original_id],
        "reference_need_sets": reference_need_sets,
        "role_assignment_prompt": render_role_assignment_prompt(sections, roles, relabel_map),
        "prompt_writing_prompt": render_prompt_writing_prompt(sections, roles, relabel_map),
    }


def iter_scenario_paths(scenarios_dir: Path) -> list[Path]:
    return sorted(scenarios_dir.glob("*.md"))


def build_evaluations(
    scenarios_dir: Path,
    distractor_pool_dir: Path,
    shuffle_seeds: list[int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario_path in iter_scenario_paths(scenarios_dir):
        for shuffle_seed in shuffle_seeds:
            rows.append(render_evaluation(scenario_path, shuffle_seed, distractor_pool_dir))
    return rows


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
