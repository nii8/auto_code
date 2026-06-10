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

如果内容冲突，优先级为：用户当前明确指令 > 总控入口 > 本路线图 > 方法论/架构/项目设计 > 经验库。

## 2. 配置缺失时不要让用户改 YAML

如果 `source_code_dir` 或 `source_material_file` 缺失，直接在对话里问：

```text
我需要两个信息：
1. 源码目录在哪里？
2. 原始材料 / 聊天记录文件在哪里？
```

用户回答后，Codex 自动写入 `aios_docs/aios_config.local.yaml`。`aios_config.yaml` 是可提交模板，不写真实机器路径；`aios_config.local.yaml` 是本地动态配置，不提交。

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
读取配置 → 读取 AIOS 内核文档 → 读取原始材料 → 扫描源码 → 生成证据草案和候选目标 → 和用户讨论目标
```

第一轮不能：

```text
修改业务代码
冻结目标
生成完整任务图
调用 Runner 执行生产任务
把后续层级一次性打包确认
```

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

复杂项目不要把多个目标混在同一套 `goal.md` 里，应使用 initiative：

```text
.aios/initiatives/I001_mvp/
.aios/initiatives/I002_login/
.aios/initiatives/I003_admin_dashboard/
```

每个 initiative 是一个阶段、一个需求包或一个相对独立目标。

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

不能接受：

```text
“我已经完成了”，但没有检查。
“应该可以运行”，但没有运行。
“页面已经做好”，但没有页面结构、浏览器、截图或 DOM 证据。
“流程已完成”，但没有从输入到结果的端到端验证。
“没问题”，但没有负向场景。
```

## 10. 用户角色

用户不当代码消防员。用户主要负责：确认目标、做产品取舍、授权高风险操作、处理连续失败后的方向判断、做最终主观验收。

AIOS / Codex Worker / Runner 负责：读材料、梳理目标、生成草案、执行代码任务、自动检查、自动修普通错误、保存证据、输出报告。
