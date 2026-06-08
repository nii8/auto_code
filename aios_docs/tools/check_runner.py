#!/usr/bin/env python3
"""Basic deterministic checks for AIOS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config_loader import load_config


def check_paths(config: dict) -> dict:
    source_code_dir = config.get("source_code_dir", "")
    source_material_file = config.get("source_material_file", "")
    checks = []
    for name, value in [
        ("source_code_dir", source_code_dir),
        ("source_material_file", source_material_file),
    ]:
        if not value:
            checks.append({"name": name, "status": "fail", "evidence": "empty"})
            continue
        path = Path(value).expanduser()
        checks.append({
            "name": name,
            "status": "pass" if path.exists() else "fail",
            "path": str(path),
            "evidence": "exists" if path.exists() else "not found",
        })
    return {"checker": "paths", "checks": checks, "passed": all(c["status"] == "pass" for c in checks)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AIOS checks")
    parser.add_argument("--config", default=None)
    parser.add_argument("--out")
    parser.add_argument("check", choices=["paths"])
    args = parser.parse_args()

    config = load_config(args.config) if args.config else load_config()
    if args.check == "paths":
        result = check_paths(config)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
