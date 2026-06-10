#!/usr/bin/env python3
"""Manage AIOS state.json."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from config_loader import load_config


DEFAULT_STATE = {
    "phase": "BOOTSTRAP",
    "status": "initialized",
    "iteration": 0,
    "history": [],
}


def aios_dir(config: dict) -> Path:
    source_code_dir = config.get("target_source_dir") or config.get("source_code_dir")
    if not source_code_dir:
        raise RuntimeError("target_source_dir/source_code_dir is empty in aios_config.yaml or aios_config.local.yaml")
    return Path(source_code_dir).expanduser().resolve() / ".aios"


def state_path(config: dict) -> Path:
    return aios_dir(config) / "state.json"


def load_state(config: dict) -> dict:
    path = state_path(config)
    if not path.exists():
        return dict(DEFAULT_STATE)
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(config: dict, state: dict) -> Path:
    path = state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def set_phase(config: dict, phase: str, status: str | None = None) -> Path:
    state = load_state(config)
    state["phase"] = phase
    if status is not None:
        state["status"] = status
    state.setdefault("history", []).append({
        "time": datetime.now().isoformat(timespec="seconds"),
        "phase": phase,
        "status": state.get("status"),
    })
    return save_state(config, state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage AIOS state")
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    show = sub.add_parser("show")
    setp = sub.add_parser("set-phase")
    setp.add_argument("phase")
    setp.add_argument("--status")
    args = parser.parse_args()

    config = load_config(args.config) if args.config else load_config()
    if args.cmd == "init":
        path = save_state(config, dict(DEFAULT_STATE))
        print(path)
    elif args.cmd == "show":
        print(json.dumps(load_state(config), ensure_ascii=False, indent=2))
    elif args.cmd == "set-phase":
        print(set_phase(config, args.phase, args.status))


if __name__ == "__main__":
    main()
