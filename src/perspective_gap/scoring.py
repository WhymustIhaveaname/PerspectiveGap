from __future__ import annotations

import json
import re
from typing import Any

from tokenizers import Tokenizer

_TOKENIZER: Tokenizer | None = None
_TOKENIZER_NAME = "Qwen/Qwen3.5-0.8B"
NGRAM_ORDERS = (1, 2, 3)
METRIC_NAMES = (
    "strict_pass",
    "net_match_score",
    "required_coverage",
    "boundary_precision",
    "distractor_leakage",
)


def _tokenizer() -> Tokenizer:
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = Tokenizer.from_pretrained(_TOKENIZER_NAME)
    return _TOKENIZER


def parse_json_response(text: str | None) -> Any:
    if text is None:
        raise ValueError("empty response")
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n(.*?)\n```\s*$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def parse_json_object_loose(text: str | None) -> dict[str, Any]:
    if text is None:
        raise ValueError("empty response")
    try:
        parsed = parse_json_response(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")
    return parsed


def metric_values(strict_pass: bool, tp: int, fp: int, fn: int, distractor_leak: int) -> dict[str, float]:
    expected = tp + fn
    predicted = tp + fp
    return {
        "strict_pass": float(strict_pass),
        "net_match_score": max(0.0, (tp - fp - fn) / expected) if expected else 0.0,
        "required_coverage": tp / expected if expected else 0.0,
        "boundary_precision": tp / predicted if predicted else 0.0,
        "distractor_leakage": float(distractor_leak),
    }


def score_role_assignment(
    response_text: str | None,
    reference_need_sets: dict[str, list[str]],
    distractor_id: str | None = None,
) -> dict[str, Any]:
    reference_event_count = sum(len(items) for items in reference_need_sets.values())
    parse_fail_counts = {"tp": 0, "fp": 0, "fn": reference_event_count, "distractor_leak": 0}
    strict_error = None
    try:
        strict_predicted = parse_json_response(response_text)
        if not isinstance(strict_predicted, dict):
            strict_error = "response is not a JSON object"
    except (json.JSONDecodeError, ValueError) as error:
        strict_predicted = None
        strict_error = f"parse: {error}"
    try:
        boundary_predicted = parse_json_object_loose(response_text)
    except (json.JSONDecodeError, ValueError) as error:
        return {
            "pass": False,
            "metrics": metric_values(False, **parse_fail_counts),
            "counts": parse_fail_counts,
            "predicted": strict_predicted,
            "normalized": None,
            "per_role": {},
            "error": strict_error or f"parse: {error}",
        }
    normalized = {
        role: sorted({fragment_id for fragment_id in fragment_ids if isinstance(fragment_id, str)})
        for role, fragment_ids in boundary_predicted.items()
        if isinstance(fragment_ids, list)
    }
    strict_role_values_are_valid = (
        isinstance(strict_predicted, dict)
        and all(
            isinstance(fragment_ids, list)
            and all(isinstance(fragment_id, str) for fragment_id in fragment_ids)
            for fragment_ids in strict_predicted.values()
        )
    )
    per_role = {
        role: set(normalized.get(role, [])) == set(expected)
        for role, expected in reference_need_sets.items()
    }
    tp = fp = fn = distractor_leak = 0
    distractor_ids = {distractor_id} if distractor_id else set()
    for role, expected_list in reference_need_sets.items():
        expected = set(expected_list)
        predicted_set = set(normalized.get(role, []))
        extra = predicted_set - expected
        tp += len(predicted_set & expected)
        fp += len(extra)
        fn += len(expected - predicted_set)
        distractor_leak += len(extra & distractor_ids)
    overall_pass = (
        strict_error is None
        and strict_role_values_are_valid
        and set(strict_predicted.keys()) == set(reference_need_sets.keys())
        and all(per_role.values())
    )
    counts = {"tp": tp, "fp": fp, "fn": fn, "distractor_leak": distractor_leak}
    return {
        "pass": overall_pass,
        "metrics": metric_values(overall_pass, **counts),
        "counts": counts,
        "predicted": strict_predicted if strict_predicted is not None else boundary_predicted,
        "normalized": normalized,
        "per_role": per_role,
    }


def token_sequence(text: str) -> list[str]:
    pieces = _tokenizer().encode(text).tokens
    tokens: list[str] = []
    for piece in pieces:
        cleaned = piece.lstrip("Ġ")
        if cleaned and re.search(r"[a-zA-Z0-9]", cleaned):
            tokens.append(cleaned.lower())
    return tokens


def ngrams(tokens: list[str], orders: tuple[int, ...] = NGRAM_ORDERS) -> set[str]:
    out: set[str] = set()
    for n in orders:
        if n <= 0 or n > len(tokens):
            continue
        for i in range(len(tokens) - n + 1):
            out.add(" ".join(tokens[i:i + n]))
    return out


def distinctive_ngrams(items: dict[str, str]) -> dict[str, set[str]]:
    grams = {fragment_id: ngrams(token_sequence(text)) for fragment_id, text in items.items()}
    out: dict[str, set[str]] = {}
    for fragment_id, gram_set in grams.items():
        others = set().union(*(s for k, s in grams.items() if k != fragment_id))
        out[fragment_id] = gram_set - others
    return out


def split_role_sections(response: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    pattern = re.compile(r"^# (.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(response))
    for index, match in enumerate(matches):
        role = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(response)
        sections[role] = response[start:end].strip()
    return sections


def detect_fraction(distinctive: set[str], section_grams: set[str]) -> float:
    if not distinctive:
        return 0.0
    return len(distinctive & section_grams) / len(distinctive)


def score_prompt_writing(
    response: str | None,
    fragments: list[dict[str, Any]],
    reference_need_sets: dict[str, list[str]],
    distractor_id: str | None = None,
    include_threshold: float = 0.7,
    exclude_threshold: float = 0.3,
) -> dict[str, Any]:
    if response is None:
        response = ""
    sections = split_role_sections(response)
    info_items = {fragment["id"]: fragment["text"] for fragment in fragments}
    distinctive = distinctive_ngrams(info_items)
    role_name_tokens: set[str] = set()
    for role in reference_need_sets:
        role_name_tokens.update(token_sequence(role))

    def drop_role_only(grams: set[str]) -> set[str]:
        return {
            gram
            for gram in grams
            if not all(token in role_name_tokens for token in gram.split(" "))
        }

    distinctive = {fragment_id: drop_role_only(grams) for fragment_id, grams in distinctive.items()}
    per_role: dict[str, dict[str, Any]] = {}
    overall_pass = True
    distractor_ids = {distractor_id} if distractor_id else set()
    for role, expected_list in reference_need_sets.items():
        expected = set(expected_list)
        section_grams = ngrams(token_sequence(sections.get(role, "")))
        fractions = {
            fragment_id: round(detect_fraction(grams, section_grams), 3)
            for fragment_id, grams in distinctive.items()
        }
        detected = {
            fragment_id
            for fragment_id in expected
            if fractions.get(fragment_id, 0.0) >= include_threshold
        }
        extra = {
            fragment_id
            for fragment_id, fraction in fractions.items()
            if fraction >= exclude_threshold
        } - expected
        missing = expected - detected
        role_pass = not missing and not extra
        overall_pass = overall_pass and role_pass
        per_role[role] = {
            "pass": role_pass,
            "expected": sorted(expected),
            "detected": sorted(detected),
            "missing": sorted(missing),
            "extra": sorted(extra),
            "distractor_leak": sorted(extra & distractor_ids),
            "fractions": fractions,
        }
    tp = sum(len(role_result["detected"]) for role_result in per_role.values())
    fp = sum(len(role_result["extra"]) for role_result in per_role.values())
    fn = sum(len(role_result["missing"]) for role_result in per_role.values())
    distractor_leak = sum(len(role_result["distractor_leak"]) for role_result in per_role.values())
    counts = {"tp": tp, "fp": fp, "fn": fn, "distractor_leak": distractor_leak}
    return {
        "pass": overall_pass,
        "metrics": metric_values(overall_pass, **counts),
        "counts": counts,
        "sections_found": sorted(sections),
        "per_role": per_role,
    }


def score_prediction(evaluation: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"evaluation_id": evaluation["evaluation_id"]}
    if "role_assignment_response" in prediction:
        result["role_assignment"] = score_role_assignment(
            prediction["role_assignment_response"],
            evaluation["reference_need_sets"],
            evaluation.get("distractor_id"),
        )
    if "prompt_writing_response" in prediction:
        result["prompt_writing"] = score_prompt_writing(
            prediction["prompt_writing_response"],
            evaluation["fragments"],
            evaluation["reference_need_sets"],
            evaluation.get("distractor_id"),
        )
    return result


def summarize_task(rows: list[dict[str, Any]], task: str) -> dict[str, Any] | None:
    task_rows = [row[task] for row in rows if task in row]
    if not task_rows:
        return None
    n = len(task_rows)
    strict_passes = sum(1 for row in task_rows if row.get("pass"))
    tp = sum(row["counts"]["tp"] for row in task_rows)
    fp = sum(row["counts"]["fp"] for row in task_rows)
    fn = sum(row["counts"]["fn"] for row in task_rows)
    distractor_leak = sum(row["counts"]["distractor_leak"] for row in task_rows)
    return {
        "evaluations": n,
        "strict_pass_count": strict_passes,
        "metrics": {
            "strict_pass": strict_passes / n,
            "net_match_score": sum(row["metrics"]["net_match_score"] for row in task_rows) / n,
            "required_coverage": tp / (tp + fn) if tp + fn else 0.0,
            "boundary_precision": tp / (tp + fp) if tp + fp else 0.0,
            "distractor_leakage": distractor_leak / n,
        },
        "counts": {"tp": tp, "fp": fp, "fn": fn, "distractor_leak": distractor_leak},
    }


def summarize_scores(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for task in ("role_assignment", "prompt_writing"):
        task_summary = summarize_task(rows, task)
        if task_summary is not None:
            summary[task] = task_summary
    return summary


def format_metric_summary(summary: dict[str, Any]) -> str:
    task_labels = {
        "role_assignment": "role-fragment assignment",
        "prompt_writing": "free-form prompt writing",
    }
    lines: list[str] = []
    for task in ("role_assignment", "prompt_writing"):
        if task not in summary:
            continue
        task_summary = summary[task]
        metrics = task_summary["metrics"]
        lines.append(f"{task_labels[task]} ({task_summary['evaluations']} evaluations)")
        lines.append(f"  strict_pass: {metrics['strict_pass']:.4f} ({task_summary['strict_pass_count']}/{task_summary['evaluations']})")
        for name in METRIC_NAMES[1:]:
            lines.append(f"  {name}: {metrics[name]:.4f}")
    return "\n".join(lines)
