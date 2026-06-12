# AIOS 内核运行路线图

> 本文件是 AIOS 的流程顺序索引。它不替代方法论、总控入口、落地架构和项目设计，只回答一个问题：新会话从启动到自动执行，应该按什么顺序走。

## 0. 核心原则

```text
没有证据，不允许宣布完成。
用户流程证据优先于代码存在。
检查器结论优先于 AI 自评。
任务图质量决定自动化质量。
用户是目标确认者、取舍者、验收官，不是代码消防员。
```

## 1. 启动必读顺序

```text
1. AI项目操作系统总控入口.md
2. AIOS内核运行路线图.md
3. aios_config.yaml
4. AI项目操作系统方法论.md
5. AI项目操作系统落地架构.md
6. AI项目操作系统项目设计.md
7. 可选 experience/ 经验库
8. source_material_file 原始材料
9. source_code_dir 源码目录结构
```

如果内容冲突，优先级为：用户当前明确指令 > AI项目操作系统项目设计.md > 总控入口 > README.md > 本路线图/方法论/架构 > 经验库。

## 2. 配置缺失时不要让用户改 YAML

如果 `project_mode`、目标源码目录或 `source_material_file` 缺失，直接在对话里问；不要因为模板默认值替用户选择模式，也不要只问“源码目录在哪里”：

```text
我需要先绑定本机项目，不需要你手动改 YAML。请告诉我：
1. 项目模式是 greenfield、brownfield 还是 rebuild？
2. 可写目标项目目录在哪里？
3. 原始材料 / 聊天记录文件在哪里？
4. 如果是 rebuild：旧项目源码目录在哪里？旧项目只作为只读参考。
```

用户回答后，Codex 自动写入 `aios_docs/aios_config.local.yaml`。`aios_config.yaml` 是可提交模板，不写真实机器路径；`aios_config.local.yaml` 是本地动态配置，不提交。

配置齐全后，先运行或模拟 `python3 aios.py context`，把启动候选上下文大小、估算 token、最大文件和超限风险告诉用户。然后运行或模拟 `python3 aios.py clean` 生成清洗产物。清洗完成后提示用户退出当前 Codex，重新开启新会话；新会话只读取 `.aios/ingest/bootstrap_readme.md` 指定的清洗产物。上下文过大时，先摘要/索引/拆 initiative，再进入规划。

如果用户直接提供聊天记录文本，Codex 应保存成材料文件，并把路径写入本地配置。

## 2.5 项目模式

AIOS 支持三种项目模式：

```text
greenfield：全新项目。
brownfield：在现有项目上修改。
rebuild：旧项目只读参考，新项目从零重构。
```

rebuild 模式必须区分：

```text
reference_source_dirs  旧项目源码，只读参考。
target_source_dir      新项目源码，可写目标。
source_material_file   聊天记录、需求说明或旧项目说明。
```

rebuild 模式下，第一轮必须生成旧项目分析和重构目标候选；不能直接修改旧项目，也不能直接开始写新项目代码。

## 3. 第一轮只初始化

第一轮只能：

```text
读取配置 → 读取 AIOS 内核文档 → 运行上下文体检 → 运行初始化清洗 → 提示退出并重开新会话 → 新会话读取清洗产物 → 打印初始化/规划闸门 → 受控读取原始材料摘要和源码目录树 → 生成证据草案和候选目标 → 和用户讨论目标
```

第一轮不能：

```text
修改业务代码
冻结目标
生成完整任务图
调用 Runner 执行生产任务
把后续层级一次性打包确认
在上下文闸门 blocked 时继续冻结项目目标、模块目标或 initiative 目标
全文读取完整源码树当作初始化扫描
清洗完成后仍在旧 Codex 会话里直接冻结目标
```

初始化/规划上下文闸门必须在这些动作之前完成：

```text
读取 source_material_file 全文
深入扫描源码细节
生成或冻结 project_overview.md
生成或冻结 module_map.md / pipeline_map.md
生成或冻结 initiative_index.md
冻结任何 initiative 的 goal.md
```

如果闸门为 `blocked`，第一轮只允许做摘要、索引、源码目录索引、问题清单和拆 initiative 建议。

## 4. 逐层冻结

必须一次只确认一层：

```text
证据草案
↓
候选目标
↓
goal.md
↓
requirements.md
↓
spec.md
↓
examples.md
↓
workflow.md
↓
checks.md
↓
acceptance.md
↓
task_decomposition_request.md
↓
task_graph.md / task_graph.json
↓
AIOS Runner 执行
```

每层都按：Codex 生成草案 → 用户确认/修改 → Codex 写入正式文件 → 进入下一层。用户确认某一层，不代表后续层级自动确认。

## 5. 拆任务前质量闸门

任务拆解前必须检查冻结文件是否足以支撑执行：

```text
目标是否一句话能说清楚。
需求 / 非需求是否互相打架。
规格是否能指导实现，而不是只有愿望。
样例是否覆盖正向、边界和失败反例。
流程是否从用户动作开始，到用户拿到结果结束。
检查是否包含确定性检查、端到端检查和负向检查。
验收是否能证明真实可用，而不是只证明文件存在。
```

任一项不清楚，停止拆任务，回到对应层级补充。

## 6. Codex + Claude Code 任务拆解协作

任务拆解不应只依赖单模型。推荐：

```text
1. Codex 基于冻结文件生成 task_decomposition_request.md。
2. Codex 先生成 codex_task_graph_draft.md。
3. 用户可把请求和草案交给 Claude Code 复审。
4. Claude Code 输出 claude_task_graph_review.md 或 claude_task_graph_draft.md。
5. Codex 读取 Claude 结果，做融合、冲突检查、证据对齐。
6. Codex 生成最终 task_graph.md 和 task_graph.json。
7. 用户确认最终任务图。
8. Runner 执行。
```

Claude Code 是外部审稿人 / 规划顾问，不是最终执行权威。最终任务图由 Codex 融合生成，并受 AIOS 证据闸门、风险闸门和用户确认约束。

融合时必须检查：

```text
是否遗漏必做项。
是否加入明确不做的功能。
任务顺序是否符合依赖。
任务是否过大或过碎。
每个任务是否有 write_scope / success_checks。
是否有环境准备、集成验证、负向检查、最终端到端验收。
哪些任务可自动执行，哪些任务必须人工确认。
```

融合后应输出：采用 Claude 建议、拒绝 Claude 建议、修改 Claude 建议、Codex 补充、仍需用户确认。

## 6.5 多阶段项目和串行执行决策

AIOS 支持复杂项目长期演进，但当前执行模式固定为单线程串行。

```text
支持：多阶段、多需求、多 initiative。
支持：每个 initiative 有自己的目标、需求、规格、检查、验收和任务图。
支持：同一套源码持续演进。
暂不支持：多个 Codex Worker 并发写代码。
暂不支持：文件锁并发、git worktree 并发、自动合并并发分支。
```

当前规则：

```text
同一时间只执行一个 active initiative。
同一时间只执行一个任务。
Runner 按 dependencies 串行推进。
write_scope 用于限制 Worker 写入范围和审查任务边界，不用于并发调度。
dependencies 保留为 DAG 顺序描述和未来扩展点。
```

复杂项目不要把整体项目、阶段目标和模块目标混在同一套 `goal.md` 里，应先建立项目级总览和模块 / pipeline 关系，再使用 initiative 承载阶段或模块目标：

```text
.aios/project/project_overview.md
.aios/project/module_map.md
.aios/project/pipeline_map.md
.aios/project/initiative_index.md
.aios/initiatives/I001_foundation/
.aios/initiatives/I002_pipeline_ingest/
.aios/initiatives/I003_pipeline_export/
```

每个 initiative 是一个阶段、一个需求包、一个 pipeline 模块或一个相对独立目标。

## 7. 执行阶段

最终任务图确认后，才执行：

```bash
python3 aios.py run
```

执行顺序：

```text
doctor / dependency preflight
↓
低风险 Python 依赖自动安装
↓
读取 task_graph.json
↓
Runner 调 Codex Worker 执行单个任务
↓
Worker 只能改 write_scope，且必须产出证据
↓
Runner 跑 success_checks / expected_outputs / 报告证据检查
↓
通过才标记 done
↓
失败则自动 repair 或进入人工闸门
↓
全部完成后输出任务耗时和最终报告
```

## 8. 自动修复与人工闸门

应自动处理：

```text
语法错误
普通测试失败
接口字段不一致
缺少低风险 Python 包
expected_outputs 缺失
报告证据结构不完整
局部实现 bug
```

必须问用户：

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

失败时必须输出：失败任务、失败命令、stderr/stdout 摘要、日志路径、疑似原因、已尝试修复次数、需要用户判断的问题。

## 9. 证据闸门

证据等级、任务完成条件和假证据防护以 `AI项目操作系统项目设计.md` 的任务图 / 证据规范为准；README 只保留人类快速说明。

路线图只强调三条执行顺序规则：

```text
1. 没有 Runner 执行记录、检查结果或人工验收记录，不允许宣布完成。
2. AI 自述报告只是 L0 证据，不能作为唯一完成依据。
3. 默认任务必须至少有一个可复现的 blocking check，否则进入 HUMAN_GATE。
```

## 10. 用户角色

用户不当代码消防员。用户主要负责：确认目标、做产品取舍、授权高风险操作、处理连续失败后的方向判断、做最终主观验收。

AIOS / Codex Worker / Runner 负责：读材料、梳理目标、生成草案、执行代码任务、自动检查、自动修普通错误、保存证据、输出报告。
