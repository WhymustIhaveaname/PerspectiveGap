from __future__ import annotations

import json
import re
from typing import Any

from tokenizers import Tokenizer

_TOKENIZER: Tokenizer | None = None
_TOKENIZER_NAME = "Qwen/Qwen3.5-0.8B"
NGRAM_ORDERS = (1, 2, 3)


def _tokenizer() -> Tokenizer:
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = Tokenizer.from_pretrained(_TOKENIZER_NAME)
    return _TOKENIZER


def parse_json_response(text: str) -> Any:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n(.*?)\n```\s*$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def score_role_assignment(response_text: str, reference_need_sets: dict[str, list[str]]) -> dict[str, Any]:
    try:
        predicted = parse_json_response(response_text)
    except (json.JSONDecodeError, ValueError) as error:
        return {
            "pass": False,
            "predicted": None,
            "per_role": {},
            "error": f"parse: {error}",
        }
    if not isinstance(predicted, dict):
        return {
            "pass": False,
            "predicted": predicted,
            "per_role": {},
            "error": "response is not a JSON object",
        }
    normalized = {
        role: sorted(set(fragment_ids))
        for role, fragment_ids in predicted.items()
        if isinstance(fragment_ids, list)
    }
    per_role = {
        role: set(normalized.get(role, [])) == set(expected)
        for role, expected in reference_need_sets.items()
    }
    return {
        "pass": set(predicted.keys()) == set(reference_need_sets.keys()) and all(per_role.values()),
        "predicted": predicted,
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
    response: str,
    fragments: list[dict[str, Any]],
    reference_need_sets: dict[str, list[str]],
    distractor_id: str | None = None,
    include_threshold: float = 0.7,
    exclude_threshold: float = 0.3,
) -> dict[str, Any]:
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
    return {
        "pass": overall_pass,
        "sections_found": sorted(sections),
        "per_role": per_role,
    }


def score_prediction(evaluation: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"evaluation_id": evaluation["evaluation_id"]}
    if "role_assignment_response" in prediction:
        result["role_assignment"] = score_role_assignment(
            prediction["role_assignment_response"],
            evaluation["reference_need_sets"],
        )
    if "prompt_writing_response" in prediction:
        result["prompt_writing"] = score_prompt_writing(
            prediction["prompt_writing_response"],
            evaluation["fragments"],
            evaluation["reference_need_sets"],
            evaluation.get("distractor_id"),
        )
    return result
