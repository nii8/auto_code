# AIOS：AI 项目操作系统

AIOS 是一套用于复杂项目的 AI 协作操作系统原型。它通过配置文件、方法论文档、Python 工具和 `.aios/` 工作目录，把“和 AI 聊天做项目”升级成“有流程、有证据、有检查、有任务图”的流程驱动系统。

它的目标不是让 AI 更自信地说“我完成了”，而是让 AI 的每一句“完成了”都被真实证据约束；经验库是可选扩展，不是初始项目必需组件。

## 这个项目解决什么问题

普通 AI 编程协作经常会出现一种很讨厌的情况：

```text
AI 说已经完成
↓
用户相信了
↓
用户实际一用，发现这里不通、那里报错、流程根本没走完
↓
用户继续截图、描述 bug、补充细节
↓
AI 再修一点，但可能还是不行
↓
用户变成代码消防员
```

AIOS 想解决的核心不是“AI 会不会写代码”，而是：

```text
AI 是否真的理解目标
任务是否拆对
每一步是否有证据
最终用户流程是否真的跑通
普通代码错误是否能自动修
用户是否只在关键决策点介入
```

## 核心原则

```text
没有证据，不允许宣布完成。
用户流程证据优先于代码存在。
检查器结论优先于 AI 自评。
任务图质量决定自动化质量。
用户是目标确认者、取舍者、验收官，不是代码消防员。
```

## 规范优先级

为避免多份文档重复时产生冲突，AIOS 按下面顺序判定权威：

```text
1. 用户当前明确指令
2. aios_docs/AI项目操作系统项目设计.md：目录结构、状态机、任务图和证据规范的详细事实源
3. aios_docs/AI项目操作系统总控入口.md：新会话启动流程和必读索引
4. README.md：人类快速说明和使用入口
5. 其他文档：解释背景、方法论或历史设计，不覆盖以上规范
```

如果多个文档说法不一致，应优先修正文档，而不是让执行器猜测。

## 目录结构

```text
.
├── README.md                         给人类看的项目说明，也就是本文档
├── aios.py                           普通用户入口，运行 AIOS 自动执行器
├── aios_docs/                        AIOS 内核文档和工具
│   ├── AI项目操作系统总控入口.md       新 Codex 会话启动入口
│   ├── AIOS内核运行路线图.md          启动到执行的流程顺序索引
│   ├── AI项目操作系统方法论.md         方法论和证据约束原则
│   ├── AI项目操作系统落地架构.md       Python / Codex / Checker 落地方式
│   ├── AI项目操作系统项目设计.md       初始化、逐层冻结、任务图设计
│   ├── MACHINE_README.md             给 AI / Codex 读的内部说明
│   ├── aios_config.yaml              当前项目配置
│   └── tools/                        Runner、配置读取、检查器等工具
└── <source_code_dir>/                本机被 AIOS 管理的源码项目，通常不提交到本内核仓库
    ├── 原始材料 / 聊天记录
    └── .aios/                        当前项目的冻结文件、任务图、运行日志
```

## 两种使用方式

### 方式一：让 Codex 启动完整 AIOS 流程

新开一个 Codex 会话后，对它说：

```text
请读取 aios_docs/AI项目操作系统总控入口.md，按 AIOS 流程启动。
```

Codex 应该按顺序读取：

```text
1. AI项目操作系统总控入口.md
2. AIOS内核运行路线图.md
3. aios_config.yaml
4. AI项目操作系统方法论.md
5. AI项目操作系统落地架构.md
6. AI项目操作系统项目设计.md
7. 原始材料和源码目录
```

如果配置里缺项目模式、源码目录或原始材料路径，Codex 不应该让用户手动改 YAML，也不应该替用户默认选择 `greenfield`，而应该直接在对话里问：

```text
我需要先绑定本机项目，不需要你手动改 YAML。请告诉我：
1. 项目模式是 greenfield、brownfield 还是 rebuild？
2. 可写目标项目目录在哪里？
3. 原始材料 / 聊天记录文件在哪里？
4. 如果是 rebuild：旧项目源码目录在哪里？旧项目只作为只读参考。
```

用户回答后，Codex 自动写入 `aios_docs/aios_config.local.yaml`。

`aios_docs/aios_config.yaml` 是可提交的模板配置；`aios_config.local.yaml` 保存本机真实路径，已被 `.gitignore` 忽略，不需要提交，也不需要反复改来改去。

### 方式二：直接运行自动执行器

如果目标、需求、规格、检查、验收、任务图都已经冻结，可以直接运行：

```bash
python3 aios.py run
```

或者进入交互驾驶舱：

```bash
python3 aios.py
```

常用命令：

```bash
python3 aios.py status    # 查看当前进度
python3 aios.py doctor    # 检查本地运行环境
python3 aios.py check     # 检查任务图
python3 aios.py preview   # 预览下一步，不改代码
python3 aios.py next      # 只执行一个任务
python3 aios.py run       # 自动推进
python3 aios.py reset     # 清掉运行日志和任务状态，从任务图重跑
```

`run` / `next` 会先做依赖预检。项目配置中明确声明的低风险 Python 包依赖会尽量自动安装，不应该让普通用户手动当环境消防员。

## 标准项目流程

AIOS 不应该一开始就写代码。真实复杂项目通常先有整体业务、pipeline、模块边界和阶段规划，然后才进入某个阶段或模块的具体实现。标准流程是先做项目级规划，再对当前 initiative 逐层确认、逐层冻结。

```text
绑定 project_mode / 源码目录 / 原始材料路径
↓
运行上下文体检 python3 aios.py context
↓
运行初始化清洗 python3 aios.py clean
↓
生成 .aios/ingest 和 .aios/source 清洗产物，不修改源码和原始聊天记录
↓
退出当前 Codex，重新开启新会话
↓
新会话只读清洗产物，再做规划上下文闸门
↓
原始材料摘要 / 源码目录树 / 关键入口
↓
证据草案
↓
项目总览 project_overview.md
↓
模块 / pipeline 关系 module_map.md / pipeline_map.md
↓
阶段规划 initiative_index.md
↓
选择并确认 active initiative
↓
当前 initiative 的 goal.md
↓
当前 initiative 的 requirements.md
↓
当前 initiative 的 spec.md
↓
当前 initiative 的 examples.md
↓
当前 initiative 的 workflow.md
↓
当前 initiative 的 checks.md
↓
当前 initiative 的 acceptance.md
↓
当前 initiative 的 task_decomposition_request.md
↓
当前 initiative 的 task_graph.md / task_graph.json
↓
AIOS Runner 执行
```

每一层都应该是：

```text
Codex 生成草案
↓
用户确认 / 修改
↓
Codex 写入正式文件
↓
进入下一层
```

用户确认某一层，只代表这一层确认，不代表后续层级自动确认。

## 重构项目模式：旧项目只读，新项目重写

真实复杂项目经常不是继续修旧代码，而是：旧项目能跑但质量不好，需要参考旧业务重新写。

AIOS 支持这种标准模式：

```text
project_mode: rebuild
reference_source_dirs: 旧项目源码，只读参考
target_source_dir / source_code_dir: 新项目源码，可写目标
source_material_file: 聊天记录 / 需求说明 / 旧项目说明
```

规则：

```text
旧项目只能读取、理解、参考，不能修改。
新项目是唯一允许写代码的目标。
旧项目中的好设计可以借鉴，坏设计要记录并避免继承。
第一轮只做理解和规划，不写代码。
先生成旧项目分析、项目总览、initiative 候选，再确认 I001。
```

推荐启动时告诉 Codex：

```text
这是一个重构项目。
旧项目源码在：/path/to/old_project，只读参考，不允许修改。
新项目目录在：/path/to/new_project，从零实现，允许写入。
原始材料在：/path/to/material.md。
请先理解旧项目和材料，生成项目理解、旧项目分析、重构目标候选，不要写代码。
```

## 多阶段 / 多模块项目：initiative

真实项目通常不是一次性完成，而是长期演进：一期、二期、三期，或者多个业务模块沿 pipeline 流动。AIOS 不建议把大项目、阶段目标、模块目标混在同一套目标文件里。复杂项目应使用项目级文件 + initiative：

```text
.aios/project/project_overview.md
.aios/project/module_map.md
.aios/project/pipeline_map.md
.aios/project/initiative_index.md
.aios/initiatives/I001_foundation/
.aios/initiatives/I002_pipeline_ingest/
.aios/initiatives/I003_pipeline_export/
```

项目级文件回答：整体业务是什么、有哪些模块、模块之间如何流动、一期二期三期怎么排。每个 initiative 回答：当前阶段或当前模块到底要做到什么。

每个 initiative 都可以有自己的：

```text
goal.md
requirements.md
spec.md
examples.md
workflow.md
checks.md
acceptance.md
task_graph.md
task_graph.json
state.json
runs/
reports/
```

当前 AIOS 仍然只串行执行：

```text
同一时间只跑一个 active initiative。
同一时间只跑一个任务。
不做多个 Codex Worker 并发写代码。
不做文件锁并发。
不做 git worktree 并发。
```

这样能减少冲突和调试复杂度。`dependencies` 和 `write_scope` 仍然保留，用于任务边界、写入限制和未来扩展。

## 需求变更：change request

新需求不应该直接覆盖旧目标。推荐先形成 change request：

```text
.aios/changes/CR20260610_001_xxx/request.md
.aios/changes/CR20260610_001_xxx/impact_analysis.md
.aios/changes/CR20260610_001_xxx/decision.md
```

Codex 应判断它属于：

```text
当前 initiative 的小修改
新的 initiative
bugfix
目标冲突，需要问用户
验收变化，需要重新确认验收
```

## 任务拆解为什么重要

AIOS 能不能一气呵成，很大程度取决于任务图拆得好不好。

任务拆得好：

```text
每个任务目标清楚
依赖顺序清楚
写入范围清楚
成功标准清楚
失败标准清楚
检查证据清楚
```

任务拆得不好：

```text
AI 可能一路执行，但方向错了
前后端字段可能对不上
检查可能太晚才发现问题
任务可能过大导致失败
任务可能过碎导致上下文断裂
```

所以任务拆解前必须检查：

```text
目标是否一句话能说清楚
需求 / 非需求是否互相打架
规格是否能指导实现
样例是否覆盖正向、边界和失败反例
流程是否从用户动作开始，到用户拿到结果结束
检查是否包含确定性检查、端到端检查和负向检查
验收是否能证明真实可用
```

## Codex + Claude Code 任务拆解协作

复杂项目不建议只依赖单模型拆任务。

推荐方式：

```text
1. Codex 基于冻结文件生成 task_decomposition_request.md。
2. Codex 先生成一版 codex_task_graph_draft.md。
3. 用户把请求和草案交给 Claude Code 复审。
4. Claude Code 输出 claude_task_graph_review.md 或 claude_task_graph_draft.md。
5. Codex 读取 Claude 的结果。
6. Codex 做融合、冲突检查、证据对齐。
7. Codex 生成最终 task_graph.md 和 task_graph.json。
8. 用户确认最终任务图。
9. Runner 执行。
```

Claude Code 是外部审稿人 / 规划顾问，不是最终执行权威。最终任务图应该由 Codex 融合生成，因为 Codex 更清楚当前 AIOS 文件、Runner 格式、write_scope、检查器和执行状态。

融合 Claude 结果时，Codex 应输出：

```text
采用 Claude 建议
拒绝 Claude 建议
修改 Claude 建议
Codex 补充
仍需用户确认
```

## 执行阶段如何工作

执行阶段不是让聊天直接写业务代码，而是：

```text
python3 aios.py run
↓
AIOS Runner 读取 task_graph.json
↓
选择下一个可执行任务
↓
调用 Codex Worker 执行单个任务
↓
Worker 只允许改 write_scope
↓
Worker 写代码、跑检查、修普通错误
↓
Runner 运行 success_checks / expected_outputs / 报告证据检查
↓
通过才把任务标记为 done
↓
失败则自动 repair 或进入人工闸门
↓
全部完成后输出耗时汇总和最终报告
```

当前默认执行链路不调用 `llm_client.py` 做动态 Planner；`llm_client.py` 只是辅助工具。规划能力以已冻结文件和任务图为准，避免在执行阶段临时改变项目方向。

Runner 构造 Worker prompt 时会使用上下文预算。任务可以通过 `context_refs` 指定优先展开的上下文文件；其余项目级和 initiative 上下文会按预算补充。每次执行前都会打印 Worker Prompt 上下文报告，包括 prompt 总字符数、估算 token、预算使用率、展开/截断/跳过文件数量和最大上下文文件。超过预算时只保留路径提示，避免上下文过大干扰当前任务。

启动或规划前可以先运行：

```bash
python3 aios.py context
```

这个命令只做上下文体检，不执行任务。它会统计启动必读文档、原始材料/聊天记录、已冻结项目上下文和源码树大小，让用户先知道“这轮如果读进去大概有多大”。它还会给出“初始化/规划上下文闸门”结论：`ok` 可以继续规划，`warning` 需要缩小读取范围，`blocked` 不能继续冻结项目目标或模块目标，必须先摘要、索引、拆 initiative。不要把所有源码、所有 MD 和完整聊天记录塞进同一个 prompt。

路径填好后应先运行：

```bash
python3 aios.py clean
```

`clean` 会只读原始材料和源码树，生成 `.aios/ingest` 与 `.aios/source` 下的清洗产物；它不修改源码，也不修改原始聊天记录。清洗完成后会提示用户退出当前 Codex，重新开启新会话。新会话只读取 `.aios/ingest/bootstrap_readme.md` 指定的清洗产物，再开始项目级规划和模块目标冻结。

## 什么会自动处理，什么会停下来

AIOS 应该自动处理：

```text
语法错误
普通测试失败
接口字段不一致
缺少低风险 Python 包
expected_outputs 缺失
报告证据结构不完整
局部实现 bug
```

AIOS 必须停下来问用户：

```text
目标不清楚
需求 / 非需求冲突
规格和验收打架
高风险操作
删除大量文件
改数据库 / 生产数据
需要账号、密钥、付费资源
连续失败超过限制
主观体验或产品取舍
```

## 证据闸门

AIOS 区分证据可信度，不能把 AI 自己写的报告当作唯一完成依据：

```text
L0 自述证据：AI 写的报告、说明，只能辅助判断。
L1 文件证据：产物存在、路径存在，证明“有”，不证明“对”。
L2 命令证据：Runner 实际执行命令并记录返回码、stdout、stderr。
L3 可复现证据：同一检查可重新运行，或包含内容校验、大小校验、hash 校验。
L4 独立验证证据：预先定义的测试、schema、golden case、端到端脚本或人工验收记录。
```

默认情况下，任务必须至少有一个可复现的 blocking check，不能只靠报告文字或文件存在自动标记完成。

任务完成最低证据清单：

```text
改了哪些文件
运行了哪些命令
哪些检查通过
关键用户流程如何模拟
负向场景检查了什么
产物在哪里
未验证项是什么
```

不能接受的完成声明：

```text
“我已经完成了”，但没有检查。
“应该可以运行”，但没有运行。
“页面已经做好”，但没有页面结构、浏览器、截图或 DOM 证据。
“流程已完成”，但没有从输入到结果的端到端验证。
“没问题”，但没有负向场景。
```

## reset 会做什么

`python3 aios.py reset` 用于重新演练当前 active initiative 的执行流程。

它会清理：

```text
运行日志
报告
任务执行状态
```

默认不删除业务源码，也不删除生成产物。只有当项目配置显式声明 `reset.generated_paths` 时，AIOS 才会清理这些可重建路径。

它会保留：

```text
原始材料
目标
需求 / 非需求
规格
样例
流程
检查
验收
任务图
AIOS 内核文档
```

也就是说，`reset` 不是重新理解项目，而是基于已经冻结的项目定义，从任务图重新执行。

## 当前项目状态

这个仓库是 AIOS 内核仓库，不绑定任何特定业务应用。真实业务项目通过 `aios_config.local.yaml` 指向本机可写项目目录，业务源码、原始材料和 `.aios/` 工作目录通常属于被管理项目，而不是这个内核仓库。

当前内核重点验证：

```text
AIOS 能否读取冻结文件
AIOS 能否按任务图调用 Codex Worker
AIOS 能否按 active initiative 自动推进任务
AIOS 能否做依赖预检、检查、报告、耗时汇总
AIOS 能否用证据约束“完成”
```
