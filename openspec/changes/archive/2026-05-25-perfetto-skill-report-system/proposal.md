## Why

Perfetto analysis currently produces ad-hoc markdown in chat with no fixed structure, no template, and no persistent HTML output. The Skill's YAML library has 126 atomic + 33 composite skills with SQL and display metadata, but no mechanism to compose analysis results into a standardized report. Additionally, several skill design issues (trace_processor availability on Windows, FrameTimeline limitations for games, missing trace exploration guidance) block practical use.

## What Changes

### Skill 缺陷修复
- **sql_executor.py**: 支持显式传入 `bin_path` 和 `load_timeout`，解决国内网络下 trace_processor 下载失败问题
- **SKILL.md**: 新增 "Trace 探索与路由" 前置阶段指导 (查询 metadata → 进程列表 → 引擎识别 → 选择技能)
- **game_fps_analysis YAML**: 补充 SurfaceView/Vulkan 游戏的替代帧检测方案文档 (eglSwapBuffers 间隔分析)
- **game_main_loop_jank YAML**: 补充 dequeueBuffer/eglSwapBuffers/GPU completion 等渲染管线关键 slice 的覆盖

### 报告系统 (Skill 内自包含)
- **新增 `templates/chapters/`**: 13 个章节的 data schema YAML (定义 LLM 需要填充什么数据)
- **新增 `templates/chapters/`**: 13 个章节的 render YAML (定义 build_report.py 如何渲染)
- **新增 `templates/fragments/`**: 6 个 Jinja2 HTML 片段 (metric_grid, data_table, conclusion_text, distribution_bar, root_cause_table, severity_badge)
- **新增 `templates/base.html`**: 整体 HTML 框架 (CSS + 布局)
- **新增 `templates/conclusion_data.yaml`**: 结论章节数据定义
- **跨章关联分析**: Phase 2 由 LLM 基于累积 chapter_data 自行完成，不额外提供规则文件
- **新增 `scripts/build_report.py`**: 报表构建脚本 (init → chapter → conclusion → assemble 四个子命令)
- **增量构建工作流**: 每章独立查询 → 渲染 HTML → 保留结构化数据到上下文 → 进入下一章 → 最终跨章关联分析 → 组装报告

### 输出路径
- 开发环境: `data/output/trace_report/<trace_stem>/`
- 打包 exe: `<exe_dir>/output/perfetto_report/<perfetto_name>/`

### 历史面板集成
- `perfetto_capture` 历史面板展示分析报告子节点，支持双击打开 HTML

## Capabilities

### New Capabilities
- `chapter-report-system`: 基于 YAML data schema + Jinja2 fragment 的章节化 HTML 报告系统，支持增量构建和跨章关联分析。所有模板和脚本在 Skill 目录内自包含。
- `cross-chapter-analysis`: 跨章关联分析规则引擎，GPU→FPS、CPU→FPS、Binder→CPU、Thermal→CPU/GPU 等关联规则
- `trace-exploration`: Trace 探索与路由前置流程，metadata + process + thread + engine 识别 + 渲染管线检测

### Modified Capabilities
- `yaml-skill-library`: 扩展 YAML 技能文件的 SQL 替代方案文档 (game_fps_analysis 增加 SurfaceView/Vulkan 帧检测说明；game_main_loop_jank 扩展渲染管线 slice 覆盖)

## Impact

- **Skill 目录**: `skills/perfetto-analysis/templates/` (全新), `skills/perfetto-analysis/ref/cross-chapter-rules.md` (新增), `skills/perfetto-analysis/scripts/build_report.py` (新增)
- **Skill 文件修改**: `SKILL.md` (新增探索路由章节), `atomic/game_fps_analysis.skill.yaml` (补充文档), `atomic/game_main_loop_jank.skill.yaml` (补充覆盖)
- **Python 模块**: `modules/perfetto_analysis/src/service.py` (输出路径适配), `skills/.../scripts/sql_executor.py` (bin_path/load_timeout 支持)
- **依赖模块**: `modules/perfetto_capture/src/history_panel.py` (分析报告子节点展示)
- **不涉及**: `toolkit/` 核心框架, 其他模块, 项目根配置
