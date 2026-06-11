#!/usr/bin/env python3
"""Shared path helpers for AIOS tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STATE = {
    "phase": "BOOTSTRAP",
    "status": "initialized",
    "iteration": 0,
    "history": [],
}


def source_dir(config: dict[str, Any]) -> Path:
    raw = config.get("target_source_dir") or config.get("source_code_dir")
    if not raw:
        raise RuntimeError("target_source_dir/source_code_dir is empty in aios_config.yaml or aios_config.local.yaml")
    return Path(str(raw)).expanduser().resolve()


def reference_source_dirs(config: dict[str, Any]) -> list[Path]:
    raw_dirs = config.get("reference_source_dirs") or []
    if isinstance(raw_dirs, str):
        raw_dirs = [raw_dirs]
    return [Path(str(item)).expanduser().resolve() for item in raw_dirs if str(item).strip()]


def aios_dir(config: dict[str, Any]) -> Path:
    return source_dir(config) / ".aios"


def validate_initiative_id(value: str) -> str:
    if not value:
        return ""
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "/" in value or "\\" in value:
        raise RuntimeError("active_initiative must be a directory name, not a path")
    return value


def active_initiative_id(config: dict[str, Any]) -> str:
    configured = str(config.get("active_initiative") or "").strip()
    if configured:
        return validate_initiative_id(configured)
    global_state_path = aios_dir(config) / "global_state.json"
    if not global_state_path.exists():
        return ""
    try:
        state = json.loads(global_state_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return validate_initiative_id(str(state.get("active_initiative") or "").strip())


def active_workspace_dir(config: dict[str, Any]) -> Path:
    initiative_id = active_initiative_id(config)
    if initiative_id:
        return aios_dir(config) / "initiatives" / initiative_id
    return aios_dir(config)


def state_path(config: dict[str, Any]) -> Path:
    return active_workspace_dir(config) / "state.json"


def task_graph_path(config: dict[str, Any]) -> Path:
    return active_workspace_dir(config) / "tasks" / "task_graph.json"


def runs_dir(config: dict[str, Any]) -> Path:
    path = active_workspace_dir(config) / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def reports_dir(config: dict[str, Any]) -> Path:
    path = active_workspace_dir(config) / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_reference_dirs_readonly_boundary(config: dict[str, Any]) -> None:
    target = source_dir(config)
    for reference in reference_source_dirs(config):
        try:
            reference.relative_to(target)
        except ValueError:
            pass
        else:
            raise RuntimeError(f"reference_source_dir is inside target_source_dir and cannot be treated as read-only: {reference}")
        try:
            target.relative_to(reference)
        except ValueError:
            pass
        else:
            raise RuntimeError(f"target_source_dir is inside reference_source_dir; this breaks rebuild write boundaries: {reference}")
