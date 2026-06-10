#!/usr/bin/env python3
"""Minimal AIOS runner.

Generic runner for any project configured by aios_config.yaml. It loads the
project's .aios task graph, runs one ready task through Codex Worker, stores
logs, runs deterministic checks, and updates task/state files.
"""

from __future__ import annotations

import argparse
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


TERMINAL_STATUSES = {"done", "failed", "blocked", "skipped_with_reason", "needs_human"}
READY_STATUSES = {"pending", "failed"}
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


def active_initiative_id(config: dict[str, Any]) -> str:
    configured = str(config.get("active_initiative") or "").strip()
    if configured:
        return validate_initiative_id(configured)
    global_state_path = aios_dir(config) / "global_state.json"
    if global_state_path.exists():
        try:
            state = load_json(global_state_path)
        except Exception:
            return ""
        return validate_initiative_id(str(state.get("active_initiative") or "").strip())
    return ""


def validate_initiative_id(value: str) -> str:
    if not value:
        return ""
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "/" in value or "\\" in value:
        raise RuntimeError("active_initiative must be a directory name, not a path")
    return value


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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(config: dict[str, Any]) -> dict[str, Any]:
    path = state_path(config)
    if not path.exists():
        return {"phase": "BOOTSTRAP", "status": "initialized", "iteration": 0, "history": []}
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


def read_if_exists(path: Path, max_chars: int = 12000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]\n"
    return text


def build_prompt(config: dict[str, Any], task: dict[str, Any]) -> str:
    root = source_dir(config)
    refs = reference_source_dirs(config)
    project_mode = str(config.get("project_mode") or "未配置")
    initiative_id = active_initiative_id(config)
    workspace = active_workspace_dir(config)
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
    for rel in PROJECT_CONTEXT_FILES:
        text = read_if_exists(root / rel)
        if text:
            parts.extend([f"\n## {rel}", text])
    parts.append("\n# 当前目标冻结上下文")
    if initiative_id:
        for rel in INITIATIVE_CONTEXT_FILES:
            text = read_if_exists(workspace / rel)
            if text:
                parts.extend([f"\n## .aios/initiatives/{initiative_id}/{rel}", text])
    else:
        for rel in COMPAT_CONTEXT_FILES:
            text = read_if_exists(root / rel)
            if text:
                parts.extend([f"\n## {rel}", text])
    return "\n".join(parts)


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


def run_shell_check(config: dict[str, Any], command: str) -> dict[str, Any]:
    original_command = command
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
        "original_command": original_command,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "passed": completed.returncode == 0,
    }


def shutil_which(command: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(directory) / command
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return None


def run_task_checks(config: dict[str, Any], task: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    for command in task.get("success_checks", []) or []:
        checks.append(run_shell_check(config, str(command)))
    return checks


def validate_expected_outputs(config: dict[str, Any], task: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    root = source_dir(config)
    for rel in task.get("expected_outputs", []) or []:
        path = root / str(rel)
        checks.append({
            "checker": "expected_output_exists",
            "path": str(path),
            "passed": path.exists(),
            "blocking": True,
            "evidence": "exists" if path.exists() else "missing",
        })
    return checks


def validate_report_content(config: dict[str, Any], task: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for rel in task.get("expected_outputs", []) or []:
        rel_text = str(rel)
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
            "evidence": evidence,
        })
    return checks


def write_run_artifacts(config: dict[str, Any], task: dict[str, Any], prompt: str, result: dict[str, Any], checks: list[dict[str, Any]]) -> Path:
    run_id = f"{now_stamp()}_{task.get('task_id', 'task')}"
    path = runs_dir(config) / f"{run_id}.json"
    payload = {
        "run_id": run_id,
        "time": now_iso(),
        "task_id": task.get("task_id"),
        "task_title": task.get("title"),
        "prompt": prompt,
        "codex_result": result,
        "checks": checks,
    }
    write_json(path, payload)
    latest = runs_dir(config) / "latest_run.json"
    write_json(latest, payload)
    return path


def run_next(config: dict[str, Any], dry_run: bool = False) -> int:
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

    prompt = build_prompt(config, task)
    if dry_run:
        path = runs_dir(config) / f"{now_stamp()}_{task.get('task_id')}_prompt.md"
        path.write_text(prompt, encoding="utf-8")
        update_state(config, "EXECUTE_TASK", "dry_run", current_task_id=task.get("task_id"), prompt_path=str(path))
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

    result = run_codex(config, prompt)
    checks = []
    if result["returncode"] == 0:
        checks.extend(run_task_checks(config, task))
        checks.extend(validate_expected_outputs(config, task))
        checks.extend(validate_report_content(config, task))
    artifact_path = write_run_artifacts(config, task, prompt, result, checks)
    checks_passed = all(check.get("passed") for check in checks) if checks else True

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


def show_status(config: dict[str, Any]) -> int:
    graph = load_task_graph(config)
    state = load_state(config)
    print(json.dumps({"state": state, "tasks": graph.get("tasks", [])}, ensure_ascii=False, indent=2))
    return 0


def validate(config: dict[str, Any]) -> int:
    graph = load_task_graph(config)
    ids = set()
    errors = []
    for task in graph.get("tasks", []):
        task_id = task.get("task_id")
        if not task_id:
            errors.append("task without task_id")
            continue
        if task_id in ids:
            errors.append(f"duplicate task_id: {task_id}")
        ids.add(task_id)
    for task in graph.get("tasks", []):
        for dep in task.get("dependencies", []):
            if dep not in ids:
                errors.append(f"task {task.get('task_id')} has missing dependency {dep}")
    result = {"valid": not errors, "errors": errors, "task_count": len(graph.get("tasks", []))}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AIOS task graph with Codex Worker")
    parser.add_argument("--config", default=None, help="Path to aios_config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_parser = sub.add_parser("run", help="Run ready tasks until done, failed, blocked, high-risk, or max steps")
    run_parser.add_argument("--max-steps", type=int, default=None, help="Maximum tasks to run in this command")
    run_next_parser = sub.add_parser("run-next", help="Run next ready task")
    run_next_parser.add_argument("--dry-run", action="store_true", help="Only write the Codex prompt")
    sub.add_parser("status", help="Show state and tasks")
    sub.add_parser("validate", help="Validate task graph")
    args = parser.parse_args()

    config = load_config(args.config) if args.config else load_config()
    if args.cmd == "run":
        raise SystemExit(run_auto(config, max_steps=args.max_steps))
    if args.cmd == "run-next":
        raise SystemExit(run_next(config, dry_run=args.dry_run))
    if args.cmd == "status":
        raise SystemExit(show_status(config))
    if args.cmd == "validate":
        raise SystemExit(validate(config))


if __name__ == "__main__":
    main()
