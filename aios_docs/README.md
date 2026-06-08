# AIOS 使用说明

> AIOS 是一套用于复杂项目的 AI 协作操作系统模板。它通过配置文件、方法论文档、经验库、Python 工具和 `.aios/` 工作目录，把“聊天驱动”升级为“流程驱动”。

## 一、目录结构

```text
aios_docs/
  README.md                         使用说明
  aios_config.yaml                  每个项目启动前修改的配置文件
  AI项目操作系统总控入口.md           Codex 启动入口
  AI项目操作系统方法论.md             通用方法论
  AI项目操作系统落地架构.md           Python / Codex / LLM 落地架构
  AI项目操作系统项目设计.md           项目初始化设计
  tools/                            固定工具脚本
  experience/                       跨项目经验库
```

## 二、每个文件的作用

### `AI项目操作系统总控入口.md`

新会话启动时让 Codex 先读这个文件。

它会告诉 Codex：

```text
先读配置
再读方法论和经验库
再读原始材料
再扫描源码
先生成证据草案和候选目标
不要第一轮直接改代码
目标必须和用户确认后再冻结
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
```

### `experience/`

跨项目经验库，越用越有价值。

不要因为换项目就删除。

经验分三类：

```text
A 类：强通用经验，启动时作为候选加载，让用户确认
B 类：领域经验，按项目领域需要再读取
C 类：项目特定经验，按源码/项目匹配度需要再读取
```

## 三、第一次使用步骤

### 第 1 步：填写配置

打开：

```text
aios_docs/aios_config.yaml
```

填写：

```yaml
source_code_dir: "/你的/源码/目录"
source_material_file: "/你的/原始材料.md"
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
读取 A 类候选经验
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
```

例如：用户确认“目标正确”时，只表示目标层冻结；下一步只能生成并讨论“需求 / 非需求”草案，不能直接生成规格、样例、流程、检查、验收或任务拆解。

任何阶段都必须先获得用户对当前层的明确确认，再进入下一层。

确认前文件应是：

```text
*.draft.md
```

确认后才生成正式文件：

```text
*.md
```

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
aios_docs/experience/
AI项目操作系统总控入口.md
AI项目操作系统方法论.md
AI项目操作系统落地架构.md
AI项目操作系统项目设计.md
```

这些是模板、工具和经验库。

尤其不要删：

```text
aios_docs/experience/
```

经验库是跨项目资产，越用越有价值。

## 七、哪些东西可以删或重建

可以删或重建：

```text
<source_code_dir>/.aios/
```

它是某个具体项目的运行状态。

如果做新项目，通常不需要删旧项目 `.aios`，只要配置指向新源码目录即可。

如果同一个项目想从零开始，可以归档或删除 `.aios`。

## 八、经验库怎么用

启动时只默认读取：

```text
experience/README.md
experience/经验适用性判断规则.md
experience/通用经验.md
```

A 类强通用经验会形成候选加载清单，让用户选择是否加载。

B 类领域经验不默认加载，例如：

```text
experience/领域经验.md
```

只有当前项目属于对应领域，或用户要求时才读取。

C 类项目特定经验不默认加载，例如：

```text
experience/项目特定经验.md
```

只有源码、项目名、路径、业务上下文高度匹配时才读取。

项目结束或阶段结束时，可以把复用价值高的经验写入：

```text
experience/通用经验.md
experience/领域经验.md
experience/项目特定经验.md
experience/失败教训.md
experience/提示词经验.md
experience/检查规则经验.md
experience/工具经验.md
```

写入经验前必须补全：

```text
经验等级
适用场景
不适用场景
置信度
是否可能过期
过期检查方式
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
aios_docs/ 是固定模板、工具和经验库。
aios_config.yaml 是每次项目启动前要改的配置。
<source_code_dir>/.aios/ 是某个具体项目的运行状态。
```

换项目时：

```text
改 aios_config.yaml
不要删 aios_docs
不要删 experience
必要时删除或归档旧项目的 .aios
```
