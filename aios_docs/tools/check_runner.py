#!/usr/bin/env python3
"""Basic deterministic checks for AIOS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config_loader import load_config


def check_paths(config: dict) -> dict:
    project_mode = str(config.get("project_mode") or "").strip()
    source_code_dir = config.get("target_source_dir") or config.get("source_code_dir", "")
    source_material_file = config.get("source_material_file", "")
    reference_source_dirs = config.get("reference_source_dirs") or []
    checks = []
    checks.append({
        "name": "project_mode",
        "status": "pass" if project_mode in {"greenfield", "brownfield", "rebuild"} else "fail",
        "value": project_mode,
        "evidence": "valid" if project_mode in {"greenfield", "brownfield", "rebuild"} else "empty or invalid",
    })
    for name, value in [
        ("target_source_dir/source_code_dir", source_code_dir),
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
    if project_mode == "rebuild":
        refs = reference_source_dirs if isinstance(reference_source_dirs, list) else [reference_source_dirs]
        valid_refs = [Path(str(item)).expanduser() for item in refs if str(item).strip()]
        checks.append({
            "name": "reference_source_dirs",
            "status": "pass" if valid_refs and all(path.exists() for path in valid_refs) else "fail",
            "paths": [str(path) for path in valid_refs],
            "evidence": "exists" if valid_refs and all(path.exists() for path in valid_refs) else "empty or not found",
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
