from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Protocol

from .renderer import iter_scenario_paths, render_evaluation

TASKS = {"role_assignment", "prompt_writing"}
OPENAI_COMPATIBLE_PROVIDERS = {"deepseek", "kimi", "nvidia", "openrouter", "openai-compatible"}
MAX_OUTPUT_TOKENS = 16000
API_RETRIES = 8

PROVIDER_API_KEY_ENVS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "kimi": "KIMI_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

PROVIDER_BASE_URLS = {
    "openai": "https://us.api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "kimi": "https://api.moonshot.cn/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = ROOT / "data" / "scenarios"
DISTRACTORS_DIR = ROOT / "data" / "distractors"


class TextClient(Protocol):
    def generate(self, prompt: str, max_output_tokens: int) -> str:
        ...


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def parse_tasks(text: str) -> list[str]:
    if text == "both":
        return ["role_assignment", "prompt_writing"]
    tasks = [part.strip() for part in text.split(",") if part.strip()]
    unknown = sorted(set(tasks) - TASKS)
    if unknown:
        raise ValueError(f"unknown task(s): {', '.join(unknown)}")
    if not tasks:
        raise ValueError("at least one task must be selected")
    return tasks


def scenario_paths(scenarios_dir: Path, scenario_ids: list[str] | None) -> list[Path]:
    if not scenario_ids:
        return iter_scenario_paths(scenarios_dir)
    paths = []
    for scenario_id in scenario_ids:
        path = scenarios_dir / f"{scenario_id}.md"
        if not path.exists():
            raise SystemExit(f"unknown scenario_id: {scenario_id}")
        paths.append(path)
    return paths


def dynamic_evaluations(
    scenarios_dir: Path,
    distractors_dir: Path,
    scenario_ids: list[str] | None,
    shuffle_seeds: list[int] | None,
) -> list[dict]:
    seeds = shuffle_seeds or [42]
    rows = []
    for scenario_path in scenario_paths(scenarios_dir, scenario_ids):
        for seed in seeds:
            rows.append(render_evaluation(scenario_path, seed, distractors_dir))
    return rows


def get_api_key(provider: str, api_key_env: str | None) -> str:
    env_name = api_key_env or PROVIDER_API_KEY_ENVS.get(provider)
    if provider == "openai-compatible" and env_name is None:
        raise SystemExit("--api-key-env is required for provider=openai-compatible")
    if env_name is None:
        raise SystemExit(f"unsupported provider: {provider}")
    api_key = os.environ.get(env_name)
    if not api_key:
        raise SystemExit(f"{env_name} is not set")
    return api_key


def get_base_url(provider: str, base_url: str | None) -> str | None:
    if base_url:
        return base_url
    if provider == "openai":
        return os.environ.get("OPENAI_BASE_URL") or PROVIDER_BASE_URLS["openai"]
    if provider == "openai-compatible":
        raise SystemExit("--base-url is required for provider=openai-compatible")
    return PROVIDER_BASE_URLS.get(provider)


def retry_sleep(attempt: int) -> None:
    time.sleep(min(4 * (2 ** attempt), 90))


class OpenAICompatibleChatClient:
    def __init__(self, model: str, api_key: str, base_url: str, retries: int):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.retries = retries

    def generate(self, prompt: str, max_output_tokens: int) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                )
                content = response.choices[0].message.content
                return content or ""
            except Exception as error:  # noqa: BLE001 - retry API/transient errors and re-raise last.
                last_error = error
                if attempt == self.retries:
                    break
                retry_sleep(attempt)
        raise RuntimeError(f"OpenAI-compatible call failed after {self.retries + 1} attempts: {last_error}")


class AnthropicMessagesClient:
    def __init__(self, model: str, api_key: str, retries: int):
        from anthropic import Anthropic

        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.retries = retries

    def generate(self, prompt: str, max_output_tokens: int) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_output_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                chunks = []
                for block in response.content:
                    text = getattr(block, "text", None)
                    if text:
                        chunks.append(text)
                return "".join(chunks)
            except Exception as error:  # noqa: BLE001 - retry API/transient errors and re-raise last.
                last_error = error
                if attempt == self.retries:
                    break
                retry_sleep(attempt)
        raise RuntimeError(f"Anthropic call failed after {self.retries + 1} attempts: {last_error}")


def completed_tasks(path: Path) -> dict[str, set[str]]:
    completed: dict[str, set[str]] = {}
    if not path.exists():
        return completed
    for row in load_jsonl(path):
        evaluation_id = row["evaluation_id"]
        tasks = completed.setdefault(evaluation_id, set())
        if "role_assignment_response" in row:
            tasks.add("role_assignment")
        if "prompt_writing_response" in row:
            tasks.add("prompt_writing")
    return completed


def base_prediction(evaluation: dict, args: argparse.Namespace) -> dict:
    return {
        "evaluation_id": evaluation["evaluation_id"],
        "scenario_id": evaluation["scenario_id"],
        "shuffle_seed": evaluation["shuffle_seed"],
        "model": args.model,
        "provider": args.provider,
    }


def build_client(args: argparse.Namespace) -> TextClient:
    api_key = get_api_key(args.provider, args.api_key_env)
    if args.provider == "openai":
        base_url = get_base_url(args.provider, args.base_url)
        assert base_url is not None
        return OpenAICompatibleChatClient(
            model=args.model,
            api_key=api_key,
            base_url=base_url,
            retries=API_RETRIES,
        )
    if args.provider in OPENAI_COMPATIBLE_PROVIDERS:
        base_url = get_base_url(args.provider, args.base_url)
        assert base_url is not None
        return OpenAICompatibleChatClient(
            model=args.model,
            api_key=api_key,
            base_url=base_url,
            retries=API_RETRIES,
        )
    if args.provider == "anthropic":
        return AnthropicMessagesClient(model=args.model, api_key=api_key, retries=API_RETRIES)
    raise SystemExit(f"unsupported provider: {args.provider}")


def run_predictions(args: argparse.Namespace) -> None:
    tasks = parse_tasks(args.tasks)
    evaluations = dynamic_evaluations(
        SCENARIOS_DIR,
        DISTRACTORS_DIR,
        args.scenario_id,
        args.shuffle_seed,
    )
    completed = completed_tasks(args.out)

    client = build_client(args)
    print(f"provider={args.provider}")
    print(f"model={args.model}")
    print(f"evaluations={len(evaluations)}")
    print(f"tasks={','.join(tasks)}")
    print(f"completed_responses={sum(len(done) for done in completed.values())}")

    for index, evaluation in enumerate(evaluations, start=1):
        evaluation_id = evaluation["evaluation_id"]
        done = completed.setdefault(evaluation_id, set())
        if all(task in done for task in tasks):
            print(f"[{index}/{len(evaluations)}] skip {evaluation_id}", flush=True)
            continue

        if "role_assignment" in tasks and "role_assignment" not in done:
            print(f"[{index}/{len(evaluations)}] role_assignment {evaluation_id}", flush=True)
            prediction = base_prediction(evaluation, args)
            prediction["role_assignment_response"] = client.generate(
                evaluation["role_assignment_prompt"],
                MAX_OUTPUT_TOKENS,
            )
            append_jsonl(args.out, prediction)
            done.add("role_assignment")
            print(f"[{index}/{len(evaluations)}] wrote role_assignment {evaluation_id}", flush=True)
        if "prompt_writing" in tasks and "prompt_writing" not in done:
            print(f"[{index}/{len(evaluations)}] prompt_writing {evaluation_id}", flush=True)
            prediction = base_prediction(evaluation, args)
            prediction["prompt_writing_response"] = client.generate(
                evaluation["prompt_writing_prompt"],
                MAX_OUTPUT_TOKENS,
            )
            append_jsonl(args.out, prediction)
            done.add("prompt_writing")
            print(f"[{index}/{len(evaluations)}] wrote prompt_writing {evaluation_id}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a model on PerspectiveGap evaluations.")
    parser.add_argument("--provider", required=True, choices=sorted({"anthropic", "openai"} | OPENAI_COMPATIBLE_PROVIDERS))
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tasks", default="both")
    parser.add_argument("--shuffle-seed", action="append", type=int, default=[])
    parser.add_argument("--scenario-id", action="append", default=[])
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default=None)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_predictions(args)
