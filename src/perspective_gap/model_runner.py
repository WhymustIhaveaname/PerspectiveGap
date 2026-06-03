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
TASK_EVALUATION_ID_MARKER = "__task_"

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


def parse_scenario_ids(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [part.strip() for value in values for part in value.split(",") if part.strip()]


def scenario_paths(scenarios_dir: Path, scenario_ids: list[str] | None) -> list[Path]:
    scenario_ids = parse_scenario_ids(scenario_ids)
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
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        retries: int,
        token_limit_parameter: str,
    ):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.retries = retries
        self.token_limit_parameter = token_limit_parameter

    def _completion_kwargs(self, prompt: str, max_output_tokens: int, token_limit_parameter: str) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            token_limit_parameter: max_output_tokens,
        }

    def _alternate_token_limit_parameter(self) -> str:
        if self.token_limit_parameter == "max_completion_tokens":
            return "max_tokens"
        return "max_completion_tokens"

    @staticmethod
    def _looks_like_unsupported_token_limit_parameter(error: Exception) -> bool:
        message = str(error).lower()
        return (
            ("max_tokens" in message or "max_completion_tokens" in message)
            and ("unsupported" in message or "not supported" in message or "unrecognized" in message)
        )

    def generate(self, prompt: str, max_output_tokens: int) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                kwargs = self._completion_kwargs(prompt, max_output_tokens, self.token_limit_parameter)
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                return content or ""
            except Exception as error:  # noqa: BLE001 - retry API/transient errors and re-raise last.
                if self._looks_like_unsupported_token_limit_parameter(error):
                    try:
                        alternate_parameter = self._alternate_token_limit_parameter()
                        kwargs = self._completion_kwargs(
                            prompt,
                            max_output_tokens,
                            alternate_parameter,
                        )
                        response = self.client.chat.completions.create(**kwargs)
                        self.token_limit_parameter = alternate_parameter
                        content = response.choices[0].message.content
                        return content or ""
                    except Exception as fallback_error:  # noqa: BLE001 - retry and re-raise last.
                        last_error = fallback_error
                        if attempt == self.retries:
                            break
                        retry_sleep(attempt)
                        continue
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


def task_evaluation_id(base_evaluation_id: str, task: str) -> str:
    return f"{base_evaluation_id}{TASK_EVALUATION_ID_MARKER}{task}"


def completed_requests(path: Path) -> set[tuple[str, str]]:
    completed: set[tuple[str, str]] = set()
    if not path.exists():
        return completed
    for row in load_jsonl(path):
        model = row.get("model", "")
        row_task = row.get("task")
        if isinstance(row_task, str) and row.get("response") is not None:
            completed.add((row["evaluation_id"], model))
        if "role_assignment_response" in row:
            completed.add((task_evaluation_id(row["evaluation_id"], "role_assignment"), model))
        if "prompt_writing_response" in row:
            completed.add((task_evaluation_id(row["evaluation_id"], "prompt_writing"), model))
    return completed


def base_prediction(evaluation: dict, args: argparse.Namespace, task: str) -> dict:
    request_evaluation_id = task_evaluation_id(evaluation["evaluation_id"], task)
    return {
        "evaluation_id": request_evaluation_id,
        "base_evaluation_id": evaluation["evaluation_id"],
        "scenario_id": evaluation["scenario_id"],
        "shuffle_seed": evaluation["shuffle_seed"],
        "task": task,
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
            token_limit_parameter="max_completion_tokens",
        )
    if args.provider in OPENAI_COMPATIBLE_PROVIDERS:
        base_url = get_base_url(args.provider, args.base_url)
        assert base_url is not None
        return OpenAICompatibleChatClient(
            model=args.model,
            api_key=api_key,
            base_url=base_url,
            retries=API_RETRIES,
            token_limit_parameter="max_tokens",
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
    completed = completed_requests(args.out)
    total_requests = len(evaluations) * len(tasks)
    needed_request_ids = [
        task_evaluation_id(evaluation["evaluation_id"], task)
        for evaluation in evaluations
        for task in tasks
    ]

    client = build_client(args)
    print(f"provider={args.provider}")
    print(f"model={args.model}")
    print(f"evaluations={total_requests}")
    print(f"tasks={','.join(tasks)}")
    print(f"completed_responses={sum((request_id, args.model) in completed for request_id in needed_request_ids)}")

    request_index = 0
    for evaluation in evaluations:
        if "role_assignment" in tasks:
            request_index += 1
            request_id = task_evaluation_id(evaluation["evaluation_id"], "role_assignment")
            request_key = (request_id, args.model)
            if request_key in completed:
                print(f"[{request_index}/{total_requests}] skip {request_id}", flush=True)
            else:
                print(f"[{request_index}/{total_requests}] role_assignment {request_id}", flush=True)
                prediction = base_prediction(evaluation, args, "role_assignment")
                prediction["response"] = client.generate(
                    evaluation["role_assignment_prompt"],
                    MAX_OUTPUT_TOKENS,
                )
                append_jsonl(args.out, prediction)
                completed.add(request_key)
                print(f"[{request_index}/{total_requests}] wrote role_assignment {request_id}", flush=True)
        if "prompt_writing" in tasks:
            request_index += 1
            request_id = task_evaluation_id(evaluation["evaluation_id"], "prompt_writing")
            request_key = (request_id, args.model)
            if request_key in completed:
                print(f"[{request_index}/{total_requests}] skip {request_id}", flush=True)
            else:
                print(f"[{request_index}/{total_requests}] prompt_writing {request_id}", flush=True)
                prediction = base_prediction(evaluation, args, "prompt_writing")
                prediction["response"] = client.generate(
                    evaluation["prompt_writing_prompt"],
                    MAX_OUTPUT_TOKENS,
                )
                append_jsonl(args.out, prediction)
                completed.add(request_key)
                print(f"[{request_index}/{total_requests}] wrote prompt_writing {request_id}", flush=True)


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
