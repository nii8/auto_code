# AI 项目操作系统落地架构

> 目的：把“AI 项目操作系统方法论”落地成一个可执行的 CLI / Python 自动化工具，通过文档、LLM、Codex、检查器、状态机共同推进复杂项目。

## 零、运行时可信度原则

AIOS 运行时的可信度来自证据链，而不是来自 AI 的完成感。

执行链路必须分层：

```text
Codex Worker：负责实现、局部自检、普通代码错误修复。
Runner：负责调度任务、保存日志、运行检查、判断是否允许进入下一任务。
Checker：负责确定性验证、端到端验证、负向验证和报告扫描。
Human Gate：负责目标冲突、高风险操作、连续失败和主观验收判断。
```

责任边界：

```text
Worker 可以说“我认为完成”。
Checker 才能证明“检查通过”。
Runner 才能把任务状态改为 done。
用户只需要处理目标取舍、高风险授权和最终主观验收，不应该被迫调普通代码错误。
```

运行前必须做依赖预检。普通低风险依赖应尽量自动安装；系统级依赖、全局环境变更、密钥、账号、付费资源必须进入 Human Gate。

运行后必须保存证据：

```text
<workspace>/runs/      每次任务运行、Codex 输出、检查结果、错误日志
<workspace>/reports/   阶段报告、最终验证报告、未验证项说明
可选截图/图片    浏览器截图、生成图片、视觉检查输入
```

复杂项目的 `<workspace>` 通常是 `.aios/initiatives/<id>/`；单 initiative 兼容模式下是顶层 `.aios/`。

## 零点五、当前执行策略：只串行，不并发

AIOS 当前阶段明确不做并发执行。

```text
不启动多个 Codex Worker 同时写代码。
不做文件锁并发。
不做 git worktree 并发。
不做自动合并并发分支。
```

原因：当前最重要的是目标冻结、任务拆解、证据闸门、自动修复和验收可信度。并发会引入锁、冲突检测、合并、回滚和集成复杂度，当前收益小于风险。

当前 Runner 应保持：

```text
一个 active initiative
一个 task_graph
一个任务接一个任务串行执行
失败先自动 repair，超过限制再 Human Gate
```

`dependencies` 和 `write_scope` 仍然保留，但用途是任务边界、写入限制、审查和未来扩展，不用于当前并发调度。

## 一、核心理解

这个方向不是“越狱”或绕过安全限制，而是：**在安全边界内，把 Codex、LLM、Python、文档、检查器、状态机组织起来，让项目自动推进。**

整体框架：

```text
项目目标
↓
提前写好的规则 / 样例 / 流程 / 验收文档
↓
Python 总控读取这些文档
↓
Python 调 LLM 做规划和决策
↓
Python 调 Codex 执行代码 / 文件任务
↓
Python 收集 Codex 输出、中间产物、检查结果
↓
LLM 判断下一步
↓
循环，直到达到目标或触发熔断
```

这可以理解为一个“项目级自动驾驶”。

## 二、本机 Codex CLI 调用方式

非交互执行应使用：

```bash
codex exec "帮我执行一个任务"
```

常用能力：

```bash
codex exec --json "任务"
codex exec -o last_message.txt "任务"
codex exec --output-schema schema.json "任务"
codex exec resume --last "继续刚才任务"
```

Python 可以通过 `subprocess.run()` 调用 Codex。

## 三、建议架构：七个模块

### 1. Project Context：项目上下文包

每个项目都必须有一个上下文目录，例如：

```text
.aios/
  00_goal.md
  01_requirements.md
  02_acceptance.md
  03_examples.md
  04_workflow.md
  05_tools.md
  06_constraints.md
  07_decisions.md
  08_state.json
  09_run_log.md
```

各文件作用：

```text
00_goal.md          目标是什么
01_requirements.md  需求和非需求
02_acceptance.md    验收标准
03_examples.md      正例、反例、边界例
04_workflow.md      标准流程
05_tools.md         可以调用哪些工具
06_constraints.md   递归次数、时间、预算、安全边界
07_decisions.md     历史决策
08_state.json       当前跑到哪一步
09_run_log.md       每轮做了什么
```

这是整个系统的“长期记忆”。

### 2. Orchestrator：Python 总控

Python 不直接做所有事情，而是当调度器。

它负责：

```text
读取项目文档
维护状态
决定下一步
调用 LLM
调用 Codex
调用检查器
保存中间产物
判断是否继续
触发熔断
生成报告
```

伪代码：

```python
while not done:
    context = load_project_context()
    state = load_state()

    decision = ask_planner_llm(context, state)

    if decision.action == "run_codex":
        result = run_codex(decision.prompt)

    elif decision.action == "run_checker":
        result = run_checker(decision.checker)

    elif decision.action == "ask_user":
        stop_and_report(decision.question)

    update_state(result)

    if should_stop(state):
        break
```

### 3. Planner LLM：决策脑

例如接入 `qwen3.6-plus`，可以作为 Planner。

Planner 不直接乱改文件，而是输出结构化决策。任务图字段、`success_checks`、`expected_outputs`、`context_refs` 和证据等级的详细 schema 以 `AI项目操作系统项目设计.md` 为准。

Planner 的关键是：**必须结构化输出，不允许自由发挥**；最好用 JSON Schema 约束。

### 4. Codex Worker：执行工人

Codex 适合做：

```text
读代码
改代码
写测试
跑命令
修 bug
生成文件
重构模块
```

Python 调用示例：

```python
import subprocess


def run_codex(prompt, cwd):
    result = subprocess.run(
        [
            "codex", "exec",
            "--json",
            "--cd", cwd,
            "--sandbox", "workspace-write",
            "--ask-for-approval", "never",
            prompt,
        ],
        text=True,
        capture_output=True,
        timeout=3600,
    )
    return result.stdout, result.stderr, result.returncode
```

也可以把最后回复写入文件：

```bash
codex exec -o <workspace>/runs/001_last_message.md "执行任务..."
```

如果要多轮，可以用：

```bash
codex exec resume --last "继续刚才任务，修复测试失败"
```

但早期不建议太依赖多轮 `resume`，优先使用：

```text
单轮任务 + 状态文件
```

这样更可控。

### 5. Checkers：确定性检查器

不要让 LLM 判断所有事情。

应该有很多小检查器：

```text
check_files_exist.py
check_tests_pass.py
check_no_large_diff.py
check_no_forbidden_delete.py
check_output_schema.py
check_acceptance.py
check_run_time.py
```

通用检查结果统一成：

```json
{
  "checker": "check_tests_pass",
  "status": "fail",
  "evidence": "2 tests failed",
  "details": "...",
  "blocking": true
}
```

LLM 看到这个再决定下一步。

### 6. State Machine：状态机

不要让系统无限循环。

状态应该很明确：

```text
INIT
↓
UNDERSTAND
↓
PLAN
↓
IMPLEMENT
↓
CHECK
↓
REPAIR
↓
REVIEW
↓
DONE / BLOCKED / FAILED
```

每个状态最多循环几次。

示例：

```json
{
  "phase": "REPAIR",
  "iteration": 3,
  "max_iterations": 5,
  "last_action": "run_codex",
  "last_result": "tests_failed",
  "status": "running"
}
```

如果超过限制：

```text
触发熔断
停止自动执行
输出需要人类决策的问题
```

### 7. Human Gate：人工闸门

不是所有事情都自动做。

这些必须停下来问用户：

```text
删除源码
大范围重构
修改核心规则
超过预算
连续失败
验收标准冲突
多个方案取舍
外部发布 / 上传
```

也就是说，自动化不是“完全无人驾驶”，而是：

```text
低风险自动执行
中风险自动建议
高风险人工确认
```

## 四、关于多轮对话

Python 实现“多轮对话”有三种方式。

### 方式 A：自己维护上下文

最推荐。

Python 把历史状态写入当前 workspace 的 `state.json` 和 `runs/`，每次调用 LLM / Codex 时，把必要上下文重新拼进去。

优点：

```text
可控
不怕上下文污染
可复现
易调试
```

### 方式 B：Codex resume

可以用：

```bash
codex exec resume --last "继续..."
```

优点：

```text
简单
保留 Codex 会话上下文
```

缺点：

```text
容易上下文污染
不容易复现
对自动系统不够透明
```

### 方式 C：混合模式

建议未来采用：

```text
Planner 自己维护状态
Codex Worker 尽量单轮执行
特殊调试时才 resume
```

## 五、分三代实现

不要一开始做“万能自动达成目标”。

### 第一代：半自动项目驾驶

目标：减少用户拉扯。

功能：

```text
读取项目文档
生成计划
调用 Codex 执行一个明确任务
跑检查器
生成报告
失败则给出下一步建议
```

人类仍然确认关键步骤。

这已经能解决大部分痛苦。

### 第二代：自动循环修复

增加：

```text
最多自动修复 N 次
每次修复必须基于检查证据
超过 N 次熔断
自动写决策日志
自动更新状态
```

### 第三代：多 Agent 项目操作系统

再增加：

```text
Planner
Implementer
Reviewer
Tester
Critic
Summarizer
```

但每个 Agent 都必须通过文件和 JSON 交接，不能只靠聊天。

否则 Agent 越多越乱。

## 六、关键设计原则

### 1. 文件是事实，聊天是临时

系统必须以文件为准：

```text
目标文件
规则文件
状态文件
检查报告
中间产物
最终报告
```

不要相信模型“记得”。

### 2. Planner 不直接改文件

职责分离：

```text
Planner 负责决策
Codex 负责执行
Checker 负责验证
用户负责验收
```

角色不要混。

### 3. 每一步都要有证据

禁止这种：

```text
我觉得已经好了。
```

必须是：

```text
检查项 A 通过。
测试 B 通过。
输出文件存在。
差异如下。
风险如下。
```

### 4. 自动化必须有刹车

递归步数限制很重要：

```json
{
  "max_total_steps": 20,
  "max_repair_attempts": 3,
  "max_runtime_minutes": 60,
  "max_cost_usd": 5,
  "stop_on_destructive_action": true
}
```

### 5. 所有任务必须分风险等级

```text
low：读文件、生成报告、跑测试
medium：改普通代码、生成中间文件
high：删除文件、大范围重构、发布、上传、修改规则
```

高风险必须人工确认。

## 七、一个可能的 CLI 形态

未来可以做一个命令：

```bash
aios run --project /path/to/project --goal "生成短视频 Story 模式并通过验收"
```

或者：

```bash
aios run task.md
```

`task.md` 示例：

```markdown
# 本轮任务

目标：生成一条 90 秒短视频。

输入：
- data/xxx.mp4
- data/xxx.srt

验收：
- 观点闭环
- 5~8 段
- 不频繁跳切
- 有 hook 和结论

限制：
- 最多自动修复 3 次
- 不允许删除源码
- 需要上传前人工确认
```

系统自动跑：

```text
读取 docs
规划
执行
检查
修复
报告
```

## 八、最小可实现版本

可以先实现一个用户友好的简化入口 `aios.py`，底层调用通用 Runner `aios_docs/tools/aios_runner.py`：

```text
.aios/
  goal.md
  workflow.md
  acceptance.md
  examples.md
  state.json
  tasks/task_graph.json
  runs/
```

第一版只支持：

```bash
python3 aios.py
```

配套命令：

```bash
python3 aios.py          # 自动推进，直到完成 / 失败 / 需要确认
python3 aios.py status   # 查看进度
python3 aios.py preview  # 预览下一步
python3 aios.py next     # 只执行一步
python3 aios.py check    # 检查任务图
```

第一代半自动项目驾驶不是“每一步都让用户手动敲命令”。默认应自动连续推进低风险和中风险任务；只有失败、高风险、检查不通过、连续修复超过限制、任务依赖不清或需要用户验收取舍时，才触发 Human Gate。

内部做：

```text
1. 读取 .aios 文档
2. 让 qwen 输出计划 JSON
3. 调 codex exec 执行
4. 保存输出
5. 跑检查命令
6. 生成报告
```

Runner 应保持通用：项目差异只来自 `aios_config.yaml` 和项目自己的 `.aios/` 文件。换项目时不应重写 Runner，只需修改配置、重新初始化并生成新的任务图。

不要一开始做复杂。

## 九、关于“自动达到最后目标”

这个愿景可以有，但不要一开始假设它能 100% 自动达成。

更现实的目标是：

```text
自动推进 70%
自动暴露问题 20%
剩下 10% 让用户做关键决策
```

这已经比纯聊天强很多。

如果追求 100% 自动，反而容易变成新的失控系统。

## 十、最终判断

这个方向是成立的。

它本质是：

```text
文档化上下文
状态机调度
LLM 决策
Codex 执行
程序化检查
递归修复
人工闸门
```

这就是一个通用的 AI 项目操作系统。

最重要的不是“让 Codex 无限自动跑”，而是：

```text
让 Codex 每一步都在目标、规则、样例、验收、限制、状态机里面跑。
```

否则 token 再多，也只是更大规模的混乱。
