#!/usr/bin/env python3
"""Run Codex CLI from AIOS."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from config_loader import load_config


def run_codex(prompt: str, cwd: str | Path, config: dict[str, Any]) -> dict[str, Any]:
    codex_config = config.get("codex", {})
    command = codex_config.get("command", "codex")
    default_args = codex_config.get("default_args", ["exec", "--json", "--sandbox", "workspace-write"])
    timeout = int(codex_config.get("timeout_seconds", 3600))
    cmd = [command, *default_args, "--cd", str(Path(cwd).expanduser().resolve()), prompt]

    completed = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "command": cmd,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Codex CLI")
    parser.add_argument("--config", default=None, help="Path to aios_config.yaml")
    parser.add_argument("--cwd", help="Codex working directory. Defaults to target_source_dir/source_code_dir")
    parser.add_argument("--prompt-file", help="Read prompt from file")
    parser.add_argument("--out", help="Write JSON result to file")
    parser.add_argument("prompt", nargs="?", help="Prompt text. If omitted, stdin is used.")
    args = parser.parse_args()

    config = load_config(args.config) if args.config else load_config()
    cwd = args.cwd or config.get("target_source_dir") or config.get("source_code_dir")
    if not cwd:
        raise SystemExit("target_source_dir/source_code_dir is empty; pass --cwd or fill aios_config.local.yaml")

    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    elif args.prompt:
        prompt = args.prompt
    else:
        prompt = sys.stdin.read()

    result = run_codex(prompt, cwd, config)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
