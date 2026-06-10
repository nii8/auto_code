#!/usr/bin/env python3
"""Load AIOS YAML configuration with minimal dependencies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "aios_config.yaml"
LOCAL_CONFIG_SUFFIX = ".local"


def _simple_yaml_load(text: str) -> dict[str, Any]:
    """Very small fallback parser for this template's simple YAML shape."""
    result: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, result)]

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
            continue

        if value.startswith('"') and value.endswith('"'):
            parsed: Any = value[1:-1]
        elif value in {"true", "false"}:
            parsed = value == "true"
        else:
            try:
                parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
        parent[key] = parsed

    return result


def _yaml_load_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return _simple_yaml_load(text)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def local_config_path(config_path: Path) -> Path:
    return config_path.with_name(f"{config_path.stem}{LOCAL_CONFIG_SUFFIX}{config_path.suffix}")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config_path = Path(path).expanduser().resolve()
    data = _yaml_load_file(config_path)
    local_path = local_config_path(config_path)
    if local_path.exists():
        data = _deep_merge(data, _yaml_load_file(local_path))
        data["_local_config_path"] = str(local_path)
    data["_config_path"] = str(config_path)
    return data


def main() -> None:
    print(json.dumps(load_config(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
