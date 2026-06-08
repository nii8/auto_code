# AI 项目操作系统总控入口

> 本文件是 AIOS 的通用启动入口。启动时先读取同目录下的 `aios_config.yaml`，再按交互式流程初始化项目。

## 1. 启动配置文件

启动参数不写在本文件里，统一写在：

```text
aios_docs/aios_config.yaml
```

用户启动前优先修改这个 YAML 文件。

里面最重要的参数是：

```text
source_code_dir       源码目录
source_material_file  原始项目材料文件
initial_goal_hint     当前阶段目标提示，可空
```

AIOS 工作目录固定创建在：

```text
<source_code_dir>/.aios
```

这个路径不需要用户选择，避免增加决策成本。

第一轮固定策略：

```text
允许读取源码
不允许修改源码
不允许调用 Codex/LLM 自动执行生产任务
只做项目初始化、证据草案、候选目标讨论
```

## 2. 启动后的第一件事

AI 启动后必须先做参数检查：

```text
1. 读取本文件。
2. 读取 `aios_docs/aios_config.yaml`。
3. 如果 `source_code_dir` 为空，询问用户源码目录在哪里。
4. 如果 `source_material_file` 为空，询问用户原始材料文件在哪里。
5. 在 `source_code_dir` 下创建 `.aios/` 工作目录。
6. 确认路径存在后，再继续。
```

不要要求用户复制文件；本目录已经是 AIOS 启动目录。

## 3. 配套文件

启动时应读取同目录下这些文件：

```text
AI项目操作系统方法论.md
AI项目操作系统落地架构.md
AI项目操作系统项目设计.md
```

同时读取经验库的启动必读文件和 A 类强通用经验：

```text
experience/README.md
experience/经验适用性判断规则.md
experience/通用经验.md
```

B 类领域经验和 C 类项目特定经验不要在启动时直接加载：

```text
experience/领域经验.md        按当前项目领域需要再读取
experience/项目特定经验.md    按源码/项目匹配度需要再读取
```

其他经验文件可按需读取：

```text
experience/失败教训.md
experience/提示词经验.md
experience/检查规则经验.md
experience/工具经验.md
```

经验库用于复用过去项目沉淀的经验，但不能替代当前项目的目标确认。A 类经验启动时形成候选加载清单，让用户选择是否加载；B/C 类经验必须按实际项目需要再读取。

原始材料文件由 `aios_config.yaml` 里的 `source_material_file` 指定，不要写死成某个固定文件名。

## 4. 配套文件作用

### `AI项目操作系统方法论.md`

说明 AIOS 的通用方法论：

```text
目标文档化
标准样例化
流程模块化
检查自动化
判断评测化
用户验收化
经验资产化
```

### `AI项目操作系统落地架构.md`

说明 AIOS 如何落地成 Python / CLI / Codex / LLM 驱动的自动化系统：

```text
Python 总控如何调度
Codex Worker 如何执行
Planner LLM 如何决策
Checker 如何检查
状态机如何防止无限循环
Human Gate 如何避免自动化失控
```

### `AI项目操作系统项目设计.md`

说明 AIOS 项目初始化器如何从原始长文本中，生成项目上下文、证据层、目标层、规格层、样例层、流程层、检查层、验收层，以及任务拆解请求。

### 原始材料文件

原始材料文件可以是：

```text
聊天记录
录音转写
会议纪要
用户随手写的想法
旧项目文档
需求文档
复盘材料
```

AIOS 不能直接把原始材料当成最终目标，而应该把它当作：

```text
证据来源
历史轨迹
需求线索
失败反例
用户偏好
项目背景
```

## 5. 项目启动原则

启动 AIOS 时，不要让 AI 直接拍板目标。

正确流程是：

```text
读取总控入口
↓
读取 aios_config.yaml
↓
读取方法论 / 架构 / 项目设计
↓
读取原始材料和源码目录结构
↓
先生成证据草案
↓
和用户讨论目标
↓
用户确认后冻结目标
↓
继续讨论需求 / 非需求
↓
用户确认后冻结需求
↓
继续讨论规格 / 样例 / 流程 / 检查 / 验收
↓
逐层确认，逐层冻结
↓
生成任务拆解请求
↓
必要时交给外部模型拆解任务
↓
AIOS 读取任务图
↓
Python / Codex / LLM 按状态机执行
```

核心原则：

```text
AI 可以提炼候选目标，但不能替用户决定目标。
AI 可以生成规则草案，但不能替用户冻结规则。
AI 可以建议流程，但必须和用户确认真实业务流程。
```

## 6. 推荐启动提示词

在新会话中可以这样启动：

```text
请读取 aios_docs/AI项目操作系统总控入口.md，按其中流程启动 AIOS。

注意：
1. 先读取 aios_docs/aios_config.yaml。
2. 如果源码目录或原始材料路径为空，先问我。
3. 不要直接冻结目标。
4. 不要第一轮修改源码。
5. 先读取 AIOS 方法论、落地架构、项目设计、经验库启动必读文件和 A 类候选经验，再读取原始材料。
6. 然后扫描源码目录结构。
7. 先生成证据草案和候选目标草案。
8. 候选目标必须和我讨论确认后，才能写入正式目标文件。
9. 后续需求、规格、样例、流程、检查、验收也都必须逐层确认后再冻结。
```

## 7. AIOS 工作目录

AIOS 工作目录固定为：

```text
<source_code_dir>/.aios/
```

推荐结构：

```text
.aios/
  source/      保存原始材料副本或索引
  evidence/    保存事实、痛点、需求、样例等证据草案
  context/     保存目标、需求、规格、样例、验收标准
  workflow/    保存流程、执行策略、人工闸门策略
  checks/      保存确定性检查和 LLM 判断性检查规则
  tools/       保存 AIOS 辅助 Python 脚本
  tasks/       保存任务拆解请求、任务图、当前任务
  runs/        保存运行日志、LLM 调用记录、Codex 调用记录
  reports/     保存阶段报告和最终报告
  state.json   保存状态机当前状态
```

## 8. 第一轮必须做的事情

第一轮不要改代码。

第一轮只做：

```text
1. 读取 AIOS 总控、三个方法文件、经验库启动必读文件和 A 类强通用经验。
2. 读取 `aios_config.yaml`。
3. 确认源码目录和原始材料路径。
4. 读取原始材料。
5. 扫描源码目录结构。
6. 生成证据草案。
7. 生成候选目标草案。
8. 向用户提问，确认当前阶段真实目标。
```

第一轮禁止：

```text
直接改代码
直接运行耗时任务
直接生成最终产物
直接删除文件
直接调用外部模型拆任务
直接冻结目标
直接上传 / 发布
```

## 9. 交互式冻结流程

所有关键文件都先生成草案：

```text
00_project_goal.draft.md
01_requirements.draft.md
02_specifications.draft.md
03_examples.draft.md
04_acceptance.draft.md
00_overall_workflow.draft.md
```

用户确认后，才生成正式文件：

```text
00_project_goal.md
01_requirements.md
02_specifications.md
03_examples.md
04_acceptance.md
00_overall_workflow.md
```

冻结顺序：

```text
目标
↓
需求 / 非需求
↓
规格
↓
样例
↓
流程
↓
检查
↓
验收
↓
任务拆解请求
```

## 10. Python / LLM 工具要求

AIOS 后续需要 Python 辅助工具。

工具放在：

```text
aios_docs/tools/
```

至少包含：

```text
llm_client.py      调用外部 LLM，例如 qwen3.6-plus
codex_runner.py   调用 Codex CLI
check_runner.py   运行确定性检查
state_manager.py  维护 .aios/state.json
```

API Key 不要写死在代码里，要从环境变量读取。

## 11. 状态机

状态机是 AIOS 当前进行到哪一步的记录。它防止 AI 忘记流程、跳步骤、无限循环。

```text
BOOTSTRAP                 启动，读取总控入口
CHECK_PARAMS              检查 aios_config.yaml 参数是否完整
ASK_MISSING_PARAMS         参数缺失时询问用户
INGEST_SOURCE             读取原始材料
SCAN_SOURCE_CODE          扫描源码目录结构
EXTRACT_EVIDENCE_DRAFT    生成证据草案
DISCUSS_GOAL              和用户讨论目标
FREEZE_GOAL               用户确认后冻结目标文件
DISCUSS_REQUIREMENTS      和用户讨论需求 / 非需求
FREEZE_REQUIREMENTS       用户确认后冻结需求文件
DISCUSS_SPECIFICATIONS    和用户讨论规格规则
FREEZE_SPECIFICATIONS     用户确认后冻结规格文件
DISCUSS_EXAMPLES          和用户讨论正反样例
FREEZE_EXAMPLES           用户确认后冻结样例文件
DISCUSS_WORKFLOW          和用户讨论流程
FREEZE_WORKFLOW           用户确认后冻结流程文件
DISCUSS_CHECKS_ACCEPTANCE 和用户讨论检查与验收标准
FREEZE_CHECKS_ACCEPTANCE  用户确认后冻结检查与验收文件
REQUEST_TASK_DECOMPOSITION 生成任务拆解请求
WAIT_TASK_DECOMPOSITION   等待外部模型或用户完成任务拆解
LOAD_TASK_GRAPH           读取任务图
EXECUTE                   按任务图执行
```

## 12. 任务拆解

只有当目标、需求、规格、样例、流程、检查、验收都确认后，才生成任务拆解请求。

任务拆解请求文件：

```text
.aios/tasks/task_decomposition_request.md
```

如果用户希望借助 Claude 拆解任务，则把该文件交给 Claude。

Claude 应输出：

```text
.aios/tasks/task_graph.md
.aios/tasks/task_graph.json
```

然后 AIOS 再读取任务图，进入执行阶段。

## 13. 通用性要求

本总控入口必须适用于任意源码项目。

因此不要写死：

```text
短视频项目
某个固定源码目录
某个固定聊天记录文件
某个固定输出目标
```

所有项目相关内容都应来自：

```text
source_code_dir
source_material_file
用户交互确认
```

## 14. 最终提醒

AIOS 的目标不是让 AI 更快地乱跑，而是让 AI 在以下约束中稳定推进：

```text
目标经过确认
规则经过冻结
样例经过校准
流程经过讨论
任务经过拆解
执行经过检查
失败可以熔断
用户只做关键验收
```

## 15. 经验库

AIOS 有一个跨项目经验库：

```text
aios_docs/experience/
```

用途：

```text
沉淀跨项目可复用经验
记录失败教训
保存好用提示词
保存检查规则
保存工具使用经验
保存项目复盘
```

启动新项目时，AI 应这样使用经验库：

```text
A 类强通用经验：启动时读取，列成候选加载清单，让用户选择是否加载
B 类领域经验：不启动直接加载，根据当前项目领域需要再读取
C 类项目特定经验：不启动直接加载，根据源码/项目匹配度需要再读取
经验库只能提供参考
必须检查适用场景和不适用场景
不能替代当前项目目标确认
不能把旧项目规则直接强加到新项目
```

项目结束或阶段结束时，应询问用户是否把本轮经验写入经验库。写入 A 类强通用经验必须特别慎重；写入前必须补全经验等级、适用场景、不适用场景、置信度、是否可能过期，并让用户确认。

建议写入：

```text
experience/通用经验.md
experience/领域经验.md
experience/项目特定经验.md
experience/失败教训.md
experience/提示词经验.md
experience/检查规则经验.md
experience/工具经验.md
```

如果是完整项目复盘，使用：

```text
experience/项目复盘模板.md
```

