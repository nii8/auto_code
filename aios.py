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
from project_paths import (
    active_initiative_id as config_active_initiative_id,
    active_workspace_dir,
    aios_dir,
    source_dir,
)

PROTECTED_RESET_PREFIXES = {
    ".aios/source",
    ".aios/evidence",
    ".aios/context",
    ".aios/workflow",
    ".aios/checks",
    ".aios/tasks",
    ".aios/project",
    ".aios/initiatives",
    ".aios/changes",
    ".aios/shared",
}


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


def get_status_data() -> dict[str, Any] | None:
    _, data, _ = runner_json(["status"])
    return data


def upcoming_from_status(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None
    upcoming = data.get("summary", {}).get("upcoming")
    return upcoming if isinstance(upcoming, dict) else None


def load_aios_config() -> dict[str, Any]:
    return load_config(ROOT / "aios_docs" / "aios_config.yaml")


def missing_config_fields() -> list[str]:
    config = load_aios_config()
    missing = []
    project_mode = str(config.get("project_mode", "")).strip()
    if project_mode not in {"greenfield", "brownfield", "rebuild"}:
        missing.append("project_mode")
    if not str(config.get("target_source_dir") or config.get("source_code_dir") or "").strip():
        missing.append("target_source_dir/source_code_dir")
    if not str(config.get("source_material_file", "")).strip():
        missing.append("source_material_file")
    if project_mode == "rebuild" and not config.get("reference_source_dirs"):
        missing.append("reference_source_dirs")
    return missing


def print_setup_help(raw: str | None = None) -> None:
    missing = missing_config_fields()
    print("\n⚙️ AIOS 还没有绑定本机项目。")
    if missing:
        print(f"- 缺少配置：{', '.join(missing)}")
    print("- 不需要修改可提交的 `aios_docs/aios_config.yaml`。")
    print("- 请先在对话里告诉 Codex：项目模式 greenfield/brownfield/rebuild。")
    print("- greenfield：需要可写新项目目录、原始材料/聊天记录。")
    print("- brownfield：需要现有可写源码目录、原始材料/聊天记录。")
    print("- rebuild：需要可写新项目目录、旧项目只读源码目录、原始材料/聊天记录。")
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
    return source_dir(load_aios_config())


def aios_root_from_config() -> Path:
    return aios_dir(load_aios_config())


def current_active_initiative_id() -> str:
    return config_active_initiative_id(load_aios_config())


def active_aios_workspace() -> Path:
    return active_workspace_dir(load_aios_config())


def append_user_note(text: str) -> Path:
    notes_path = active_aios_workspace() / "runs" / "user_notes.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    with notes_path.open("a", encoding="utf-8") as file:
        file.write(f"\n## 用户输入\n\n{text.strip()}\n")
    return notes_path


def runtime_python_packages() -> list[tuple[str, str]]:
    config = load_aios_config()
    raw = config.get("runtime", {}).get("python_packages", [])
    if isinstance(raw, str):
        raw = [] if raw.strip() in {"", "[]"} else [raw]
    packages = []
    for item in raw or []:
        if isinstance(item, dict):
            package_name = str(item.get("package") or item.get("name") or "").strip()
            module_name = str(item.get("module") or package_name).strip()
        else:
            package_name = str(item).strip()
            module_name = package_name
        if package_name and module_name:
            packages.append((package_name, module_name))
    return packages


def missing_runtime_modules() -> list[str]:
    missing = []
    for package_name, module_name in runtime_python_packages():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    return missing


def print_environment_hint() -> None:
    missing = missing_runtime_modules()
    if not missing:
        return
    print("\n🔧 当前运行环境可能还没准备好：")
    print(f"- 缺少 Python 包：{', '.join(missing)}")
    print(f"- 可在项目环境里安装后再继续，例如：`python3 -m pip install {' '.join(missing)}`")


def ensure_runtime_dependencies(auto_install: bool = True) -> bool:
    missing = missing_runtime_modules()
    if not missing:
        return True
    print("\n🔧 AIOS 运行前依赖预检")
    print(f"- 缺少项目配置声明的低风险 Python 包：{', '.join(missing)}")
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
    print("  reset                 清掉运行日志和任务状态，从任务图重跑")
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
        print(f"- 建议先运行：`python3 -m pip install {' '.join(missing)}`")
        return 1
    configured_packages = runtime_python_packages()
    if configured_packages:
        print("- 项目配置声明的 Python 包：已可导入")
    else:
        print("- 项目配置未声明需要预检的 Python 包")
    print("- AIOS 内核环境看起来可用。")
    return 0


def resettable_paths_from_config() -> list[Path]:
    config = load_aios_config()
    raw = config.get("reset", {}).get("generated_paths", [])
    if isinstance(raw, str):
        raw = [] if raw.strip() in {"", "[]"} else [raw]
    source_root = source_root_from_config()
    paths: list[Path] = []
    for item in raw or []:
        rel_text = str(item).strip().strip("/")
        if not rel_text or rel_text in {".", ".."}:
            continue
        rel_path = Path(rel_text)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            continue
        normalized = rel_path.as_posix()
        if any(normalized == prefix or normalized.startswith(prefix + "/") for prefix in PROTECTED_RESET_PREFIXES):
            continue
        paths.append(source_root / rel_path)
    return paths


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
    summary = data.get("summary", {})
    blocked = summary.get("blocked") or []
    current = summary.get("current")
    upcoming = summary.get("upcoming")

    print("\n📍 AIOS 状态")
    print(f"- 阶段：{summary.get('phase', state.get('phase', 'unknown'))} / {summary.get('status', state.get('status', 'unknown'))}")
    print(f"- 任务：{summary.get('done', 0)}/{summary.get('total', 0)} 已完成，{summary.get('waiting', 0)} 个等待执行")
    if current:
        print(f"- 正在执行：{current.get('task_id')} {current.get('title')}")
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
    blocked = data.get("summary", {}).get("blocked") or []
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
    upcoming = upcoming_from_status(data)
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
    upcoming = upcoming_from_status(data)
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
    upcoming = upcoming_from_status(data)
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
    initiative_id = current_active_initiative_id()
    print("🧹 重置执行现场，保留源码、原始材料和已确认的 AIOS 文档。")
    if initiative_id:
        print(f"- 当前 initiative：{initiative_id}")
    else:
        print("- 当前模式：顶层 .aios 兼容模式")
    generated_paths = resettable_paths_from_config()
    if generated_paths:
        print("- 将按配置清理 reset.generated_paths 中声明的生成路径。")
    else:
        print("- 未配置 reset.generated_paths，不删除业务源码或生成产物。")
    for path in generated_paths:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"- 已删除：{path}")

    completed = call_runner(["reset"], capture=True)
    if completed.returncode != 0:
        print(completed.stderr.strip() or completed.stdout.strip() or "reset 失败。")
        return completed.returncode
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
