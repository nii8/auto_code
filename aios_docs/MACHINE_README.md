# AIOS 机器读内部说明

> 本文件主要给 Codex / AIOS 内部流程读取，不是人类用户的主 README。人类用户请优先阅读仓库根目录 `README.md`。AIOS 通过配置文件、方法论文档、Python 工具和 `.aios/` 工作目录，把“聊天驱动”升级为“流程驱动”。经验库是可选扩展，不是初始项目必需组件。

## 一、目录结构

```text
aios_docs/
  MACHINE_README.md                 给 AI / Codex 读取的内部说明
  aios_config.yaml                  可提交模板配置，不写真实路径
  AI项目操作系统总控入口.md           Codex 启动入口
  AIOS内核运行路线图.md              启动到执行的流程顺序索引
  AI项目操作系统方法论.md             通用方法论
  AI项目操作系统落地架构.md           Python / Codex / LLM 落地架构
  AI项目操作系统项目设计.md           项目初始化设计
  tools/                            固定工具脚本
  experience/                       可选：跨项目经验库，初始项目可不存在
```

## 二、每个文件的作用

### `AI项目操作系统总控入口.md`

新会话启动时让 Codex 先读这个文件。

它会告诉 Codex：

```text
先读 AIOS 内核运行路线图
再读配置
再读方法论 / 架构 / 项目设计
如果经验库存在则按需读取
再读原始材料
再扫描源码
先生成证据草案和候选目标
不要第一轮直接改代码
目标必须和用户确认后再冻结
```

### `AIOS内核运行路线图.md`

新会话的流程顺序索引。

它不会替代方法论和项目设计，只帮助 Codex 快速抓住主线：

```text
配置缺失时如何问用户
第一轮只初始化
逐层冻结顺序
Codex + Claude Code 如何协作拆任务
任务图如何融合确认
Runner 如何执行
证据闸门和人工闸门如何触发
```

### `aios_config.yaml`

每次换项目主要改这个文件。

最重要的字段：

```yaml
source_code_dir: ""       # 源码目录
source_material_file: ""  # 原始材料文件
initial_goal_hint: ""     # 可选，当前阶段目标提示
```

AIOS 工作目录固定为：

```text
<source_code_dir>/.aios/
```

### `tools/`

固定工具目录，通常不要删。

当前包含：

```text
config_loader.py   读取 aios_config.yaml
llm_client.py      调用 OpenAI-compatible LLM，例如 qwen3.6-plus
codex_runner.py    调用 codex exec
check_runner.py    基础确定性检查
state_manager.py   管理 .aios/state.json
aios_runner.py     通用 AIOS 执行器：读取任务图并调用 Codex Worker
```

### `experience/`

可选的跨项目经验库。

初始项目可以没有 `experience/` 目录，也可以是空目录；没有经验库时，AIOS 直接跳过经验加载，不影响启动。

只有当项目运行或复盘后确实沉淀了可复用内容，才需要创建经验库。经验只能作为候选参考，不能替代当前项目的目标确认和逐层冻结。

## 三、第一次使用步骤

### 第 1 步：填写配置

打开：

```text
aios_docs/aios_config.yaml
```

填写：

```yaml
source_code_dir: ""
source_material_file: ""
initial_goal_hint: "可选，一句话描述当前想做什么"
```

如果不填，Codex 启动后会询问你。

### 第 2 步：启动 Codex

在新会话里输入：

```text
请读取 aios_docs/AI项目操作系统总控入口.md，按其中流程启动 AIOS。
```

### 第 3 步：第一轮只初始化

第一轮只做：

```text
读取配置
读取方法论
如果经验库存在，读取候选经验；如果不存在则跳过
读取原始材料
扫描源码目录
生成证据草案
生成候选目标草案
和用户讨论目标
```

第一轮不要做：

```text
改代码
删除文件
运行生产任务
上传发布
冻结目标
```

### 第 4 步：逐层确认

AIOS 的底层规则是：一次只确认一层，不能打包确认。

按顺序确认并冻结：

```text
目标
需求 / 非需求
规格
样例
流程
检查
验收
任务拆解请求
任务图
AIOS Runner 执行
```

例如：用户确认“目标正确”时，只表示目标层冻结；下一步只能生成并讨论“需求 / 非需求”草案，不能直接生成规格、样例、流程、检查、验收或任务拆解。

任何阶段都必须先获得用户对当前层的明确确认，再进入下一层。

任务拆解请求确认后，不应直接在当前聊天里裸写业务代码。正确做法是：

```text
1. 将任务拆解请求转换为 `.aios/tasks/task_graph.md` 和 `.aios/tasks/task_graph.json`。
2. 使用通用 AIOS Runner 读取已冻结上下文、任务图和状态机。
3. Runner 调用 Codex Worker 执行单个明确任务。
4. Runner 保存运行日志、检查结果和状态更新。
5. 低风险任务可继续执行；失败或高风险时停下让用户确认。
```

也就是说，聊天负责确认方向和规则；执行阶段以文件、任务图、Runner、Codex Worker 和检查器为准。

普通用户不需要记住底层 Runner 命令，优先使用仓库根目录的交互式入口：

```bash
python3 aios.py
```

启动后会进入类似 Codex / OpenCode 的交互式驾驶舱：

```text
aios> run
aios> status
aios> preview
aios> doctor
aios> reset
aios> 这一步为什么失败？
aios> exit
```

直接回车或输入 `run`，AIOS 会先做依赖预检，再自动推进；遇到失败、高风险、阻塞或需要用户决策时，不会退出程序，而是停在 `aios>` 输入区，打印失败信息并等待用户自然语言输入。中文别名仍可用，例如“继续”“状态”“重置”。

自动推进过程中，低风险和普通开发任务会连续执行；遇到以下情况会停下来：

```text
任务失败
检查不通过
任务被标记为高风险
依赖缺失或任务阻塞
超过最大步数 / 最大修复次数
需要用户做产品取舍或验收判断
```

停下来之后，用户不需要理解底层 JSON，可以直接用自然语言继续：

```text
status    看卡在哪里
run       修复后继续跑
preview   看下一步准备做什么
doctor    检查依赖和运行环境
reset     清掉已生成业务代码和运行日志，从任务图重新演练
```

Runner 会保留 `.aios/context/`、`.aios/workflow/`、`.aios/checks/`、`.aios/tasks/` 等已确认资产；`reset` 只清理业务代码、任务产物和运行日志，用于重新演练执行流程。

AIOS 的完成判断遵守证据闸门：

```text
没有证据，不允许宣布完成。
检查器结论优先于 AI 自评。
关键用户流程必须尽量被自动模拟。
负向场景必须进入检查范围。
缺依赖等普通环境问题应前置自动处理，不转嫁给用户手工排查。
目标冲突、高风险操作、连续失败才进入人工闸门。
```

底层等价命令是 `python3 aios_docs/tools/aios_runner.py ...`，主要给调试和扩展时使用。

确认前文件应是：

```text
*.draft.md
```

确认后才生成正式文件：

```text
*.md
```

## 三点四、rebuild 重构模式

rebuild 模式用于“旧项目只读参考，新项目从零重构”。

```text
project_mode: rebuild
target_source_dir: 新项目目录，可写
reference_source_dirs: 旧项目目录，只读
source_material_file: 聊天记录 / 需求说明
```

AIOS / Codex Worker 必须遵守：

```text
只能读取 reference_source_dirs。
只能写入 target_source_dir。
第一轮先生成 legacy_analysis、project_overview、initiative_index，不写代码。
```

## 三点五、多阶段和串行执行

复杂项目可以使用 initiative 管理多阶段、多需求：

```text
.aios/initiatives/I001_xxx/
.aios/initiatives/I002_xxx/
.aios/changes/CR.../
```

当前执行策略固定为串行：

```text
同一时间只执行一个 active initiative。
同一时间只执行一个任务。
不做并发 Worker、文件锁并发或 git worktree 并发。
```

简单项目仍可使用 `.aios/context`、`.aios/tasks` 等单 initiative 兼容模式。

## 四、运行中产生的文件在哪里

运行中所有项目状态和中间产物放在：

```text
<source_code_dir>/.aios/
```

典型结构：

```text
.aios/
  source/      原始材料副本或索引
  evidence/    事实、痛点、需求、样例等证据草案
  context/     目标、需求、规格、样例、验收标准
  workflow/    流程、执行策略、人工闸门策略
  checks/      检查规则
  tools/       项目内辅助工具，可选
  tasks/       任务拆解请求、任务图、当前任务
  runs/        运行日志、LLM 调用记录、Codex 调用记录
  reports/     阶段报告和最终报告
  state.json   状态机当前状态
```

## 五、换一个新项目怎么做

### 情况 A：换到另一个源码目录

只需要修改：

```text
aios_docs/aios_config.yaml
```

改成新的：

```yaml
source_code_dir: "/新的/源码/目录"
source_material_file: "/新的/原始材料.md"
initial_goal_hint: "新的阶段目标提示，可空"
```

然后新会话重新启动：

```text
请读取 aios_docs/AI项目操作系统总控入口.md，按其中流程启动 AIOS。
```

旧项目的 `.aios/` 会留在旧源码目录，不影响新项目。

### 情况 B：同一个源码目录重新开始

如果你想丢弃当前项目运行状态，可以删除：

```text
<source_code_dir>/.aios/
```

命令示例：

```bash
trash <source_code_dir>/.aios
```

如果没有 `trash`，可以先改名归档：

```bash
mv <source_code_dir>/.aios <source_code_dir>/.aios_archive_YYYYMMDD
```

不建议直接 `rm -rf`，避免误删。

### 情况 C：同一个源码目录继续上次项目

不要删除 `.aios/`。

直接重新启动 Codex，让它读取：

```text
<source_code_dir>/.aios/state.json
```

继续上次状态。

## 六、哪些东西不要删

不要删：

```text
aios_docs/
aios_docs/tools/
AI项目操作系统总控入口.md
AI项目操作系统方法论.md
AI项目操作系统落地架构.md
AI项目操作系统项目设计.md
```

这些是 AIOS 模板和工具。

`aios_docs/experience/` 是可选经验库：初始项目可以没有；只有里面已经沉淀了用户明确要保留的跨项目经验时，才需要保留。
## 七、哪些东西可以删或重建

可以删或重建：

```text
<source_code_dir>/.aios/
```

它是某个具体项目的运行状态。

如果做新项目，通常不需要删旧项目 `.aios`，只要配置指向新源码目录即可。

如果同一个项目想从零开始，可以归档或删除 `.aios`。

## 八、经验库怎么用

经验库是可选扩展。

启动时按这个规则处理：

```text
如果 aios_docs/experience/ 不存在：跳过经验加载。
如果 aios_docs/experience/ 存在但为空：跳过经验加载。
如果 aios_docs/experience/ 存在且有文件：只把经验作为候选参考，先说明适用场景，再让用户确认是否启用。
```

初始项目不应该预置具体经验。经验应该来自后续真实项目运行、失败教训、复盘或用户明确要求保存的规则。

经验不能用于：

```text
替用户决定目标
跳过逐层确认
把旧项目规则强加到新项目
绕过当前项目证据和用户确认
```

## 九、常用命令

测试配置是否能读取：

```bash
python3 aios_docs/tools/config_loader.py
```

检查配置里的路径是否存在：

```bash
python3 aios_docs/tools/check_runner.py paths
```

测试 LLM 是否可用：

```bash
python3 aios_docs/tools/llm_client.py --config aios_docs/aios_config.yaml '请只回复：AIOS_LLM_OK'
```

调用 Codex 执行一个任务：

```bash
python3 aios_docs/tools/codex_runner.py --config aios_docs/aios_config.yaml '请阅读项目目录并总结结构，不要修改文件'
```

初始化状态文件：

```bash
python3 aios_docs/tools/state_manager.py --config aios_docs/aios_config.yaml init
```

查看状态：

```bash
python3 aios_docs/tools/state_manager.py --config aios_docs/aios_config.yaml show
```

## 十、最重要原则

```text
aios_docs/ 是固定模板和工具；经验库是可选扩展。
aios_config.yaml 是可提交模板配置；aios_config.local.yaml 是本地真实项目配置，不提交。
<source_code_dir>/.aios/ 是某个具体项目的运行状态。
```

换项目时：

```text
写入或更新 aios_config.local.yaml
不要删 aios_docs
如果 experience 存在且有用户确认保留的经验，不要误删
必要时删除或归档旧项目的 .aios
```
