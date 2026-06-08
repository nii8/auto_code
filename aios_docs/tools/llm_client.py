#!/usr/bin/env python3
"""OpenAI-compatible LLM client for AIOS."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from config_loader import load_config


def call_llm(prompt: str, config: dict[str, Any], system: str | None = None) -> str:
    llm_config = config.get("llm", {})
    base_url = str(llm_config.get("base_url", "")).rstrip("/")
    model = llm_config.get("model", "qwen3.6-plus")
    api_key_env = llm_config.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.environ.get(api_key_env)
    temperature = llm_config.get("temperature", 0.2)
    timeout = int(llm_config.get("timeout_seconds", 300))

    if not base_url:
        raise RuntimeError("llm.base_url is empty in aios_config.yaml")
    if not api_key:
        raise RuntimeError(f"Environment variable {api_key_env} is not set")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP error {exc.code}: {detail}") from exc

    return payload["choices"][0]["message"]["content"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Call configured LLM")
    parser.add_argument("--config", default=None, help="Path to aios_config.yaml")
    parser.add_argument("--prompt-file", help="Read prompt from file")
    parser.add_argument("--system-file", help="Read system prompt from file")
    parser.add_argument("--out", help="Write response to file")
    parser.add_argument("prompt", nargs="?", help="Prompt text. If omitted, stdin is used.")
    args = parser.parse_args()

    config = load_config(args.config) if args.config else load_config()
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    elif args.prompt:
        prompt = args.prompt
    else:
        prompt = sys.stdin.read()

    system = None
    if args.system_file:
        system = Path(args.system_file).read_text(encoding="utf-8")

    response = call_llm(prompt, config, system=system)
    if args.out:
        Path(args.out).write_text(response, encoding="utf-8")
    else:
        print(response)


if __name__ == "__main__":
    main()
