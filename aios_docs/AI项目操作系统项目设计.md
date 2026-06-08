# AI 项目操作系统项目设计

> 目的：设计一个通用 AI 项目操作系统，把混乱的原始文本、聊天记录、录音转写、需求碎片，转化为可执行、可检查、可递归推进的项目上下文与任务系统。

## 一、核心理解

这个项目要做的是一个 **AIOS 项目初始化器 + 项目执行调度器**。

输入是一个原始 MD 长文本，里面可能包含：

```text
聊天记录
录音转写
会议纪要
用户随手想法
失败经验
成功样例
项目背景
旧方案
新方案
```

系统要做的不是马上执行任务，而是先把这些混乱信息整理成一个可执行的项目操作系统。

整体流程：

```text
一个原始 MD 长文本
↓
LLM 读取、理解、提炼
↓
自动生成项目操作系统所需的上下文文件
↓
形成目标、规格、样例、流程、检查、验收、状态机、任务图
↓
后续 AI / Codex / Python / 外部工具按这些文件自动推进项目
```

## 二、关键修正：不能一步到位

原始想法可能是：

```text
原始输入文件
↓
LLM 直接生成目标、规格、样例、流程、检查、验收
```

这个有风险。

风险是：**LLM 可能从原始材料里误读目标、误提炼规则、误判断用户痛点。**

所以不能让 LLM 一步到位直接生成最终项目文件。

这里的“不能一步到位”不是只禁止一次性生成最终文件，也禁止一次性让用户打包确认多个层级。

AIOS 的底层确认协议是：

```text
目标层单独确认
↓
需求 / 非需求层单独确认
↓
规格层单独确认
↓
样例层单独确认
↓
流程层单独确认
↓
检查层单独确认
↓
验收层单独确认
↓
任务拆解请求单独确认
```

任何一层没有确认，都不能自动跳到下一层；任何一次用户确认，都只对当前层有效。

应该改成：

```text
原始输入
↓
证据提取层
↓
候选项目理解
↓
用户确认 / 自动置信度判断
↓
正式生成项目操作系统文件
```

第一步不是“生成目标”，而是先生成：

```text
这个原始文件里到底有哪些事实？
用户反复说了什么？
哪些是明确需求？
哪些只是情绪表达？
哪些是失败经验？
哪些是成功样例？
哪些是 AI 推测？
哪些需要用户确认？
```

这是整个系统稳定的基础。

## 三、推荐总流程

整个系统分成 8 个阶段。

```text
0. 创建项目空间
1. 读取原始输入
2. 提取证据
3. 生成候选理解
4. 逐层生成人类可确认的项目草案
5. 逐层冻结项目文件
6. 建立任务图和状态机
7. 自动执行 / 检查 / 修复
8. 验收 / 复盘 / 沉淀
```

阶段 4 和阶段 5 必须交替进行，不能先把所有草案都生成完再让用户一次性确认。

正确节奏是：

```text
生成目标草案 → 用户确认 → 冻结目标
生成需求草案 → 用户确认 → 冻结需求
生成规格草案 → 用户确认 → 冻结规格
生成样例草案 → 用户确认 → 冻结样例
生成流程草案 → 用户确认 → 冻结流程
生成检查草案 → 用户确认 → 冻结检查
生成验收草案 → 用户确认 → 冻结验收
```

## 四、阶段 0：创建项目空间

每个项目创建一个目录：

```text
.aios/
  source/
  evidence/
  context/
  workflow/
  checks/
  tasks/
  runs/
  reports/
  state.json
```

建议结构：

```text
.aios/
  source/
    initial_input.md

  evidence/
    facts.md
    pain_points.md
    user_needs.md
    success_examples.md
    failure_examples.md
    open_questions.md
    assumptions.md

  context/
    00_project_goal.md
    01_requirements.md
    02_specifications.md
    03_examples.md
    04_acceptance.md
    05_constraints.md
    06_glossary.md

  workflow/
    00_overall_workflow.md
    01_task_decomposition.md
    02_execution_policy.md
    03_review_policy.md
    04_human_gate_policy.md

  checks/
    deterministic_checks.md
    llm_judgment_checks.md
    check_registry.json

  tasks/
    task_decomposition_request.md
    task_graph.md
    task_graph.json
    current_task.md
    blocked_tasks.md

  runs/
    run_log.md
    codex_calls/
    llm_calls/
    artifacts/

  reports/
    latest_report.md
    final_report.md

  state.json
```

这就是项目的“外部大脑”。

## 五、阶段 1：读取原始输入

原始输入统一放到：

```text
.aios/source/initial_input.md
```

但系统不能假设它是干净的。

它可能包含：

```text
重复
情绪
错别字
口语
前后矛盾
用户临时想法
旧方案
废弃方案
真正重要的经验
```

所以后面必须先做“证据提取”。

## 六、阶段 2：证据提取层

不要直接生成目标，而是先生成这些文件：

```text
.aios/evidence/facts.md
.aios/evidence/pain_points.md
.aios/evidence/user_needs.md
.aios/evidence/success_examples.md
.aios/evidence/failure_examples.md
.aios/evidence/open_questions.md
.aios/evidence/assumptions.md
```

每一条最好带来源引用，例如：

```text
证据 ID：E-023
来源：initial_input.md 第 120-135 行
内容：用户反复强调不能频繁跳切。
类型：用户痛点 / 验收标准候选
置信度：高
```

后面生成目标、规则、流程时，不是凭空生成，而是基于证据。

## 七、阶段 3：候选项目理解

然后生成一个候选理解文件：

```text
.aios/context/00_project_goal_draft.md
```

里面不是最终目标，而是候选理解：

```text
我理解这个项目要解决的问题是：
用户是谁：
用户痛点是：
好结果是：
坏结果是：
本阶段目标是：
暂时不做的是：
我不确定的是：
需要用户确认的是：
```

这里应该有一次 Human Gate。

否则如果一开始目标理解错了，后面所有自动化都会错。

## 八、阶段 4：生成六层项目文件

用户确认项目蓝图后，再生成正式文件。

### 1. 目标层

文件：

```text
.aios/context/00_project_goal.md
```

内容：

```text
项目最终目标
当前阶段目标
用户是谁
用户痛点
好结果
坏结果
本阶段不做什么
成功标准
失败标准
```

### 2. 规格层

文件：

```text
.aios/context/02_specifications.md
```

内容：

```text
必须做到：
- ...

禁止出现：
- ...

允许但要谨慎：
- ...

优先级：
P0：必须满足
P1：重要
P2：可优化
```

规格最好分级，不要所有规则都一样重要。

否则 AI 会为了满足小规则破坏大目标。

### 3. 样例层

文件：

```text
.aios/context/03_examples.md
```

内容：

```text
黄金正例
失败反例
边界例子
每个例子为什么好 / 为什么坏
以后如何判断类似情况
```

复杂项目里，样例比抽象规则更有用。

### 4. 流程层

文件：

```text
.aios/workflow/00_overall_workflow.md
```

内容：

```text
第 1 步：输入是什么
第 1 步：输出是什么
第 1 步：成功标准是什么
第 1 步：失败怎么办

第 2 步：...
```

每一步必须说人话。

### 5. 检查层

文件：

```text
.aios/checks/deterministic_checks.md
.aios/checks/llm_judgment_checks.md
.aios/checks/check_registry.json
```

把问题分成两类：

```text
确定性问题：程序检查
判断性问题：LLM 检查
```

确定性检查示例：

```text
文件是否存在
输出是否为空
测试是否通过
是否删除了禁止删除的文件
是否超过最大行数
是否有重复内容
```

判断性检查示例：

```text
用户体验是否好
是否专业
是否观点闭环
是否符合用户审美
是否表达自然
```

### 6. 验收层

文件：

```text
.aios/context/04_acceptance.md
.aios/workflow/03_review_policy.md
```

内容：

```text
最终验收标准
每轮验收标准
哪些情况自动通过
哪些情况需要人工确认
哪些情况直接失败
```

## 九、阶段 5：任务图和递归拆解

子目标可能很难，需要递归拆解。

不能简单跳过，也不能无限拆。

应该引入：

```text
Task Graph / Work Breakdown Tree
```

但这里建议增加一层：**外部工具任务拆解层**。

因为不同模型擅长不同事情。如果 Claude 更擅长拆解复杂任务，就可以让 Claude 专门做任务拆解。

### 1. 先生成任务拆解请求文件

AIOS 先写一个文件：

```text
.aios/tasks/task_decomposition_request.md
```

这个文件不是最终任务图，而是给外部工具阅读的任务拆解说明。

内容包括：

```text
项目目标
当前阶段目标
已确认规格
验收标准
约束条件
已知风险
需要拆解的问题
希望输出的任务图格式
递归深度限制
任务优先级规则
阻塞处理规则
```

### 2. 文件里内置给 Claude 的提示词

`task_decomposition_request.md` 里应该包含一段明确提示词：

```text
请你作为任务拆解专家，阅读本文件中的项目背景、目标、规格、验收标准和限制。

你的任务：
1. 把当前阶段目标拆解成可执行任务树。
2. 每个任务都要写清楚输入、输出、成功标准、失败标准、风险等级。
3. 如果某个任务过大，请继续递归拆解。
4. 如果任务依赖不清楚，请标记为 needs_human。
5. 如果任务可以并行，请标记 parallel_group。
6. 如果任务必须串行，请写明依赖。
7. 不要执行任务，只做任务拆解。
8. 输出写入 .aios/tasks/task_graph.md 和 .aios/tasks/task_graph.json。
```

### 3. 用户调用 Claude 拆解

用户可以把这个文件交给 Claude：

```text
请阅读 .aios/tasks/task_decomposition_request.md，按里面的提示词拆解任务，并把结果写入指定文件。
```

Claude 输出：

```text
.aios/tasks/task_graph.md
.aios/tasks/task_graph.json
```

### 4. AIOS 再回来读取任务图

Python / Codex / LLM 再读取：

```text
.aios/tasks/task_graph.md
.aios/tasks/task_graph.json
```

然后进入执行阶段。

这样做的好处：

```text
任务拆解从执行系统里独立出来
可以借助更擅长拆解的外部模型
任务图成为稳定文件
后续执行不再靠聊天临时理解
```

### 5. 任务图结构

`task_graph.json` 示例：

```json
{
  "task_id": "T-001",
  "title": "生成短视频 Story 模式",
  "status": "in_progress",
  "depth": 0,
  "max_depth": 4,
  "children": [
    {
      "task_id": "T-001-1",
      "title": "读取项目文档并理解目标",
      "status": "done"
    },
    {
      "task_id": "T-001-2",
      "title": "生成专业剪辑大纲",
      "status": "pending"
    }
  ]
}
```

### 6. 递归拆解规则

```text
如果任务太大 → 拆成子任务
如果子任务仍然太大 → 继续拆
如果超过最大深度 → 停止，标记为 needs_human
如果任务不清楚 → 生成问题，不执行
如果任务被阻塞 → 标记 blocked，继续其他独立任务
```

不能静默跳过。

任务状态应包括：

```text
pending
in_progress
done
failed
blocked
skipped_with_reason
needs_human
```

如果跳过，必须写原因：

```text
跳过原因：
- 缺少输入文件
- 验收标准冲突
- 风险太高
- 超过递归深度
- 需要用户决策
```

## 十、阶段 6：状态机

整个 AIOS 不能靠 LLM 自由发挥，必须有状态机。

建议状态：

```text
BOOTSTRAP
↓
INGEST_SOURCE
↓
EXTRACT_EVIDENCE
↓
DRAFT_CONTEXT
↓
HUMAN_CONFIRM_CONTEXT
↓
BUILD_PROJECT_FILES
↓
REQUEST_TASK_DECOMPOSITION
↓
WAIT_TASK_DECOMPOSITION
↓
LOAD_TASK_GRAPH
↓
PLAN_TASKS
↓
EXECUTE_TASK
↓
RUN_CHECKS
↓
REPAIR
↓
REVIEW
↓
DONE / BLOCKED / FAILED
```

注意：这里增加了三步：

```text
REQUEST_TASK_DECOMPOSITION
WAIT_TASK_DECOMPOSITION
LOAD_TASK_GRAPH
```

这是为了支持 Claude 等外部工具拆解任务。

`state.json` 示例：

```json
{
  "phase": "EXECUTE_TASK",
  "current_task_id": "T-001-2",
  "iteration": 2,
  "max_iterations": 5,
  "max_depth": 4,
  "status": "running",
  "last_result": "checker_failed",
  "needs_human": false
}
```

状态机的作用是：

```text
防止无限循环
防止跳步骤
防止忘记当前目标
防止 AI 突然改变方向
防止外部任务拆解结果没有被正式加载
```

## 十一、阶段 7：执行系统

执行时应该有三个角色：

```text
Planner LLM：决定下一步做什么
Codex Worker：执行代码 / 文件修改
Checker：检查结果是否达标
```

职责分离：

```text
Planner 不直接改文件
Codex 不决定项目方向
Checker 不做主观推理
用户只做关键验收
```

执行循环：

```text
读取 state
读取 task_graph
读取 context
Planner 选择下一个任务
Codex 执行
Checker 检查
Planner 根据检查结果决定继续 / 修复 / 阻塞 / 完成
更新 state
写 run_log
```

## 十二、主要风险与解决方案

### 风险 1：让 LLM 直接从原始文本生成最终规则

容易误读。

解决：

```text
先证据提取
再候选理解
再用户确认
再生成正式规则
```

### 风险 2：规则太多，没有优先级

AI 会为了小规则破坏大目标。

解决：

```text
P0：绝对不能违反
P1：重要
P2：尽量优化
```

### 风险 3：递归拆解无限扩张

任务会越拆越多，永远做不完。

解决：

```text
max_depth
max_iterations
max_runtime
max_cost
熔断机制
```

### 风险 4：全自动失控

自动删除、自动重构、自动发布，会很危险。

解决：

```text
Human Gate
风险分级
高风险必须停下来
```

### 风险 5：每次都重新理解项目

浪费 token，也容易前后不一致。

解决：

```text
state.json
decision log
context files
run log
```

### 风险 6：判断性问题没有校准

LLM 会自信但判断错。

解决：

```text
黄金样例
失败样例
LLM 评估 rubric
多轮评审
必要时人工验收
```

### 风险 7：外部工具拆解和 AIOS 执行脱节

Claude 拆得很好，但 AIOS 没有正式加载，后续还是乱跑。

解决：

```text
任务拆解必须写入 task_graph.md 和 task_graph.json
AIOS 必须进入 LOAD_TASK_GRAPH 状态
加载后校验 task_graph.json 格式
校验每个任务都有输入、输出、验收标准、风险等级
```

## 十三、建议 MVP

不要一开始做全功能。

第一版只做“项目初始化器 + 任务拆解请求生成器”。

输入：

```text
一个很长的 initial_input.md
```

输出：

```text
.aios/evidence/facts.md
.aios/evidence/pain_points.md
.aios/evidence/user_needs.md
.aios/evidence/success_examples.md
.aios/evidence/failure_examples.md
.aios/evidence/open_questions.md

.aios/context/00_project_goal.md
.aios/context/01_requirements.md
.aios/context/02_specifications.md
.aios/context/03_examples.md
.aios/context/04_acceptance.md

.aios/workflow/00_overall_workflow.md
.aios/checks/deterministic_checks.md
.aios/checks/llm_judgment_checks.md
.aios/tasks/task_decomposition_request.md
.aios/state.json
```

第一版先不要自动执行 Codex。

先验证一件事：

```text
它能不能从混乱的原始文本里，提炼出靠谱的项目操作系统文件？
```

如果这个做不好，后面自动执行一定会乱。

## 十四、第二版再做自动执行

第二版加入：

```text
Planner LLM
Codex Worker
Checker
Task Graph Loader
Run Log
Repair Loop
```

执行命令可以是：

```bash
aios init initial_input.md
aios review-context
aios request-task-decomposition
aios load-task-graph
aios run "开始实现当前阶段目标"
```

或者：

```bash
aios run task.md
```

## 十五、这个系统的本质

它不是一个普通 CLI。

它本质上是：

```text
项目知识提取器
+
项目上下文生成器
+
任务拆解请求生成器
+
外部任务拆解协调器
+
任务图加载器
+
状态机调度器
+
Agent 执行器
+
自动检查器
+
人工验收闸门
```

一句话：

```text
把用户混乱的自然语言项目经验，变成 AI 可以稳定执行的项目操作系统。
```

## 十六、最终建议

不要直接：

```text
原始文本 → 目标 / 规则 / 流程
```

而是：

```text
原始文本
↓
证据提取
↓
候选理解
↓
用户确认
↓
项目文件生成
↓
任务拆解请求文件
↓
Claude 等外部工具拆解任务
↓
AIOS 读取任务图
↓
状态机执行
↓
检查与修复
↓
人工验收
```

最关键的设计原则：

```text
先理解，再冻结；
先证据，再规则；
先样例，再判断；
先小闭环，再全自动；
先任务拆解，再任务执行；
先状态机，再递归；
先人工闸门，再无人执行。
```

这样这个 AI 操作系统才不会变成“更复杂、更自动化的拉扯”。
