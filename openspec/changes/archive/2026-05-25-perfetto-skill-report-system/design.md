## Context

当前 Perfetto 分析完全依赖 LLM 在对话中生成非结构化 markdown，无模板、无持久化标准格式、无跨章关联分析能力。Skill 库已有的 126 个 atomic + 33 个 composite YAML 定义了"查什么"（SQL + display metadata），但缺少"如何展示结果"和"如何关联多个分析维度"的机制。

关键约束：
- **报告系统必须在 Skill 目录内自包含**（`skills/perfetto-analysis/templates/` + `scripts/build_report.py`），不依赖 Python 模块代码
- **LLM 是编排者**：负责选章、执行 SQL、格式化数据，Python 脚本只做确定性渲染
- **增量构建**：每章独立执行→渲染→保留结构化数据，避免一次性全量查询导致上下文膨胀和注意力衰减
- **trace_processor 可用性问题**：国内网络无法访问 Google Cloud Storage 下载二进制

## Goals / Non-Goals

**Goals:**
- 定义 13 个分析章节的 data schema (YAML) 和 render 配置 (YAML)
- 实现 6 个可复用的 Jinja2 HTML 渲染片段
- 实现 `build_report.py` 脚本 (init / chapter / conclusion / assemble 四个子命令)
- 设计增量构建工作流：每章独立查询→渲染→保留结构化数据→最终跨章关联分析
- 跨章关联规则引擎 (GPU↔FPS, CPU↔FPS, Binder↔CPU, Thermal↔CPU/GPU 等)
- Trace 探索与路由前置流程
- sql_executor.py 增加 `bin_path` 和 `load_timeout` 支持
- 历史面板集成分析报告展示

**Non-Goals:**
- 不重构现有 atomic/composite YAML 的 SQL 定义
- 不修改 `toolkit/` 核心框架
- 不改变现有 `pa_execute_sql` 工具接口
- 不实现实时图表渲染（图表占位符预留给后续 JS 库集成）

## Decisions

### 1. data schema 与 render 配置拆分

每个章节拆为两个 YAML 文件：
- `{chapter}_data.yaml` — LLM 加载，定义需要填充的数据字段和格式
- `{chapter}_render.yaml` — build_report.py 加载，定义如何渲染（fragment 类型 + 参数）

**理由**: LLM 不需要知道渲染细节（Jinja2 模板路径、CSS 类名），脚本不需要知道数据来源。拆分后 LLM 每章只加载 ~50 行 YAML，上下文开销最小。

### 2. Fragment 系统

使用 Jinja2 模板引擎，6 个基础 fragment 类型覆盖所有章节渲染需求：

| Fragment | 用途 | 输入 |
|----------|------|------|
| `metric_grid.j2` | 指标卡片网格 | `items: [{label, value, severity}]` |
| `data_table.j2` | 通用数据表格 + 可选分布条 | `columns, rows, show_distribution_bar` |
| `conclusion_text.j2` | 结论区块（评级+总结+亮点+关注点+建议） | `overall_rating, summary, highlights, risks, recommendations` |
| `distribution_bar.j2` | CSS 条形图 | `rows: [{label, percentage}]` |
| `root_cause_table.j2` | 根因卡片列表 | `items: [{severity, cause, evidence, impact, suggestion}]` |
| `severity_badge.j2` | 严重度标签 | 内嵌于其他 fragment 中使用 |

**替代方案考虑**: 最初考虑更细粒度的 fragment（如单个 metric_card、单个 table_row），但会导致章节定义中大量重复的组合逻辑。当前 6 个 fragment 粒度在复用性和简洁性之间取得平衡。

### 3. 增量构建工作流

```
Phase 0: trace探索 → 确定章节列表 → init报告目录 + header
Phase 1: for each chapter:
          1. LLM加载{chapter}_data.yaml (~50行)
          2. 执行对应的atomic skills (1-3个SQL查询)
          3. 格式化结果为chapter_data结构
          4. 写入chapter_data/{chapter}.json (磁盘)
          5. 调用build_report.py chapter → 渲染{chapter}.html (磁盘)
          6. chapter_data保留在上下文 (不额外摘要、不截断)
          7. 清理原始SQL结果 (释放上下文)
Phase 2: LLM加载所有chapter_data + cross-chapter-rules.md
          → 跨章关联分析
          → 生成root_causes + conclusion
          → 渲染root_causes.html + conclusion.html
Phase 3: build_report.py assemble → report.html
```

**关键设计**: 每章结束后清理原始 SQL 结果（几千行），但保留结构化 chapter_data（标签化的指标，自然长度 ~0.5-2KB）。不做人为 token 截断或二次摘要，让 LLM 在 Phase 2 自行判断哪些字段对关联分析重要。

### 4. build_report.py 子命令设计

```bash
build_report.py init      --output-dir <dir> --header '{"trace_name":...}'
build_report.py chapter   --chapter-id fps --data chapter_data.json \
                          --chapters-dir templates/chapters/ \
                          --fragments-dir templates/fragments/ \
                          --output <dir>/chapters/fps.html
build_report.py conclusion --data conclusion.json \
                          --fragments-dir templates/fragments/ \
                          --output <dir>/conclusion.html
build_report.py assemble  --output-dir <dir> \
                          --template templates/base.html \
                          --output <dir>/report.html
```

**理由**: 四个独立子命令对应工作流的四个阶段，每次调用上下文隔离。`chapter` 子命令可被 LLM 在循环中反复调用。

### 5. 输出路径

沿用现有 `service.py` 的路径逻辑：

```python
# service.py _get_output_dir() 修改为:
# Dev:  root_dir/data/output/trace_report/<trace_stem>/
# Exe:  exe_dir/output/perfetto_report/<trace_stem>/
```

每份报告的目录结构：
```
<trace_stem>/
├── header.json
├── chapters/
│   ├── fps.html
│   ├── cpu.html
│   └── ...
├── chapter_data/
│   ├── fps.json
│   ├── cpu.json
│   └── ...
├── conclusion.html
└── report.html
```

### 6. 章节选择逻辑

LLM 根据 Phase 0 的探索结果确定哪些章节需要执行：

| 探索发现 | 必选章节 | 可选章节 |
|---------|---------|---------|
| 游戏进程 (Unity/Unreal) | fps, cpu, gpu, memory | binder, sf, lock |
| 普通应用 | fps, cpu | memory, binder |
| 有启动场景 | startup | — |
| 设备发热/限频 | thermal | power |
| 有 ANR 事件 | binder, lock | io |
| 系统级分析 | sf, io, power | thermal |

规则写入 `chapters/{id}_data.yaml` 的 `trigger` 字段，LLM 根据实际发现的 trace 特征自动选择。

### 7. 跨章关联分析

Phase 2 的跨章关联直接由 LLM 基于累积的 chapter_data 自行完成，不提供额外的规则文件。
领域知识（GPU→FPS 因果关系、GC→Jank 时间关联等）属于分析师能力范畴，
不属于报告模板系统的职责。

## Risks / Trade-offs

- **[Risk] Chapter YAML 与 Atomic YAML 的对应关系可能不精确** → 每个 chapter 的 `trigger.when_skills_used` 显式列出对应的 atomic skills，LLM 据此匹配。若分析中使用了未列出的 skill 但有相关数据，LLM 可自行判断是否包含该章节
- **[Risk] Fragment 类型不够用** → 6 个 fragment 覆盖了当前所有渲染需求。若未来需要新布局（如瀑布图、火焰图），新增 fragment .j2 文件 + 在 render YAML 中引用即可，无需改动架构
- **[Risk] base.html 的 CSS 在不同渲染引擎中表现不一致** → 使用标准 CSS Grid + Flexbox，在常见浏览器中测试。内嵌样式避免外部 CSS 依赖
- **[Trade-off] chapter_data.json 写入磁盘 + 保留在上下文 (双份存储)** → 磁盘用于 build_report.py 渲染和调试追溯，上下文用于 Phase 2 跨章关联。10章 × 2KB = 20KB 在现代模型上下文中可忽略

## 实际验证发现的问题 (2026-05-25)

使用王者荣耀 trace 完整走通分析→报告生成流程后，发现以下问题：

### 问题 1: SKILL.md 未引导 Agent 使用 build_report.py 生成 HTML

**现象**: Agent 分析完成后直接在对话区输出 Markdown 报告，完全没有触发 HTML 报告生成。用户需要明确指出"为什么没有生成 HTML"后，Agent 才开始查找 `build_report.py`。

**根因**: SKILL.md 第 403-437 行的"分析流程"第 8 步写的是"生成分析报告"，指向的却是 Markdown 模板（第 416-437 行）。全文未提及 `scripts/build_report.py` 及其 `init → chapter → conclusion → assemble` 流水线。

**修复方向**: 
- 删除 SKILL.md 中的 Markdown 报告模板（第 415-437 行）
- 新增"报告生成"章节，描述 HTML 报告生成流程
- 明确报告是 HTML 格式，对话区仅输出报告路径和根因摘要

### 问题 2: 报告文件名无标识信息

**现象**: 报告文件名为 `report.html`，无法从文件名辨识对应哪个应用、哪个 trace、什么分析类型。

**根因**: `build_report.py assemble` 的 `--output` 参数完全由调用者决定，没有命名规范指导。

**修复方向**: 在 SKILL.md 中定义命名规范：
```
格式: perfetto-report-{app_short}-{date}-{analysis_type}.html
示例: perfetto-report-sgame-20260402-jank.html
```
其中:
- `app_short`: 从包名提取，如 `com.tencent.tmgp.sgame` → `sgame`
- `date`: trace 文件名中的日期或当前分析日期 (YYYYMMDD)
- `analysis_type`: jank / startup / memory / comprehensive 等

### 问题 3: 报告输出路径不规范

**现象**: 临时脚本将报告放在 `data/output/report-sgame-20260402/`，与 design.md 中约定的 `data/output/trace_report/<trace_stem>/` 不一致。

**根因**: design.md Decision 5 定义了路径规范，但 SKILL.md 中未写入该规范，Agent 不知道标准输出位置。

**修复方向**: 在 SKILL.md 的"报告生成"章节中写入输出路径规范：
```
data/output/trace_report/<trace_stem>/
├── header.json
├── chapters/
│   ├── fps.html
│   ├── cpu.html
│   └── ...
├── chapter_data/
│   ├── fps.json
│   └── ...
├── conclusion.html
└── perfetto-report-{app_short}-{date}-{type}.html
```

### 问题 4: 报告生成需额外写临时脚本

**现象**: Agent 为了生成报告，额外写了一个 `gen_report_sgame.py`（200+ 行）来准备 data JSON 并调用 build_report.py 子命令。这个脚本是一次性的，不可复用。

**根因**: 
1. `build_report.py` 只能通过 CLI subprocess 调用（`sys.exit()` + `argparse.Namespace`），无法作为库导入
2. SKILL.md 没有描述 data JSON 的准备流程，Agent 不知道可以直接在对话中写 JSON 文件 + 运行命令

**修复方向**:
- 方案 A（最小改动）: 更新 SKILL.md，让 Agent 知道可以直接用 Write 工具写 JSON 文件，然后用 Bash 工具调用 build_report.py 命令。不需要中间脚本。
- 方案 B（增强 build_report.py）: 将 `cmd_init/chapter/conclusion/assemble` 从 argparse 重构为普通函数，使其可被 `import` 直接调用，减少 subprocess 开销。
- 推荐：A + B 都做。A 确保 Agent 知道流程，B 提升工具的可用性。

### 问题 5: SKILL.md 报告模板与 HTML 报告系统重复

**现象**: SKILL.md 第 415-437 行定义了一个 Markdown 报告模板，但实际报告系统（build_report.py + templates/）输出的是 HTML。两套模板并存造成混乱。

**根因**: Markdown 模板是早期设计，HTML 报告系统是后续实现的，SKILL.md 未同步更新。

**修复方向**: 删除 Markdown 模板，替换为 HTML 报告生成流程说明。

## 修复规格

### 修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `SKILL.md` | 修改 | 删除 Markdown 模板 → 替换为 HTML 报告生成流程 + 命令速查 |
| `scripts/build_report.py` | 修改 | 导出可 import 的函数，保留 CLI 兼容 |
| `scripts/gen_report_sgame.py` | 删除 | 临时脚本，不应提交 |

### SKILL.md 修改详情

#### 1. 更新分析流程第 8 步 (第 403-412 行)

将:
```
8. 按 YAML 中的 output/thresholds/diagnostics 评估结果
9. 生成分析报告
```
替换为:
```
8. 按 YAML 中的 output/thresholds/diagnostics 评估结果
9. 生成 HTML 报告（参见下方"报告生成"章节）
```

#### 2. 删除 Markdown 报告模板 (第 415-437 行)

整段删除 `## 报告模板` 及其下的 Markdown 模板。

#### 3. 新增"报告生成"章节

在原"报告模板"位置插入：

```markdown
## 报告生成

分析完成后 MUST 使用 `scripts/build_report.py` 生成 HTML 报告，对话区仅输出报告路径和根因摘要。

### 输出路径规范

```
data/output/trace_report/<trace_stem>/
├── header.json
├── chapters/
│   ├── fps.html
│   ├── cpu.html
│   └── ...
├── chapter_data/
│   ├── fps.json
│   └── ...
├── conclusion.html
└── perfetto-report-{app_short}-{date}-{type}.html
```

- `trace_stem`: trace 文件名去后缀，如 `trace-sun-BQ2A....perfetto-trace` → `trace-sun-BQ2A...`
- 最终报告文件名: `perfetto-report-{app_short}-{date}-{type}.html`

### 报告生成流水线

```
Phase 0: init      → 创建输出目录 + header.json
Phase 1: chapter   → 为每个分析章节准备 data JSON → 渲染章节 HTML
Phase 2: conclusion → 准备 conclusion JSON → 渲染结论 HTML
Phase 3: assemble  → 组装所有章节 + 结论 → 生成最终 report.html
```

> **重要**: 了解 build_report.py 的用法和子命令时，执行 `python scripts/build_report.py --help`，禁止阅读源码。

### 命令速查

```bash
# Phase 0: 初始化
python scripts/build_report.py init \
  --output-dir data/output/trace_report/<trace_stem>/ \
  --header '{"trace_name":"...","analysis_time":"..."}'

# Phase 1: 逐章渲染 (以 fps 为例)
# 1) 写入 data JSON 到 chapter_data/fps.json
# 2) 运行 chapter 命令
python scripts/build_report.py chapter \
  --chapter-id fps \
  --data data/output/trace_report/<trace_stem>/chapter_data/fps.json \
  --chapters-dir templates/chapters/ \
  --fragments-dir templates/fragments/ \
  -o data/output/trace_report/<trace_stem>/chapters/fps.html

# Phase 2: 结论
python scripts/build_report.py conclusion \
  --data data/output/trace_report/<trace_stem>/chapter_data/conclusion.json \
  --fragments-dir templates/fragments/ \
  -o data/output/trace_report/<trace_stem>/conclusion.html

# Phase 3: 组装
python scripts/build_report.py assemble \
  -d data/output/trace_report/<trace_stem>/ \
  -t templates/base.html \
  -o data/output/trace_report/<trace_stem>/perfetto-report-{app}-{date}-{type}.html
```

### 章节选择规则

Agent 根据实际运行的分析技能自动选择章节（章节 YAML `trigger.when_skills_used` 定义）：

| 分析场景 | 必选章节 | 触发条件 |
|---------|---------|---------|
| 帧率/卡顿 | fps, root_causes, conclusion | 使用了 game_fps_analysis / game_main_loop_jank |
| CPU/调度 | cpu | 使用了 sched_latency_in_range / cpu_topology_view |
| GPU 渲染 | gpu | 使用了 gpu_metrics / gpu_render_in_range |
| 内存 | memory | 使用了 gc_events_in_range / memory_growth_detector |
| Binder/IPC | binder | 使用了 binder_blocking_in_range |
| 启动 | startup | 使用了 startup_events_in_range |
| (其余按需) | sf, io, power, lock, thermal | 对应 trigger 匹配 |

header 和 root_causes 始终包含。

### data JSON 格式

每个章节的 data JSON 结构：

```json
{
  "title": "章节显示标题",
  "data": {
    "<section_id>": { ... },   // object → metric_grid
    "<section_id>": [ ... ],   // array → data_table
    "<section_id>": null       // null + optional=true → 跳过
  }
}
```

具体字段定义见 `templates/chapters/{chapter_id}_data.yaml`。

### 对话区输出规范

生成 HTML 报告后，对话区仅输出：
1. 报告文件路径（可点击的 markdown 链接）
2. 根因摘要（3-5 条，每条一行，包含严重度标签）

详细数据、表格、图表均在 HTML 报告中，对话区不重复输出。
```

### build_report.py 修改详情

将 4 个命令函数从 `argparse.Namespace` 解耦，新增可直接导入的函数：

```python
# 新增: 可直接导入的便捷函数
def init_report(output_dir: str, header: dict) -> None:
    """初始化报告目录."""

def build_chapter(chapter_id: str, data: dict, output_dir: str,
                  chapters_dir: str | None = None,
                  fragments_dir: str | None = None) -> None:
    """渲染单个章节 HTML."""

def build_conclusion(data: dict, output_dir: str,
                     fragments_dir: str | None = None) -> None:
    """渲染结论 HTML."""

def assemble_report(output_dir: str, template_path: str | None = None,
                    output_path: str | None = None) -> None:
    """组装最终 report.html."""
```

CLI 子命令改为调用上述函数，保持向后兼容。

### 验证方法

1. 使用同一份王者荣耀 trace 重新触发 skill 分析
2. 验证 Agent 主动:
   - 执行 trace 探索 + SQL 分析（现有流程）
   - 写入章节 data JSON 文件到标准输出目录
   - 调用 `build_report.py` 流水线生成 HTML
   - 报告文件名包含 app 名称、日期和分析类型
3. 对话区仅输出报告路径和根因摘要，不再输出完整 Markdown 报告
