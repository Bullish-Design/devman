#!/usr/bin/env uv run
"""Text in on stdin, text out on stdout — the same contract `claude -p
--output-format text` gives `agent:review` and `gitman:commit-message`
(devenv.nix), swapped to a local GPU model over pydantic-ai.

Points at an OpenAI-compatible server (llgym's shim over the `inferference`
llama.cpp fork by default: `llgym serve`, README.md "Phase-1 usage"). devman
does not start or own that server (`processes.dagu`'s note in devenv.nix is
the same call for Dagu itself) — this script only calls it, and fails plainly
if nothing answers.

    GPU_LLM_BASE_URL   default http://127.0.0.1:8000/v1
    GPU_LLM_MODEL       required — no default model is guessed

    echo "..." | uv run --script scripts/gpu_complete.py
"""
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pydantic-ai-slim[openai]",
# ]
# ///

from __future__ import annotations

import os
import sys

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider


def main() -> int:
    base_url = os.environ.get("GPU_LLM_BASE_URL", "http://127.0.0.1:8000/v1")
    model_name = os.environ.get("GPU_LLM_MODEL")
    if not model_name:
        print(
            "gpu_complete: GPU_LLM_MODEL is unset — name the model llgym loaded",
            file=sys.stderr,
        )
        return 2

    prompt = sys.stdin.read()
    if not prompt.strip():
        print("gpu_complete: empty stdin — nothing to send", file=sys.stderr)
        return 2

    # api_key is required by the OpenAI client shape but unchecked by llgym's
    # shim; any non-empty string satisfies it.
    model = OpenAIModel(
        model_name, provider=OpenAIProvider(base_url=base_url, api_key="local")
    )
    agent = Agent(model)

    try:
        result = agent.run_sync(prompt)
    except Exception as exc:  # the server being down is the expected failure here
        print(
            f"gpu_complete: {base_url} did not answer — is `llgym serve` running? ({exc})",
            file=sys.stderr,
        )
        return 1

    print(result.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
