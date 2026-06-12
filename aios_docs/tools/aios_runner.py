#!/usr/bin/env python3
"""Minimal AIOS runner.

Generic runner for any project configured by aios_config.yaml. It loads the
project's .aios task graph, runs one ready task through Codex Worker, stores
logs, runs deterministic checks, and updates task/state files.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import json
import select
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from config_loader import load_config
from project_paths import (
    DEFAULT_STATE,
    active_initiative_id,
    active_workspace_dir,
    aios_dir,
    ensure_reference_dirs_readonly_boundary,
    reference_source_dirs,
    reports_dir,
    runs_dir,
    source_dir,
    state_path,
    task_graph_path,
)


TERMINAL_STATUSES = {"done", "failed", "blocked", "skipped_with_reason", "needs_human"}
READY_STATUSES = {"pending", "failed"}
REPRODUCIBLE_CHECKERS = {
    "shell",
    "expected_output_content",
    "expected_output_sha256",
    "expected_output_min_size",
}
REFERENCE_MANIFEST_MAX_FILES = 10000
PROJECT_CONTEXT_FILES = [
    ".aios/project/project_overview.md",
    ".aios/project/architecture.md",
    ".aios/project/module_map.md",
    ".aios/project/pipeline_map.md",
    ".aios/project/initiative_index.md",
    ".aios/shared/constraints.md",
    ".aios/shared/coding_rules.md",
    ".aios/shared/dependency_policy.md",
    ".aios/shared/risk_policy.md",
    ".aios/shared/evidence_policy.md",
]
COMPAT_CONTEXT_FILES = [
    ".aios/context/goal.md",
    ".aios/context/requirements.md",
    ".aios/context/spec.md",
    ".aios/context/examples.md",
    ".aios/workflow/workflow.md",
    ".aios/checks/checks.md",
    ".aios/context/acceptance.md",
]
INITIATIVE_CONTEXT_FILES = [
    "context/goal.md",
    "context/requirements.md",
    "context/spec.md",
    "context/examples.md",
    "workflow/workflow.md",
    "checks/checks.md",
    "context/acceptance.md",
]
DEFAULT_PROMPT_CONTEXT_BUDGET_CHARS = 60000
DEFAULT_PLANNING_CONTEXT_BUDGET_CHARS = 120000
PROMPT_WARNING_RATIO = 0.85
STARTUP_CONTEXT_WARNING_CHARS = 120000
STARTUP_CONTEXT_DANGER_CHARS = 240000
SOURCE_TREE_WARNING_FILES = 800
SOURCE_TREE_DANGER_FILES = 5000
SOURCE_TREE_WARNING_BYTES = 10 * 1024 * 1024
SOURCE_TREE_DANGER_BYTES = 50 * 1024 * 1024


def estimate_tokens(text_or_chars: str | int) -> int:
    chars = len(text_or_chars) if isinstance(text_or_chars, str) else int(text_or_chars)
    if chars <= 0:
        return 0
    return max(1, math.ceil(chars / 3))


def context_severity(chars: int, warning_chars: int, danger_chars: int) -> str:
    if chars >= danger_chars:
        return "danger"
    if chars >= warning_chars:
        return "warning"
    return "ok"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "未知"
    total = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}小时{minutes}分{secs}秒"
    if minutes:
        return f"{minutes}分{secs}秒"
    return f"{secs}秒"


def task_duration_seconds(task: dict[str, Any]) -> int | None:
    value = task.get("duration_seconds")
    if isinstance(value, (int, float)):
        return int(round(value))
    started = task.get("started_at")
    finished = task.get("finished_at")
    if not started or not finished:
        return None
    try:
        start_time = datetime.fromisoformat(str(started))
        finish_time = datetime.fromisoformat(str(finished))
    except ValueError:
        return None
    return max(0, int(round((finish_time - start_time).total_seconds())))


def print_run_summary(tasks: list[dict[str, Any]], total_seconds: float | int | None, completed_this_run: int) -> None:
    print("\n📊 本次执行汇总")
    print(f"- 本次完成：{completed_this_run} 个任务")
    print(f"- 总耗时：{format_duration(total_seconds)}")
    print("\n任务耗时：")
    for task in tasks:
        duration = format_duration(task_duration_seconds(task))
        print(f"- {task.get('task_id')} {task.get('title')}：{task.get('status', 'pending')}，耗时 {duration}")



def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(config: dict[str, Any]) -> dict[str, Any]:
    path = state_path(config)
    if not path.exists():
        return dict(DEFAULT_STATE)
    return load_json(path)


def save_state(config: dict[str, Any], state: dict[str, Any]) -> None:
    write_json(state_path(config), state)


def update_state(config: dict[str, Any], phase: str, status: str, **extra: Any) -> None:
    state = load_state(config)
    state["phase"] = phase
    state["status"] = status
    state.update(extra)
    state.setdefault("history", []).append({"time": now_iso(), "phase": phase, "status": status, **extra})
    save_state(config, state)


def load_task_graph(config: dict[str, Any]) -> dict[str, Any]:
    path = task_graph_path(config)
    if not path.exists():
        raise RuntimeError(f"task graph not found: {path}")
    graph = load_json(path)
    if not isinstance(graph.get("tasks"), list):
        raise RuntimeError("task_graph.json must contain a tasks list")
    return graph


def save_task_graph(config: dict[str, Any], graph: dict[str, Any]) -> None:
    write_json(task_graph_path(config), graph)


def task_by_id(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(task.get("task_id")): task for task in graph.get("tasks", [])}


def dependencies_done(task: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> bool:
    for dep_id in task.get("dependencies", []):
        dep = tasks.get(str(dep_id))
        if not dep or dep.get("status") != "done":
            return False
    return True


def next_ready_task(graph: dict[str, Any]) -> dict[str, Any] | None:
    tasks = task_by_id(graph)
    for task in graph.get("tasks", []):
        status = task.get("status", "pending")
        if status in TERMINAL_STATUSES and status != "failed":
            continue
        if status not in READY_STATUSES:
            continue
        attempts = int(task.get("attempts", 0))
        max_attempts = int(task.get("max_repair_attempts", 0))
        if status == "failed" and attempts > max_attempts:
            task["status"] = "needs_human"
            task["blocked_reason"] = "max repair attempts exceeded"
            continue
        if dependencies_done(task, tasks):
            return task
    return None


def has_unresolved_tasks(graph: dict[str, Any]) -> bool:
    return any(task.get("status", "pending") != "done" for task in graph.get("tasks", []))


def status_summary(tasks: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    total = len(tasks)
    done = sum(1 for task in tasks if task.get("status") == "done")
    waiting = sum(1 for task in tasks if task.get("status", "pending") == "pending")
    blocked = [task for task in tasks if task.get("status") in {"failed", "blocked", "needs_human"}]
    current = next((task for task in tasks if task.get("status") == "in_progress"), None)
    upcoming = next_ready_task({"tasks": tasks})
    phase = state.get("phase", "unknown")
    if blocked and phase == "DONE":
        phase = "BLOCKED"
    return {
        "total": total,
        "done": done,
        "waiting": waiting,
        "blocked": blocked,
        "current": current,
        "upcoming": upcoming,
        "phase": phase,
        "status": state.get("status", "unknown"),
    }


def read_if_exists(path: Path, max_chars: int = 12000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]\n"
    return text


def prompt_context_budget(config: dict[str, Any]) -> int:
    raw = config.get("prompt", {}).get("context_budget_chars", DEFAULT_PROMPT_CONTEXT_BUDGET_CHARS)
    try:
        return max(8000, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_PROMPT_CONTEXT_BUDGET_CHARS


def planning_context_budget(config: dict[str, Any]) -> int:
    raw = config.get("planning", {}).get("context_budget_chars", DEFAULT_PLANNING_CONTEXT_BUDGET_CHARS)
    try:
        return max(20000, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_PLANNING_CONTEXT_BUDGET_CHARS


def safe_context_ref(root: Path, workspace: Path, rel: str) -> Path | None:
    rel_text = str(rel).strip().lstrip("/")
    if not rel_text:
        return None
    rel_path = Path(rel_text)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        return None
    if rel_text.startswith(".aios/"):
        return root / rel_path
    return workspace / rel_path


def append_context_file(
    parts: list[str],
    report_files: list[dict[str, Any]],
    label: str,
    path: Path,
    remaining_chars: int,
    max_file_chars: int = 12000,
    required: bool = False,
) -> int:
    entry: dict[str, Any] = {
        "label": label,
        "path": str(path),
        "required": required,
        "exists": path.exists(),
        "included_chars": 0,
        "original_chars": 0,
        "truncated": False,
        "skipped_reason": "",
    }
    if not path.exists() or not path.is_file():
        entry["skipped_reason"] = "missing"
        report_files.append(entry)
        return remaining_chars
    try:
        original_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        entry["skipped_reason"] = f"read_error: {exc}"
        report_files.append(entry)
        return remaining_chars
    entry["original_chars"] = len(original_text)
    if remaining_chars <= 0:
        entry["skipped_reason"] = "context_budget_exhausted"
        entry["truncated"] = True
        report_files.append(entry)
        return remaining_chars
    limit = min(max_file_chars, remaining_chars)
    included_text = original_text[:limit]
    if len(original_text) > limit:
        included_text += "\n\n[TRUNCATED]\n"
        entry["truncated"] = True
    if not included_text:
        entry["skipped_reason"] = "empty"
        report_files.append(entry)
        return remaining_chars
    parts.extend([f"\n## {label}", included_text])
    entry["included_chars"] = len(included_text)
    report_files.append(entry)
    return max(0, remaining_chars - len(included_text))


def build_prompt_with_report(config: dict[str, Any], task: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    root = source_dir(config)
    refs = reference_source_dirs(config)
    project_mode = str(config.get("project_mode") or "未配置")
    initiative_id = active_initiative_id(config)
    workspace = active_workspace_dir(config)
    budget = prompt_context_budget(config)
    parts = [
        "你是 AIOS 的 Codex Worker。请只执行当前任务，不要改变项目方向。",
        "",
        "# 项目模式",
        project_mode,
        "",
        "# 当前执行范围",
        f"active_initiative: {initiative_id or '兼容模式：顶层 .aios'}",
        f"aios_workspace: {workspace}",
        "",
        "# 可写目标工作目录",
        str(root),
        "",
        "# 只读参考源码目录",
        "\n".join(str(path) for path in refs) if refs else "无",
        "",
        "# 当前任务",
        json.dumps(task, ensure_ascii=False, indent=2),
        "",
        "# 硬性规则",
        "- 只修改 write_scope 中允许的文件或目录。",
        "- 所有写入必须发生在可写目标工作目录内；不要写入只读参考源码目录。",
        "- reference_source_dirs 只能读取和理解，不能修改、格式化、删除或生成文件。",
        "- rebuild 模式下，旧项目只作为业务理解和参考，不允许把旧项目当作修补目标。",
        "- 不要修改 .aios/project、.aios/shared、当前 initiative 的 context/workflow/checks 等已冻结文档。",
        "- 如果任务属于复杂 pipeline，必须尊重 module_map/pipeline_map 中的上下游关系和阶段边界。",
        "- 如果发现当前任务会破坏其他模块、其他 initiative 或项目级约束，停止并说明 needs_human。",
        "- 不要实现任务明确排除的功能。",
        "- 如果任务不清楚或需要高风险操作，停止并说明 needs_human。",
        "- 没有证据不允许宣布完成；不能只凭自评说任务完成。",
        "- 必须尽量运行与当前任务相关的确定性检查；能模拟用户流程时必须模拟关键路径。",
        "- 必须包含负向检查：空输入、非法资源、不存在对象、路径穿越、失败状态等按任务相关性选择。",
        "- 如果因为环境、权限或外部依赖无法验证，必须明确写出未验证项和阻塞原因，不要包装成完成。",
        "- 完成报告必须包含：改动文件、运行命令、检查结果、证据路径、未验证项。",
        "",
        "# 项目级冻结上下文",
    ]
    remaining = budget
    report_files: list[dict[str, Any]] = []
    unsafe_refs: list[str] = []
    for rel in task.get("context_refs", []) or []:
        path = safe_context_ref(root, workspace, str(rel))
        if path:
            remaining = append_context_file(parts, report_files, str(rel), path, remaining, required=True)
        else:
            unsafe_refs.append(str(rel))
    for rel in PROJECT_CONTEXT_FILES:
        remaining = append_context_file(parts, report_files, rel, root / rel, remaining, max_file_chars=8000)
    parts.append("\n# 当前目标冻结上下文")
    if initiative_id:
        for rel in INITIATIVE_CONTEXT_FILES:
            remaining = append_context_file(parts, report_files, f".aios/initiatives/{initiative_id}/{rel}", workspace / rel, remaining, max_file_chars=8000)
    else:
        for rel in COMPAT_CONTEXT_FILES:
            remaining = append_context_file(parts, report_files, rel, root / rel, remaining, max_file_chars=8000)
    budget_exhausted = remaining <= 0
    if budget_exhausted:
        parts.append("\n[CONTEXT_BUDGET_EXHAUSTED: 其余上下文未全文展开；如任务需要，请按路径读取相关文件。]")
    prompt = "\n".join(parts)
    included_context_chars = sum(int(item.get("included_chars", 0)) for item in report_files)
    original_context_chars = sum(int(item.get("original_chars", 0)) for item in report_files)
    truncated_files = [item for item in report_files if item.get("truncated")]
    skipped_files = [item for item in report_files if item.get("skipped_reason")]
    report = {
        "budget_chars": budget,
        "warning_chars": int(budget * PROMPT_WARNING_RATIO),
        "prompt_chars": len(prompt),
        "estimated_tokens": estimate_tokens(prompt),
        "included_context_chars": included_context_chars,
        "original_context_chars": original_context_chars,
        "remaining_context_budget_chars": remaining,
        "budget_exhausted": budget_exhausted,
        "budget_usage_ratio": round(included_context_chars / budget, 4) if budget else 0,
        "severity": context_severity(included_context_chars, int(budget * PROMPT_WARNING_RATIO), budget),
        "context_file_count": len(report_files),
        "included_file_count": sum(1 for item in report_files if int(item.get("included_chars", 0)) > 0),
        "truncated_file_count": len(truncated_files),
        "skipped_file_count": len(skipped_files),
        "unsafe_context_refs": unsafe_refs,
        "largest_files": sorted(report_files, key=lambda item: int(item.get("original_chars", 0)), reverse=True)[:8],
        "files": report_files,
    }
    return prompt, report


def build_prompt(config: dict[str, Any], task: dict[str, Any]) -> str:
    prompt, _ = build_prompt_with_report(config, task)
    return prompt


def print_prompt_report(report: dict[str, Any]) -> None:
    severity = report.get("severity", "ok")
    icon = "🚨" if severity == "danger" else "⚠️" if severity == "warning" else "📏"
    print(f"{icon} Worker Prompt 上下文报告", flush=True)
    print(f"- prompt 总量：{report.get('prompt_chars', 0)} 字符，约 {report.get('estimated_tokens', 0)} tokens", flush=True)
    print(f"- 上下文预算：{report.get('included_context_chars', 0)}/{report.get('budget_chars', 0)} 字符，使用率 {float(report.get('budget_usage_ratio', 0)):.0%}", flush=True)
    print(f"- 展开文件：{report.get('included_file_count', 0)}/{report.get('context_file_count', 0)}，截断 {report.get('truncated_file_count', 0)}，跳过 {report.get('skipped_file_count', 0)}", flush=True)
    if report.get("budget_exhausted"):
        print("- 已达到上下文预算：其余文件只保留路径线索，当前任务应缩小范围或补 context_refs。", flush=True)
    unsafe_refs = report.get("unsafe_context_refs") or []
    if unsafe_refs:
        print(f"- 忽略了不安全 context_refs：{', '.join(unsafe_refs[:5])}", flush=True)
    largest = report.get("largest_files") or []
    if largest:
        print("- 最大上下文文件：", flush=True)
        for item in largest[:5]:
            status = "截断" if item.get("truncated") else "完整" if item.get("included_chars") else item.get("skipped_reason", "跳过")
            print(f"  - {item.get('label')}：原始 {item.get('original_chars', 0)} 字符，放入 {item.get('included_chars', 0)} 字符，{status}", flush=True)


def run_codex(config: dict[str, Any], prompt: str) -> dict[str, Any]:
    codex_config = config.get("codex", {})
    command = codex_config.get("command", "codex")
    default_args = codex_config.get("default_args", ["exec", "--json", "--sandbox", "workspace-write"])
    timeout = int(codex_config.get("timeout_seconds", 3600))
    cmd = [command, *default_args, "--cd", str(source_dir(config)), prompt]
    started = time.time()
    process = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    last_event_time = time.time()
    last_heartbeat = time.time()

    assert process.stdout is not None
    while True:
        ready, _, _ = select.select([process.stdout], [], [], 0.2)
        if ready:
            line = process.stdout.readline()
            if line:
                stdout_parts.append(line)
                last_event_time = time.time()
                print_codex_event(line)
                continue
        if process.poll() is not None:
            rest = process.stdout.read()
            if rest:
                stdout_parts.append(rest)
                for line in rest.splitlines():
                    print_codex_event(line)
            break

        now = time.time()
        if now - started > timeout:
            process.kill()
            stderr_parts.append(f"Timed out after {timeout} seconds\n")
            break
        if now - last_heartbeat >= 20:
            elapsed = int(now - started)
            silent = int(now - last_event_time)
            print(f"   …Codex Worker 仍在执行（已 {elapsed}s，{silent}s 无新事件）", flush=True)
            last_heartbeat = now

    if process.stderr is not None:
        stderr_parts.append(process.stderr.read())
    returncode = process.wait()
    return {
        "command": cmd[:-1] + ["<prompt>"],
        "returncode": returncode,
        "stdout": "".join(stdout_parts),
        "stderr": "".join(stderr_parts),
    }


def print_codex_event(line: str) -> None:
    text = line.strip()
    if not text:
        return
    try:
        event = json.loads(text)
    except json.JSONDecodeError:
        clipped = text[:180]
        print(f"   codex> {clipped}", flush=True)
        return

    message = summarize_codex_event(event)
    if message:
        print(f"   {message}", flush=True)


def summarize_codex_event(event: dict[str, Any]) -> str | None:
    event_type = str(event.get("type", ""))
    item = event.get("item") if isinstance(event.get("item"), dict) else {}
    item_type = str(item.get("type", ""))
    status = str(item.get("status", ""))

    if item_type == "command_execution":
        command = str(item.get("command", ""))
        if status == "in_progress":
            return "🔧 执行命令：" + clip(command)
        if status == "completed":
            exit_code = item.get("exit_code")
            output = str(item.get("aggregated_output", "")).strip()
            if output:
                return f"✅ 命令完成 exit={exit_code}: {clip(command)}\n      输出：{clip(output, 360)}"
            return f"✅ 命令完成 exit={exit_code}: {clip(command)}"

    if item_type == "todo_list":
        todos = item.get("items") or []
        if todos:
            done = sum(1 for todo in todos if todo.get("completed"))
            return f"📋 进度：{done}/{len(todos)} 个子步骤完成"

    if item_type == "agent_message":
        content = str(item.get("text", "")).strip()
        if content:
            return "💬 " + clip(content)

    if event_type in {"turn.started", "turn.completed"}:
        return "🚦 " + event_type

    return None


def clip(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def run_shell_check(config: dict[str, Any], check: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(check, dict):
        command = str(check.get("command") or "").strip()
        blocking = bool(check.get("blocking", True))
        evidence_level = str(check.get("evidence_level") or "L2")
    else:
        command = str(check).strip()
        blocking = True
        evidence_level = "L2"
    original_command = command
    if not command:
        return {
            "checker": "shell",
            "original_command": original_command,
            "command": command,
            "returncode": 1,
            "stdout": "",
            "stderr": "empty shell check command",
            "passed": False,
            "blocking": blocking,
            "evidence_level": evidence_level,
        }
    if command.startswith("python ") and not shutil_which("python") and shutil_which("python3"):
        command = "python3 " + command[len("python "):]
    completed = subprocess.run(
        command,
        shell=True,
        cwd=source_dir(config),
        text=True,
        capture_output=True,
        timeout=300,
    )
    return {
        "checker": "shell",
        "original_command": original_command,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "passed": completed.returncode == 0,
        "blocking": blocking,
        "evidence_level": evidence_level,
    }


def shutil_which(command: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(directory) / command
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return None


def run_task_checks(config: dict[str, Any], task: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    for check in task.get("success_checks", []) or []:
        checks.append(run_shell_check(config, check))
    return checks


def validate_expected_outputs(config: dict[str, Any], task: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    root = source_dir(config)
    for item in task.get("expected_outputs", []) or []:
        if isinstance(item, dict):
            rel = str(item.get("path") or "").strip()
            blocking = bool(item.get("blocking", True))
            content_contains = item.get("content_contains") or []
            min_size = item.get("min_size")
            expected_sha256 = str(item.get("sha256") or "").strip()
        else:
            rel = str(item).strip()
            blocking = True
            content_contains = []
            min_size = None
            expected_sha256 = ""
        path = root / rel
        checks.append({
            "checker": "expected_output_exists",
            "path": str(path),
            "passed": path.exists(),
            "blocking": blocking,
            "evidence_level": "L1",
            "evidence": "exists" if path.exists() else "missing",
        })
        if not path.exists() or path.is_dir():
            continue
        if isinstance(content_contains, str):
            content_contains = [content_contains]
        if content_contains:
            text = path.read_text(encoding="utf-8", errors="replace")
            missing = [str(marker) for marker in content_contains if str(marker) not in text]
            checks.append({
                "checker": "expected_output_content",
                "path": str(path),
                "passed": not missing,
                "blocking": blocking,
                "evidence_level": "L2",
                "evidence": "all content markers present" if not missing else "missing markers: " + ", ".join(missing[:5]),
            })
        if min_size is not None:
            try:
                minimum = int(min_size)
            except (TypeError, ValueError):
                minimum = 0
            size = path.stat().st_size
            checks.append({
                "checker": "expected_output_min_size",
                "path": str(path),
                "passed": size >= minimum,
                "blocking": blocking,
                "evidence_level": "L2",
                "evidence": f"size={size}, min_size={minimum}",
            })
        if expected_sha256:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            checks.append({
                "checker": "expected_output_sha256",
                "path": str(path),
                "passed": digest == expected_sha256,
                "blocking": blocking,
                "evidence_level": "L3",
                "evidence": f"sha256={digest}",
            })
    return checks


def validate_evidence_policy(task: dict[str, Any], checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if task.get("evidence_required") is False:
        return []
    blocking_checks = [check for check in checks if check.get("blocking", True)]
    reproducible = [
        check for check in blocking_checks
        if check.get("checker") in REPRODUCIBLE_CHECKERS
    ]
    passed = bool(reproducible)
    return [{
        "checker": "evidence_policy",
        "passed": passed,
        "blocking": True,
        "evidence_level": "policy",
        "evidence": "has reproducible blocking check" if passed else "missing reproducible blocking check; AI self-report or file existence alone is not enough",
    }]


def task_has_reproducible_evidence_spec(task: dict[str, Any]) -> bool:
    if task.get("evidence_required") is False:
        return True
    for check in task.get("success_checks", []) or []:
        if isinstance(check, dict):
            if check.get("blocking", True) and str(check.get("command") or "").strip():
                return True
        elif str(check).strip():
            return True
    for item in task.get("expected_outputs", []) or []:
        if not isinstance(item, dict):
            continue
        if not item.get("blocking", True):
            continue
        if item.get("content_contains") or item.get("min_size") is not None or item.get("sha256"):
            return True
    return False


def snapshot_reference_sources(config: dict[str, Any]) -> dict[str, Any]:
    manifest: dict[str, Any] = {"roots": {}, "truncated": False, "file_count": 0}
    for root in reference_source_dirs(config):
        root_key = str(root)
        files: dict[str, Any] = {}
        if not root.exists():
            manifest["roots"][root_key] = {"exists": False, "files": files}
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if manifest["file_count"] >= REFERENCE_MANIFEST_MAX_FILES:
                manifest["truncated"] = True
                break
            try:
                stat = path.stat()
                rel = path.relative_to(root).as_posix()
            except OSError:
                continue
            files[rel] = {
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
            manifest["file_count"] += 1
        manifest["roots"][root_key] = {"exists": True, "files": files}
    return manifest


def compare_reference_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes: list[str] = []
    before_roots = before.get("roots", {})
    after_roots = after.get("roots", {})
    for root in sorted(set(before_roots) | set(after_roots)):
        before_root = before_roots.get(root, {})
        after_root = after_roots.get(root, {})
        if before_root.get("exists") != after_root.get("exists"):
            changes.append(f"root existence changed: {root}")
            continue
        before_files = before_root.get("files", {})
        after_files = after_root.get("files", {})
        for rel in sorted(set(before_files) | set(after_files)):
            if before_files.get(rel) != after_files.get(rel):
                changes.append(f"{root}/{rel}")
                if len(changes) >= 20:
                    return {"changed": True, "changes": changes, "truncated": before.get("truncated") or after.get("truncated")}
    return {"changed": bool(changes), "changes": changes, "truncated": before.get("truncated") or after.get("truncated")}


def reference_integrity_check(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    comparison = compare_reference_snapshots(before, after)
    changed = bool(comparison.get("changed"))
    return {
        "checker": "reference_source_integrity",
        "passed": not changed,
        "blocking": True,
        "evidence_level": "L3",
        "evidence": "reference_source_dirs unchanged" if not changed else "reference_source_dirs changed: " + "; ".join(comparison.get("changes", [])[:5]),
        "details": comparison,
    }


def validate_report_content(config: dict[str, Any], task: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for item in task.get("expected_outputs", []) or []:
        rel_text = str(item.get("path") if isinstance(item, dict) else item).strip()
        if not rel_text.endswith(".md"):
            continue
        path = source_dir(config) / rel_text
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        bad_markers = ["部分通过", "环境阻塞", "阻塞", "MISSING", "未通过", "无法完成", "failed", "失败"]
        evidence_markers = ["结论", "检查", "通过", "验证", "证据"]
        found = [marker for marker in bad_markers if marker in text]
        missing_evidence = [marker for marker in evidence_markers if marker not in text]
        passed = not found and not missing_evidence
        evidence = "no blocker markers and evidence markers present"
        if found:
            evidence = "found blockers: " + ", ".join(found[:5])
        elif missing_evidence:
            evidence = "missing evidence markers: " + ", ".join(missing_evidence[:5])
        checks.append({
            "checker": "report_evidence_scan",
            "path": str(path),
            "passed": passed,
            "blocking": True,
            "evidence_level": "L0",
            "evidence": evidence,
        })
    return checks


def write_run_artifacts(
    config: dict[str, Any],
    task: dict[str, Any],
    prompt: str,
    result: dict[str, Any],
    checks: list[dict[str, Any]],
    prompt_report: dict[str, Any] | None = None,
) -> Path:
    run_id = f"{now_stamp()}_{task.get('task_id', 'task')}"
    path = runs_dir(config) / f"{run_id}.json"
    payload = {
        "run_id": run_id,
        "time": now_iso(),
        "task_id": task.get("task_id"),
        "task_title": task.get("title"),
        "prompt": prompt,
        "prompt_report": prompt_report or {},
        "codex_result": result,
        "checks": checks,
    }
    write_json(path, payload)
    latest = runs_dir(config) / "latest_run.json"
    write_json(latest, payload)
    return path


def run_next(config: dict[str, Any], dry_run: bool = False) -> int:
    ensure_reference_dirs_readonly_boundary(config)
    graph = load_task_graph(config)
    task = next_ready_task(graph)
    if task is None:
        save_task_graph(config, graph)
        update_state(config, "DONE", "no_ready_task")
        print("No ready task. Project may be done or blocked.")
        return 0

    risk_level = str(task.get("risk_level", "medium"))
    if risk_level == "high":
        task["status"] = "needs_human"
        task["blocked_reason"] = "high risk task requires human confirmation"
        save_task_graph(config, graph)
        update_state(config, "HUMAN_GATE", "high_risk_task", current_task_id=task.get("task_id"))
        print(f"⚠️ 需要你确认：{task.get('task_id')} {task.get('title')} 是高风险任务。")
        return 2

    prompt, prompt_report = build_prompt_with_report(config, task)
    if dry_run:
        path = runs_dir(config) / f"{now_stamp()}_{task.get('task_id')}_prompt.md"
        path.write_text(prompt, encoding="utf-8")
        report_path = path.with_suffix(".prompt_report.json")
        write_json(report_path, prompt_report)
        update_state(config, "EXECUTE_TASK", "dry_run", current_task_id=task.get("task_id"), prompt_path=str(path), prompt_report_path=str(report_path))
        print_prompt_report(prompt_report)
        print(path)
        return 0

    task_started = time.time()
    task["status"] = "in_progress"
    task["started_at"] = now_iso()
    save_task_graph(config, graph)
    update_state(config, "EXECUTE_TASK", "running", current_task_id=task.get("task_id"))

    attempts = int(task.get("attempts", 0)) + 1
    task["attempts"] = attempts
    save_task_graph(config, graph)

    print_prompt_report(prompt_report)
    reference_before = snapshot_reference_sources(config)
    result = run_codex(config, prompt)
    reference_after = snapshot_reference_sources(config)
    checks = []
    checks.append(reference_integrity_check(reference_before, reference_after))
    if result["returncode"] == 0:
        checks.extend(run_task_checks(config, task))
        checks.extend(validate_expected_outputs(config, task))
        checks.extend(validate_report_content(config, task))
        checks.extend(validate_evidence_policy(task, checks))
    artifact_path = write_run_artifacts(config, task, prompt, result, checks, prompt_report=prompt_report)
    blocking_checks = [check for check in checks if check.get("blocking", True)]
    checks_passed = all(check.get("passed") for check in blocking_checks) if blocking_checks else False

    graph = load_task_graph(config)
    tasks = task_by_id(graph)
    current = tasks.get(str(task.get("task_id")), task)
    current["attempts"] = attempts
    current["last_run"] = str(artifact_path)
    current["finished_at"] = now_iso()
    current["duration_seconds"] = int(round(time.time() - task_started))

    if result["returncode"] == 0 and checks_passed:
        current["status"] = "done"
        status = "task_done"
    else:
        current["status"] = "failed"
        current["last_error"] = result.get("stderr") or "checks failed"
        status = "task_failed"

    save_task_graph(config, graph)
    update_state(config, "CHECK", status, current_task_id=current.get("task_id"), last_run=str(artifact_path))
    if current["status"] == "done":
        print(f"✅ 完成：{current.get('task_id')} {current.get('title')}")
        print(f"- 耗时：{format_duration(current.get('duration_seconds'))}")
        print(f"- 日志：{artifact_path}")
    else:
        print(f"❌ 停下：{current.get('task_id')} {current.get('title')} 未通过。")
        print(f"- 耗时：{format_duration(current.get('duration_seconds'))}")
        print(f"- 日志：{artifact_path}")
        if checks:
            failed_checks = [check for check in checks if not check.get("passed")]
            for check in failed_checks[:3]:
                print(f"- 失败检查：{check.get('command')}")
                detail = (check.get("stderr") or check.get("stdout") or "").strip()
                if detail:
                    print(f"  {detail.splitlines()[0]}")
    return 0 if current["status"] == "done" else 1


def run_auto(config: dict[str, Any], max_steps: int | None = None) -> int:
    limits = config.get("limits", {})
    step_limit = max_steps or int(limits.get("max_total_steps", 20))
    completed = 0
    run_started = time.time()

    for _ in range(step_limit):
        graph = load_task_graph(config)
        task = next_ready_task(graph)
        if task is None:
            save_task_graph(config, graph)
            phase = "DONE" if not has_unresolved_tasks(graph) else "BLOCKED"
            status = "all_tasks_done" if phase == "DONE" else "no_ready_task"
            update_state(config, phase, status)
            total_seconds = time.time() - run_started
            if phase == "DONE":
                print(f"🎉 全部任务完成。本次完成 {completed} 个任务。")
            else:
                print(f"⏸️ 没有可继续执行的任务。本次完成 {completed} 个任务。")
                print("- 仍有任务未完成，可能失败、阻塞或需要人工确认。")
                print("- 请输入 `status` 或 `这是什么问题？` 查看原因。")
            print_run_summary(graph.get("tasks", []), total_seconds, completed)
            return 0 if phase == "DONE" else 2

        print(f"\n▶️ {task.get('task_id')} {task.get('title')}", flush=True)
        code = run_next(config, dry_run=False)
        if code != 0:
            graph = load_task_graph(config)
            total_seconds = time.time() - run_started
            print(f"⏸️ AIOS 已暂停。本次完成 {completed} 个任务。")
            print("- 原因：任务失败、高风险或需要人工确认。")
            print("- 你可以输入 `python3 aios.py status` 查看卡在哪里。")
            print("- 处理好后输入 `python3 aios.py run`，AIOS 会从失败点继续。")
            print("- 如果要从头演练，输入 `python3 aios.py reset`。")
            print_run_summary(graph.get("tasks", []), total_seconds, completed)
            return code
        completed += 1

    graph = load_task_graph(config)
    total_seconds = time.time() - run_started
    update_state(config, "HUMAN_GATE", "max_steps_reached", completed_this_run=completed, total_seconds=int(round(total_seconds)))
    print(f"⏸️ 达到本轮最大步数，AIOS 暂停。本次完成 {completed} 个任务。")
    print_run_summary(graph.get("tasks", []), total_seconds, completed)
    return 2


def file_char_entry(label: str, path: Path, required: bool = False) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "label": label,
        "path": str(path),
        "required": required,
        "exists": path.exists(),
        "chars": 0,
        "estimated_tokens": 0,
        "bytes": 0,
        "error": "",
    }
    if not path.exists() or not path.is_file():
        return entry
    try:
        stat = path.stat()
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        entry["error"] = str(exc)
        return entry
    entry["chars"] = len(text)
    entry["estimated_tokens"] = estimate_tokens(text)
    entry["bytes"] = stat.st_size
    return entry


def config_relative_path(config: dict[str, Any], value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    config_path = Path(str(config.get("_config_path") or ".")).expanduser().resolve()
    candidate = (config_path.parent / path).resolve()
    if candidate.exists():
        return candidate
    return (source_dir(config) / path).resolve()


def source_material_entry(config: dict[str, Any]) -> dict[str, Any] | None:
    raw = str(config.get("source_material_file") or "").strip()
    if not raw:
        return None
    return file_char_entry("source_material_file", config_relative_path(config, raw), required=True)


def collect_context_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    root = source_dir(config)
    workspace = active_workspace_dir(config)
    initiative_id = active_initiative_id(config)
    entries: list[dict[str, Any]] = []
    for rel in PROJECT_CONTEXT_FILES:
        entries.append(file_char_entry(rel, root / rel))
    if initiative_id:
        for rel in INITIATIVE_CONTEXT_FILES:
            entries.append(file_char_entry(f".aios/initiatives/{initiative_id}/{rel}", workspace / rel))
    else:
        for rel in COMPAT_CONTEXT_FILES:
            entries.append(file_char_entry(rel, root / rel))
    entries.append(file_char_entry("task_graph.json", task_graph_path(config), required=True))
    return entries


def source_tree_summary(config: dict[str, Any]) -> dict[str, Any]:
    root = source_dir(config)
    excluded = {".git", ".aios", "node_modules", "dist", "build", "__pycache__", ".venv", "venv"}
    file_count = 0
    total_bytes = 0
    top_extensions: dict[str, dict[str, int]] = {}
    largest: list[dict[str, Any]] = []
    if not root.exists():
        return {"root": str(root), "exists": False, "file_count": 0, "total_bytes": 0, "top_extensions": [], "largest_files": []}
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [item for item in dirs if item not in excluded]
        current = Path(current_root)
        for name in files:
            path = current / name
            try:
                stat = path.stat()
            except OSError:
                continue
            file_count += 1
            total_bytes += stat.st_size
            suffix = path.suffix.lower() or "[no_ext]"
            item = top_extensions.setdefault(suffix, {"files": 0, "bytes": 0})
            item["files"] += 1
            item["bytes"] += stat.st_size
            rel = path.relative_to(root).as_posix()
            largest.append({"path": rel, "bytes": stat.st_size})
    return {
        "root": str(root),
        "exists": True,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "top_extensions": sorted(
            [{"extension": ext, **data} for ext, data in top_extensions.items()],
            key=lambda item: int(item.get("bytes", 0)),
            reverse=True,
        )[:12],
        "largest_files": sorted(largest, key=lambda item: int(item.get("bytes", 0)), reverse=True)[:12],
    }


def build_planning_gate(
    config: dict[str, Any],
    startup_chars: int,
    material_chars: int,
    project_context_chars: int,
    source_summary: dict[str, Any],
    material_exists: bool,
) -> dict[str, Any]:
    budget = planning_context_budget(config)
    candidate_chars = startup_chars + material_chars + project_context_chars
    file_count = int(source_summary.get("file_count", 0) or 0)
    total_bytes = int(source_summary.get("total_bytes", 0) or 0)
    status = "ok"
    reasons: list[str] = []
    required_actions: list[str] = []

    if candidate_chars >= budget:
        status = "blocked"
        reasons.append(f"初始化候选上下文 {candidate_chars} 字符超过规划预算 {budget} 字符")
        required_actions.append("先生成 source_material_summary.md、requirements_index.md、decision_log.md，再进入项目级规划。")
    elif candidate_chars >= int(budget * PROMPT_WARNING_RATIO):
        status = "warning"
        reasons.append(f"初始化候选上下文接近规划预算：{candidate_chars}/{budget} 字符")
        required_actions.append("规划时只读取摘要和索引，避免把原始材料全文和所有 AIOS 文档一起塞入 prompt。")

    if material_chars >= int(budget * 0.5):
        status = "blocked" if material_chars >= budget else ("warning" if status == "ok" else status)
        reasons.append("原始材料/聊天记录过大，不能直接作为项目规划 prompt 的主体。")
        required_actions.append("先对聊天记录分段摘要，抽取目标、约束、争议、决策和未决问题。")

    if project_context_chars >= int(budget * 0.5):
        status = "warning" if status == "ok" else status
        reasons.append("已冻结项目上下文较大，规划新模块前应先选 active initiative。")
        required_actions.append("只展开当前 initiative 相关的 goal/requirements/spec/checks，其余保留路径索引。")

    if file_count >= SOURCE_TREE_DANGER_FILES or total_bytes >= SOURCE_TREE_DANGER_BYTES:
        status = "blocked"
        reasons.append("源码树很大，初始化阶段禁止全文读取源码。")
        required_actions.append("先只读目录树、配置、入口文件、测试索引和模块边界，再按模块逐步深入。")
    elif file_count >= SOURCE_TREE_WARNING_FILES or total_bytes >= SOURCE_TREE_WARNING_BYTES:
        status = "warning" if status == "ok" else status
        reasons.append("源码树偏大，扫描源码时需要分层抽样，不应全文读取。")
        required_actions.append("先生成 source_tree_index.md 和 module_candidates.md，再确认模块边界。")

    if not required_actions:
        required_actions.append("可以进入项目级规划，但仍应先读目录树/摘要，再按模块补充源码细节。")

    return {
        "status": status,
        "planning_context_budget_chars": budget,
        "candidate_chars": candidate_chars,
        "estimated_candidate_tokens": estimate_tokens(candidate_chars),
        "full_material_read_allowed": material_exists and status == "ok" and material_chars < int(budget * 0.5),
        "full_source_read_allowed": False,
        "module_freeze_allowed": status != "blocked",
        "reasons": reasons,
        "required_actions": required_actions,
        "safe_initialization_order": [
            "绑定 project_mode、target_source_dir/source_code_dir、source_material_file。",
            "运行上下文体检并向用户报告规划闸门结果。",
            "只读取源码目录树、配置、入口文件和必要 README，不全文读取源码。",
            "如果原始材料过大，先生成摘要、需求索引、决策日志和未决问题清单。",
            "先冻结 project_overview/module_map/pipeline_map/initiative_index。",
            "选择一个 active initiative 后，再逐层确认并冻结该 initiative 的目标、需求、规格、样例、流程、检查、验收。",
        ],
    }


def build_context_report(config: dict[str, Any]) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    docs_root = Path(__file__).resolve().parents[1]
    startup_docs = [
        docs_root / "AI项目操作系统总控入口.md",
        docs_root / "AIOS内核运行路线图.md",
        docs_root / "AI项目操作系统方法论.md",
        docs_root / "AI项目操作系统落地架构.md",
        docs_root / "AI项目操作系统项目设计.md",
    ]
    startup_entries = [file_char_entry(path.name, path, required=True) for path in startup_docs]
    all_markdown_paths = [repo_root / "README.md", *sorted(docs_root.glob("*.md"))]
    all_markdown_entries = [file_char_entry(path.relative_to(repo_root).as_posix(), path) for path in all_markdown_paths]
    project_entries = collect_context_entries(config)
    startup_chars = sum(int(item.get("chars", 0)) for item in startup_entries)
    all_docs_chars = sum(int(item.get("chars", 0)) for item in all_markdown_entries)
    project_context_chars = sum(int(item.get("chars", 0)) for item in project_entries)
    material = source_material_entry(config)
    material_chars = int(material.get("chars", 0)) if material else 0
    total_startup_candidate_chars = startup_chars + material_chars
    source_summary = source_tree_summary(config)
    material_exists = bool(material and material.get("exists"))
    planning_gate = build_planning_gate(config, startup_chars, material_chars, project_context_chars, source_summary, material_exists)
    warning_chars = STARTUP_CONTEXT_WARNING_CHARS
    danger_chars = STARTUP_CONTEXT_DANGER_CHARS
    warnings: list[str] = []
    if total_startup_candidate_chars >= warning_chars:
        warnings.append("启动必读文档 + 原始材料过大：应先摘要/索引，不要把聊天记录全文长期塞入每轮任务。")
    if material_chars >= warning_chars:
        warnings.append("source_material_file 很大：建议生成 source_material_summary.md、decision_log.md 和需求索引后再规划。")
    if project_context_chars >= warning_chars:
        warnings.append("已冻结项目/initiative 上下文较大：任务应使用 context_refs 精准引用，必要时拆 initiative。")
    source_file_count = int(source_summary.get("file_count", 0) or 0)
    source_total_bytes = int(source_summary.get("total_bytes", 0) or 0)
    if source_file_count >= SOURCE_TREE_WARNING_FILES or source_total_bytes >= SOURCE_TREE_WARNING_BYTES:
        warnings.append("源码树偏大：初始化阶段只允许目录树/入口/配置/测试索引级扫描，不允许全文读取源码。")
    return {
        "prompt_budget_chars": prompt_context_budget(config),
        "startup_warning_chars": warning_chars,
        "startup_danger_chars": danger_chars,
        "startup_required_docs": startup_entries,
        "startup_required_docs_chars": startup_chars,
        "all_aios_markdown": all_markdown_entries,
        "all_aios_markdown_chars": all_docs_chars,
        "source_material": material,
        "project_context_files": project_entries,
        "project_context_chars": project_context_chars,
        "total_startup_candidate_chars": total_startup_candidate_chars,
        "estimated_startup_tokens": estimate_tokens(total_startup_candidate_chars),
        "startup_severity": context_severity(total_startup_candidate_chars, warning_chars, danger_chars),
        "planning_gate": planning_gate,
        "source_tree": source_summary,
        "warnings": warnings,
        "policy": [
            "初始化/规划前先过 planning_gate；blocked 时不能继续冻结项目目标或模块目标。",
            "启动先统计，再决定读取策略；不要默认把源码、聊天记录和所有 MD 全文塞入同一轮。",
            "大材料先生成摘要、需求索引和决策日志；执行期只按当前任务 context_refs 精准展开。",
            "Worker prompt 超预算时优先缩小任务或补摘要，不靠模型在巨大上下文里自行搜索。",
        ],
    }


def show_context_report(config: dict[str, Any]) -> int:
    print(json.dumps(build_context_report(config), ensure_ascii=False, indent=2))
    return 0


def write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text_window(path: Path, max_chars: int = 40000) -> tuple[str, bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:max_chars], len(text) > max_chars


def first_nonempty_lines(text: str, limit: int = 80) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lines.append(stripped)
        if len(lines) >= limit:
            break
    return lines


def keyword_lines(text: str, keywords: list[str], limit: int = 120) -> list[str]:
    found: list[str] = []
    lower_keywords = [item.lower() for item in keywords]
    for line in text.splitlines():
        compact = line.strip()
        if not compact:
            continue
        lower = compact.lower()
        if any(keyword in lower for keyword in lower_keywords):
            found.append(compact[:300])
            if len(found) >= limit:
                break
    return found


def markdown_list(items: list[str], empty_text: str = "暂无自动提取项。") -> str:
    if not items:
        return f"- {empty_text}\n"
    return "".join(f"- {item}\n" for item in items)


def source_scan_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    root = source_dir(config)
    excluded = {".git", ".aios", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache"}
    entries: list[dict[str, Any]] = []
    if not root.exists():
        return entries
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [item for item in dirs if item not in excluded]
        current = Path(current_root)
        for name in files:
            path = current / name
            try:
                stat = path.stat()
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            entries.append({
                "path": rel,
                "bytes": stat.st_size,
                "extension": path.suffix.lower() or "[no_ext]",
                "sha256": sha256_file(path) if stat.st_size <= 2 * 1024 * 1024 else "skipped_large_file",
            })
    return sorted(entries, key=lambda item: str(item.get("path")))


def directory_tree_lines(entries: list[dict[str, Any]], limit: int = 2000) -> list[str]:
    lines: list[str] = []
    seen_dirs: set[str] = set()
    for entry in entries:
        rel = str(entry.get("path", ""))
        parts = rel.split("/")
        for depth in range(1, len(parts)):
            directory = "/".join(parts[:depth])
            if directory not in seen_dirs:
                seen_dirs.add(directory)
                lines.append("  " * (depth - 1) + parts[depth - 1] + "/")
        depth = len(parts) - 1
        lines.append("  " * depth + f"{parts[-1]} ({entry.get('bytes', 0)} bytes)")
        if len(lines) >= limit:
            lines.append("... [TRUNCATED]")
            break
    return lines


def likely_entrypoints(entries: list[dict[str, Any]]) -> list[str]:
    names = {
        "main.py", "app.py", "server.py", "manage.py", "index.js", "index.ts", "main.ts", "main.js", "app.ts", "app.js",
        "package.json", "pyproject.toml", "requirements.txt", "setup.py", "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
        "docker-compose.yml", "Dockerfile", "README.md", "readme.md",
    }
    result = []
    for entry in entries:
        rel = str(entry.get("path", ""))
        name = Path(rel).name
        if name in names or "/routes/" in f"/{rel}" or "/api/" in f"/{rel}" or "/tests/" in f"/{rel}"[:20]:
            result.append(rel)
        if len(result) >= 120:
            break
    return result


def module_candidates(entries: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for entry in entries:
        rel = str(entry.get("path", ""))
        parts = rel.split("/")
        key = parts[0] if len(parts) > 1 else "[root]"
        counts[key] = counts.get(key, 0) + 1
    return [f"{name}: {count} files" for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:80]]


def clean_ingest_and_source(config: dict[str, Any]) -> dict[str, Any]:
    root = source_dir(config)
    workspace = aios_dir(config)
    ingest_dir = workspace / "ingest"
    source_index_dir = workspace / "source"
    report = build_context_report(config)
    material_entry = report.get("source_material") or {}
    material_path = Path(str(material_entry.get("path") or "")) if material_entry else None
    generated: list[str] = []

    material_manifest: dict[str, Any] = {
        "time": now_iso(),
        "source_material_file": str(material_path) if material_path else "",
        "exists": bool(material_path and material_path.exists()),
        "chars": int(material_entry.get("chars", 0) or 0),
        "bytes": int(material_entry.get("bytes", 0) or 0),
        "sha256": "",
        "cleaning_policy": "原始材料不修改；清洗产物写入 .aios/ingest；大文件只摘取窗口和关键词索引。",
    }
    material_text = ""
    material_truncated = False
    if material_path and material_path.exists() and material_path.is_file():
        material_manifest["sha256"] = sha256_file(material_path)
        material_text, material_truncated = read_text_window(material_path)
    write_json(ingest_dir / "source_material_manifest.json", material_manifest)
    generated.append(str(ingest_dir / "source_material_manifest.json"))

    summary_lines = first_nonempty_lines(material_text, limit=60)
    write_text_file(
        ingest_dir / "source_material_summary.md",
        "# 原始材料清洗摘要\n\n"
        f"- 来源文件：`{material_manifest['source_material_file']}`\n"
        f"- SHA256：`{material_manifest['sha256'] or 'N/A'}`\n"
        f"- 原始字符数：{material_manifest['chars']}\n"
        f"- 本次清洗读取窗口：{len(material_text)} 字符\n"
        f"- 是否截断：{'是' if material_truncated else '否'}\n\n"
        "## 摘要候选\n\n"
        "以下为确定性抽取的前部有效行，不代表最终需求结论；新会话应基于它继续整理并向用户确认。\n\n"
        + markdown_list(summary_lines, "原始材料不存在或为空。"),
    )
    generated.append(str(ingest_dir / "source_material_summary.md"))

    requirement_hits = keyword_lines(material_text, ["需要", "需求", "必须", "希望", "支持", "实现", "用户", "业务", "流程", "模块"])
    decision_hits = keyword_lines(material_text, ["决定", "确认", "不要", "不做", "改成", "最终", "必须", "禁止", "只允许"])
    question_hits = keyword_lines(material_text, ["?", "？", "问题", "不确定", "是否", "怎么", "如何", "为什么"])
    conflict_hits = keyword_lines(material_text, ["但是", "冲突", "矛盾", "推翻", "不要", "不是", "改成", "之前"])

    for filename, title, items, empty in [
        ("requirements_index.md", "需求索引候选", requirement_hits, "未自动提取到需求关键词。"),
        ("decision_log.md", "决策日志候选", decision_hits, "未自动提取到决策关键词。"),
        ("open_questions.md", "未决问题候选", question_hits, "未自动提取到问题关键词。"),
        ("conflict_log.md", "冲突/变更线索候选", conflict_hits, "未自动提取到冲突关键词。"),
        ("out_of_scope.md", "不做/排除范围候选", keyword_lines(material_text, ["不做", "不要", "排除", "禁止", "不能", "不是"]), "未自动提取到排除范围关键词。"),
    ]:
        write_text_file(
            ingest_dir / filename,
            f"# {title}\n\n这些条目是清洗阶段的候选索引，不是冻结结论。正式规划前必须由用户确认。\n\n" + markdown_list(items, empty),
        )
        generated.append(str(ingest_dir / filename))

    entries = source_scan_entries(config)
    write_json(source_index_dir / "source_manifest.json", {"time": now_iso(), "root": str(root), "file_count": len(entries), "files": entries})
    generated.append(str(source_index_dir / "source_manifest.json"))
    write_text_file(source_index_dir / "source_tree.md", "# 源码目录索引\n\n源码未被修改；本文件只记录目录和文件大小。\n\n```text\n" + "\n".join(directory_tree_lines(entries)) + "\n```\n")
    generated.append(str(source_index_dir / "source_tree.md"))
    write_text_file(source_index_dir / "entrypoints.md", "# 入口和关键文件候选\n\n" + markdown_list(likely_entrypoints(entries), "未自动识别入口文件。"))
    generated.append(str(source_index_dir / "entrypoints.md"))
    write_text_file(source_index_dir / "module_candidates.md", "# 模块候选\n\n基于顶层目录和文件数量推断，必须由用户确认。\n\n" + markdown_list(module_candidates(entries), "未自动识别模块候选。"))
    generated.append(str(source_index_dir / "module_candidates.md"))
    write_text_file(source_index_dir / "dependency_map.md", "# 依赖关系草案\n\n清洗阶段不全文分析源码，因此这里只保留待确认占位。后续应基于入口文件、配置和用户确认逐步补全。\n")
    generated.append(str(source_index_dir / "dependency_map.md"))
    write_text_file(source_index_dir / "source_scan_report.md", "# 源码扫描报告\n\n- 源码目录：`" + str(root) + "`\n- 扫描文件数：" + str(len(entries)) + "\n- 源码未修改：是\n- 排除目录：`.git`, `.aios`, `node_modules`, `dist`, `build`, 缓存和虚拟环境\n- 全文读取源码：否\n")
    generated.append(str(source_index_dir / "source_scan_report.md"))

    bootstrap = (
        "# 清洗后新会话启动说明\n\n"
        "清洗阶段已完成。为了避免当前会话已经读入的大材料污染后续判断，建议退出当前 Codex 会话，重新开启新会话。\n\n"
        "## 新会话只读取这些文件\n\n"
        "```text\n"
        ".aios/ingest/source_material_manifest.json\n"
        ".aios/ingest/source_material_summary.md\n"
        ".aios/ingest/requirements_index.md\n"
        ".aios/ingest/decision_log.md\n"
        ".aios/ingest/open_questions.md\n"
        ".aios/ingest/conflict_log.md\n"
        ".aios/ingest/out_of_scope.md\n"
        ".aios/source/source_tree.md\n"
        ".aios/source/source_manifest.json\n"
        ".aios/source/entrypoints.md\n"
        ".aios/source/module_candidates.md\n"
        ".aios/source/source_scan_report.md\n"
        "```\n\n"
        "## 新会话不要做\n\n"
        "```text\n"
        "不要默认读取原始聊天记录全文。\n"
        "不要全文读取源码树。\n"
        "不要在未确认清洗结果前冻结项目目标、模块目标或 initiative 目标。\n"
        "```\n"
    )
    write_text_file(ingest_dir / "bootstrap_readme.md", bootstrap)
    generated.append(str(ingest_dir / "bootstrap_readme.md"))

    update_state(config, "RESTART_REQUIRED", "cleaning_done", cleaning_generated=generated, bootstrap_readme=str(ingest_dir / "bootstrap_readme.md"))
    return {
        "status": "cleaning_done",
        "restart_required": True,
        "message": "清洗产物已生成；建议退出当前 Codex，新会话只读取 bootstrap_readme 指定的清洗产物。",
        "generated_files": generated,
        "bootstrap_readme": str(ingest_dir / "bootstrap_readme.md"),
        "source_modified": False,
        "source_material_modified": False,
        "planning_gate": report.get("planning_gate"),
    }


def show_clean_report(config: dict[str, Any]) -> int:
    print(json.dumps(clean_ingest_and_source(config), ensure_ascii=False, indent=2))
    return 0


def show_status(config: dict[str, Any]) -> int:
    ensure_reference_dirs_readonly_boundary(config)
    graph = load_task_graph(config)
    state = load_state(config)
    tasks = graph.get("tasks", [])
    print(json.dumps({"state": state, "tasks": tasks, "summary": status_summary(tasks, state)}, ensure_ascii=False, indent=2))
    return 0


def validate(config: dict[str, Any]) -> int:
    graph = load_task_graph(config)
    ids = set()
    errors = []
    try:
        ensure_reference_dirs_readonly_boundary(config)
    except RuntimeError as exc:
        errors.append(str(exc))
    for task in graph.get("tasks", []):
        task_id = task.get("task_id")
        if not task_id:
            errors.append("task without task_id")
            continue
        if task_id in ids:
            errors.append(f"duplicate task_id: {task_id}")
        ids.add(task_id)
        if not task_has_reproducible_evidence_spec(task):
            errors.append(
                f"task {task_id} lacks reproducible blocking evidence: add success_checks or structured expected_outputs with content_contains/min_size/sha256"
            )
    for task in graph.get("tasks", []):
        for dep in task.get("dependencies", []):
            if dep not in ids:
                errors.append(f"task {task.get('task_id')} has missing dependency {dep}")
    result = {"valid": not errors, "errors": errors, "task_count": len(graph.get("tasks", []))}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def reset_execution_state(config: dict[str, Any]) -> int:
    workspace = active_workspace_dir(config)
    graph = load_task_graph(config)
    for task in graph.get("tasks", []):
        task["status"] = "pending"
        for key in ["attempts", "started_at", "finished_at", "last_run", "last_error", "manual_note", "blocked_reason", "duration_seconds"]:
            task.pop(key, None)
    graph.get("root_task", {})["status"] = "pending"
    save_task_graph(config, graph)

    for folder in [runs_dir(config), reports_dir(config)]:
        if folder.exists():
            for child in folder.iterdir():
                if child.is_dir():
                    import shutil
                    shutil.rmtree(child)
                else:
                    child.unlink()
        folder.mkdir(parents=True, exist_ok=True)

    state = {
        "phase": "READY_TO_EXECUTE",
        "status": "reset_done",
        "iteration": 0,
        "history": [{"time": now_iso(), "phase": "READY_TO_EXECUTE", "status": "reset_done", "note": "run logs and task status cleared; source and frozen AIOS docs kept"}],
    }
    save_state(config, state)
    print(json.dumps({"workspace": str(workspace), "status": "reset_done"}, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AIOS task graph with Codex Worker")
    parser.add_argument("--config", default=None, help="Path to aios_config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_parser = sub.add_parser("run", help="Run ready tasks until done, failed, blocked, high-risk, or max steps")
    run_parser.add_argument("--max-steps", type=int, default=None, help="Maximum tasks to run in this command")
    run_next_parser = sub.add_parser("run-next", help="Run next ready task")
    run_next_parser.add_argument("--dry-run", action="store_true", help="Only write the Codex prompt")
    sub.add_parser("status", help="Show state and tasks")
    sub.add_parser("context", help="Show startup and prompt context size report")
    sub.add_parser("clean", help="Generate ingest/source cleaning artifacts before planning")
    sub.add_parser("validate", help="Validate task graph")
    sub.add_parser("reset", help="Reset run logs, reports, task statuses, and active workspace state")
    args = parser.parse_args()

    config = load_config(args.config) if args.config else load_config()
    if args.cmd == "run":
        raise SystemExit(run_auto(config, max_steps=args.max_steps))
    if args.cmd == "run-next":
        raise SystemExit(run_next(config, dry_run=args.dry_run))
    if args.cmd == "status":
        raise SystemExit(show_status(config))
    if args.cmd == "context":
        raise SystemExit(show_context_report(config))
    if args.cmd == "clean":
        raise SystemExit(show_clean_report(config))
    if args.cmd == "validate":
        raise SystemExit(validate(config))
    if args.cmd == "reset":
        raise SystemExit(reset_execution_state(config))


if __name__ == "__main__":
    main()
