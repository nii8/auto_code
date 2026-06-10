#!/usr/bin/env python3
"""Friendly interactive AIOS command wrapper."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "aios_docs" / "tools" / "aios_runner.py"
sys.path.insert(0, str(ROOT / "aios_docs" / "tools"))
from config_loader import load_config

TERMINAL_DONE = {"done"}
WAITING = {"pending"}
BLOCKING = {"failed", "blocked", "needs_human"}
RESETTABLE_PATHS = ["app.py", "templates", "static", "jobs", ".codex", "__pycache__"]


class AiosExit(Exception):
    pass


def call_runner(args: list[str], capture: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(RUNNER), *args]
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=capture)


def runner_json(args: list[str]) -> tuple[int, dict[str, Any] | None, str]:
    completed = call_runner(args, capture=True)
    text = completed.stdout.strip()
    if not text:
        return completed.returncode, None, completed.stderr.strip()
    try:
        return completed.returncode, json.loads(text), completed.stderr.strip()
    except json.JSONDecodeError:
        extra = "\n" + completed.stderr.strip() if completed.stderr.strip() else ""
        return completed.returncode, None, text + extra


def task_map(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(task.get("task_id")): task for task in tasks}


def next_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_id = task_map(tasks)
    for task in tasks:
        if task.get("status", "pending") not in WAITING:
            continue
        deps = task.get("dependencies", [])
        if all(by_id.get(str(dep), {}).get("status") == "done" for dep in deps):
            return task
    return None


def get_status_data() -> dict[str, Any] | None:
    _, data, _ = runner_json(["status"])
    return data


def load_aios_config() -> dict[str, Any]:
    return load_config(ROOT / "aios_docs" / "aios_config.yaml")


def missing_config_fields() -> list[str]:
    config = load_aios_config()
    missing = []
    for key in ["source_code_dir", "source_material_file"]:
        if not str(config.get(key, "")).strip():
            missing.append(key)
    return missing


def print_setup_help(raw: str | None = None) -> None:
    missing = missing_config_fields()
    print("\n⚙️ AIOS 还没有绑定本机项目。")
    if missing:
        print(f"- 缺少配置：{', '.join(missing)}")
    print("- 不需要修改可提交的 `aios_docs/aios_config.yaml`。")
    print("- 请在对话里告诉 Codex：源码目录在哪里、原始材料/聊天记录在哪里。")
    print("- Codex 会把真实路径写入 `aios_docs/aios_config.local.yaml`，该文件不会提交 Git。")
    print("- 也可以参考 `aios_docs/aios_config.local.example.yaml` 手动创建本地配置。")
    if raw and "Traceback" not in raw:
        print(f"- 底层信息：{raw.splitlines()[0] if raw.splitlines() else raw}")


def ensure_project_configured() -> bool:
    if not missing_config_fields():
        return True
    print_setup_help()
    return False


def resolve_command(raw: str | None) -> str:
    if not raw:
        return "run"
    text = raw.strip().lower()
    if text in {"q", "quit", "exit", "退出", "结束", "拜拜"}:
        return "exit"
    if text in {"run", "continue"}:
        return "run"
    if text in {"help", "帮助", "?", "？"}:
        return "help"
    if text in {"check", "检查", "校验", "检查任务图"}:
        return "check"
    if text in {"doctor", "诊断", "环境", "环境检查", "检查环境"}:
        return "doctor"
    if text in {"status", "状态", "进度", "看看", "到哪了", "现在到哪了"}:
        return "status"
    if text in {"preview", "预览", "看看下一步", "下一步做什么"}:
        return "preview"
    if text in {"next", "step", "单步", "执行一步", "只跑一步"}:
        return "next"
    if text in {"reset", "重置", "清理", "从头来", "重新跑", "重新开始"}:
        return "reset"
    if any(word in text for word in ["为什么", "什么问题", "原因", "咋了", "怎么了", "哪里错", "啥问题"]):
        return "explain"
    if any(word in text for word in ["继续", "跑", "开始", "执行", "重试", "修复", "好了", "可以了", "go"]):
        return "run"
    return "note"


def source_root_from_config() -> Path:
    config = load_aios_config()
    value = str(config.get("source_code_dir", "")).strip()
    if value:
        return Path(value).expanduser().resolve()
    raise RuntimeError("aios_config.yaml / aios_config.local.yaml 里没有 source_code_dir")


def append_user_note(text: str) -> Path:
    source_root = source_root_from_config()
    notes_path = source_root / ".aios" / "runs" / "user_notes.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    with notes_path.open("a", encoding="utf-8") as file:
        file.write(f"\n## 用户输入\n\n{text.strip()}\n")
    return notes_path


def missing_runtime_modules() -> list[str]:
    required = {"flask": "flask", "Pillow": "PIL"}
    missing = []
    for package_name, module_name in required.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    return missing


def print_environment_hint() -> None:
    missing = missing_runtime_modules()
    if not missing:
        return
    print("\n🔧 当前运行环境可能还没准备好：")
    print(f"- 缺少 Python 包：{', '.join(missing)}")
    print("- 可在项目环境里安装后再继续，例如：`python3 -m pip install flask Pillow`")


def ensure_runtime_dependencies(auto_install: bool = True) -> bool:
    missing = missing_runtime_modules()
    if not missing:
        return True
    print("\n🔧 AIOS 运行前依赖预检")
    print(f"- 缺少低风险 Python 包：{', '.join(missing)}")
    if not auto_install:
        print("- 当前命令只诊断，不自动安装。")
        return False
    print("- AIOS 将自动安装这些依赖，然后继续执行。")
    cmd = [sys.executable, "-m", "pip", "install", *missing]
    completed = subprocess.run(cmd, cwd=ROOT, text=True)
    if completed.returncode != 0:
        print("❌ 依赖自动安装失败，AIOS 暂停。")
        return False
    still_missing = missing_runtime_modules()
    if still_missing:
        print(f"❌ 安装后仍缺少：{', '.join(still_missing)}")
        return False
    print("✅ 依赖已就绪。")
    return True


def print_help() -> None:
    print("\nAIOS 交互命令：")
    print("  回车 / run / continue  自动推进，直到完成或需要确认")
    print("  status                查看进度")
    print("  preview               看下一步，不改代码")
    print("  next                  只执行一个任务")
    print("  check                 检查任务图")
    print("  doctor                检查本地运行环境")
    print("  reset                 清掉业务代码和运行日志，从任务图重跑")
    print("  exit                  离开 AIOS")
    print("  其他自然语言           记录为用户备注，然后你可以输入 run")
    print("\n中文别名仍可用：继续、状态、预览、单步、检查、诊断、重置、退出。")


def cmd_doctor() -> int:
    print("\n🩺 AIOS 环境诊断")
    source_root = source_root_from_config()
    print(f"- 源码目录：{source_root}")
    print(f"- Python：{sys.executable}")
    missing = missing_runtime_modules()
    if missing:
        print(f"- 缺少依赖：{', '.join(missing)}")
        print("- 建议先运行：`python3 -m pip install flask Pillow`")
        return 1
    print("- Flask / Pillow：已可导入")
    print("- 环境看起来可以运行当前奖状 MVP。")
    return 0


def cmd_check() -> int:
    if not ensure_project_configured():
        return 1
    code, data, raw = runner_json(["validate"])
    if not data:
        print(raw or "任务图检查失败。")
        return code or 1
    if data.get("valid"):
        print(f"✅ 任务图正常，共 {data.get('task_count', 0)} 个任务。")
        return 0
    print("❌ 任务图有问题：")
    for error in data.get("errors", []):
        print(f"- {error}")
    return 1


def cmd_status() -> int:
    if not ensure_project_configured():
        return 1
    code, data, raw = runner_json(["status"])
    if not data:
        print(raw or "读取状态失败。")
        return code or 1
    state = data.get("state", {})
    tasks = data.get("tasks", [])
    total = len(tasks)
    done = sum(1 for task in tasks if task.get("status") in TERMINAL_DONE)
    waiting = sum(1 for task in tasks if task.get("status", "pending") in WAITING)
    blocked = [task for task in tasks if task.get("status") in BLOCKING]
    current = [task for task in tasks if task.get("status") == "in_progress"]
    upcoming = next_task(tasks)

    print("\n📍 AIOS 状态")
    if blocked and state.get("phase") == "DONE":
        print("- 阶段：BLOCKED / 有任务失败或需要人工处理")
    else:
        print(f"- 阶段：{state.get('phase', 'unknown')} / {state.get('status', 'unknown')}")
    print(f"- 任务：{done}/{total} 已完成，{waiting} 个等待执行")
    if current:
        task = current[0]
        print(f"- 正在执行：{task.get('task_id')} {task.get('title')}")
    elif upcoming:
        print(f"- 下一步：{upcoming.get('task_id')} {upcoming.get('title')}")
    else:
        print("- 下一步：暂无可执行任务")
    if blocked:
        print("- 阻塞/失败：")
        for task in blocked:
            print(f"  - {task.get('task_id')} {task.get('title')} [{task.get('status')}]")
            reason = task.get("blocked_reason") or task.get("last_error")
            if reason:
                print(f"    原因：{str(reason).splitlines()[0]}")
    return 0


def cmd_explain() -> int:
    if not ensure_project_configured():
        return 1
    data = get_status_data()
    if not data:
        print("暂时读不到状态。")
        return 1
    blocked = [task for task in data.get("tasks", []) if task.get("status") in BLOCKING]
    if not blocked:
        print("当前没有失败或阻塞任务。输入“状态”可以查看进度，输入“继续”可以推进。")
        return 0
    print("\n🧭 当前卡点说明")
    for task in blocked:
        print(f"- {task.get('task_id')} {task.get('title')}：{task.get('status')}")
        reason = task.get("blocked_reason") or task.get("last_error") or "没有记录具体原因"
        print(f"  原因：{reason}")
        run = task.get("last_run")
        if run:
            print(f"  日志：{run}")
    print_environment_hint()
    print("\n可以怎么做：")
    print("- 如果是缺依赖/环境问题，先补环境，再输入 `run`。")
    print("- 如果要重新演练，输入 `reset`。")
    print("- 如果要看下一步提示词，输入 `preview`。")
    return 0


def cmd_preview() -> int:
    if not ensure_project_configured():
        return 1
    data = get_status_data()
    upcoming = next_task(data.get("tasks", [])) if data else None
    completed = call_runner(["run-next", "--dry-run"], capture=True)
    path = completed.stdout.strip()
    if completed.returncode != 0:
        print(completed.stderr.strip() or path or "预览失败。")
        return completed.returncode
    if upcoming:
        print(f"👀 下一步：{upcoming.get('task_id')} {upcoming.get('title')}")
    print(f"- Codex 提示词已生成：{path}")
    print("- 这只是预览，没有改业务代码。")
    return 0


def cmd_next() -> int:
    if not ensure_project_configured():
        return 1
    if not ensure_runtime_dependencies(auto_install=True):
        return 1
    data = get_status_data()
    upcoming = next_task(data.get("tasks", [])) if data else None
    if upcoming:
        print(f"🚀 开始执行一步：{upcoming.get('task_id')} {upcoming.get('title')}")
    completed = call_runner(["run-next"], capture=False)
    return completed.returncode


def cmd_run() -> int:
    if not ensure_project_configured():
        return 1
    if not ensure_runtime_dependencies(auto_install=True):
        return 1
    data = get_status_data()
    upcoming = next_task(data.get("tasks", [])) if data else None
    if upcoming:
        print(f"🚀 AIOS 自动推进，从 {upcoming.get('task_id')} {upcoming.get('title')} 开始")
        print("遇到失败、高风险或需要你决策时会停在这里，等你输入。")
    completed = call_runner(["run"], capture=False)
    if completed.returncode != 0:
        print_environment_hint()
        print("\n你可以直接输入自然语言，例如：")
        print("  status     查看卡在哪里")
        print("  run        修复后继续跑")
        print("  preview    看下一步准备做什么")
        print("  这是什么问题？  查看失败原因和处理建议")
    return completed.returncode


def cmd_reset() -> int:
    if not ensure_project_configured():
        return 1
    source_root = source_root_from_config()
    print("🧹 重置执行现场，只保留已确认的 AIOS 文档和原始材料。")
    for rel in RESETTABLE_PATHS:
        path = source_root / rel
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"- 已删除：{path}")

    for folder in [source_root / ".aios" / "runs", source_root / ".aios" / "reports"]:
        if folder.exists():
            for child in folder.iterdir():
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        folder.mkdir(parents=True, exist_ok=True)

    graph_path = source_root / ".aios" / "tasks" / "task_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    for task in graph.get("tasks", []):
        task["status"] = "pending"
        for key in ["attempts", "started_at", "finished_at", "last_run", "last_error", "manual_note", "blocked_reason"]:
            task.pop(key, None)
    graph.get("root_task", {})["status"] = "pending"
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    state_path = source_root / ".aios" / "state.json"
    state = {
        "phase": "READY_TO_EXECUTE",
        "status": "reset_done",
        "iteration": 0,
        "history": [{"phase": "READY_TO_EXECUTE", "status": "reset_done", "note": "business files and run logs cleared; frozen AIOS docs kept"}],
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✅ 已 reset。输入 `run` 或直接回车即可从 T1 重新开始。")
    return 0


def handle_input(raw: str, interactive: bool) -> int:
    command = resolve_command(raw)
    if command == "exit":
        raise AiosExit
    if command == "help":
        print_help()
        return 0
    if command == "check":
        return cmd_check()
    if command == "doctor":
        return cmd_doctor()
    if command == "status":
        return cmd_status()
    if command == "explain":
        return cmd_explain()
    if command == "preview":
        return cmd_preview()
    if command == "next":
        return cmd_next()
    if command == "reset":
        return cmd_reset()
    if command == "note":
        path = append_user_note(raw)
        print(f"📝 已记录你的输入：{path}")
        print("如果这是给 AIOS 的补充说明，接下来输入“继续”即可。")
        return 0
    return cmd_run()


def repl() -> int:
    print("AIOS 已启动。输入 `help` 查看命令；直接回车或输入 `run` 会自动推进。")
    cmd_status()
    while True:
        try:
            raw = input("\naios> ").strip()
            handle_input(raw, interactive=True)
        except AiosExit:
            print("已退出 AIOS。")
            return 0
        except KeyboardInterrupt:
            print("\n已暂停。输入 `run` 可恢复，输入 `exit` 离开。")
        except EOFError:
            print("\n已退出 AIOS。")
            return 0
        except Exception as exc:
            print(f"❌ AIOS 自身出错：{exc}")
            print("你可以输入 `status` 查看当前进度，或输入 `exit`。")


def main() -> None:
    if len(sys.argv) == 1:
        raise SystemExit(repl())
    raw = " ".join(sys.argv[1:]).strip()
    if raw in {"-h", "--help", "help", "帮助"}:
        print_help()
        raise SystemExit(0)
    try:
        raise SystemExit(handle_input(raw, interactive=False))
    except AiosExit:
        raise SystemExit(0)


if __name__ == "__main__":
    main()
