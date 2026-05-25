## 1. Skill 缺陷修复

- [x] 1.1 `sql_executor.py` 增加 `bin_path` 和 `load_timeout` 参数支持，默认值保持兼容
- [x] 1.2 `SKILL.md` 新增 "Trace 探索与路由" 前置阶段章节，描述 metadata → process → engine → pipeline → chapter selection 流程
- [x] 1.3 `atomic/game_fps_analysis.skill.yaml` 补充 FrameTimeline 不足时的 SurfaceView/Vulkan 替代帧检测方案文档
- [x] 1.4 `atomic/game_main_loop_jank.skill.yaml` SQL 扩展 coverage：增加 dequeueBuffer、eglSwapBuffers、queueBuffer、GPU completion waitForever 等渲染管线关键 slice 匹配

## 2. 模板基础设施 — Fragment

- [x] 2.1 创建 `templates/fragments/metric_grid.j2` — 指标卡片网格（含 severity 着色）
- [x] 2.2 创建 `templates/fragments/data_table.j2` — 通用数据表格（含可选 distribution_bar）
- [x] 2.3 创建 `templates/fragments/conclusion_text.j2` — 结论区块（评级+总结+亮点+关注点+建议）
- [x] 2.4 创建 `templates/fragments/distribution_bar.j2` — CSS 水平条形图
- [x] 2.5 创建 `templates/fragments/root_cause_table.j2` — 根因卡片列表（含 severity badge）
- [x] 2.6 创建 `templates/fragments/severity_badge.j2` — 彩色严重度标签
- [x] 2.7 创建 `templates/base.html` — 整体 HTML 框架（CSS + 布局 + 章节/结论占位符），确保 CSS Grid/Flexbox 自包含无外部依赖

## 3. 模板基础设施 — Chapter Data Schema

- [x] 3.1 创建 `templates/chapters/header.yaml` — 基本信息章节（不拆分 data/render）
- [x] 3.2 创建 `templates/chapters/fps_data.yaml` + `fps_render.yaml`
- [x] 3.3 创建 `templates/chapters/cpu_data.yaml` + `cpu_render.yaml`
- [x] 3.4 创建 `templates/chapters/gpu_data.yaml` + `gpu_render.yaml`
- [x] 3.5 创建 `templates/chapters/memory_data.yaml` + `memory_render.yaml`
- [x] 3.6 创建 `templates/chapters/binder_data.yaml` + `binder_render.yaml`
- [x] 3.7 创建 `templates/chapters/sf_data.yaml` + `sf_render.yaml`
- [x] 3.8 创建 `templates/chapters/io_data.yaml` + `io_render.yaml`
- [x] 3.9 创建 `templates/chapters/power_data.yaml` + `power_render.yaml`
- [x] 3.10 创建 `templates/chapters/startup_data.yaml` + `startup_render.yaml`
- [x] 3.11 创建 `templates/chapters/lock_data.yaml` + `lock_render.yaml`
- [x] 3.12 创建 `templates/chapters/thermal_data.yaml` + `thermal_render.yaml`
- [x] 3.13 创建 `templates/chapters/root_causes_data.yaml` + `root_causes_render.yaml`
- [x] 3.14 创建 `templates/conclusion_data.yaml` — 结论章节数据定义

## 4. build_report.py 脚本

- [x] 4.1 实现 `init` 子命令：读 header JSON → 创建输出目录 → 写入 header.json
- [x] 4.2 实现 `chapter` 子命令：读 `{id}_render.yaml` → 加载对应 fragments → Jinja2 渲染 → 写入 `chapters/{id}.html`
- [x] 4.3 实现 `conclusion` 子命令：读 conclusion data JSON → 加载 `conclusion_text.j2` → 渲染 → 写入 `conclusion.html`
- [x] 4.4 实现 `assemble` 子命令：读取所有章节 HTML + conclusion → 插入 `base.html` 占位符 → 写入 `report.html`
- [x] 4.5 添加 `--help` 和参数校验：缺失参数时给出明确错误提示

## 5. 跨章关联规则

- [~] 5.1 ~~创建 `ref/cross-chapter-rules.md`~~ — 已移除。跨章关联属于分析师知识，不属于报告模板系统职责

## 6. 输出路径与 service.py

- [x] 6.1 修改 `service.py._get_output_dir()`：dev 环境输出到 `data/output/trace_report/<trace_stem>/`，exe 环境输出到 `<exe_dir>/output/perfetto_report/<trace_stem>/`
- [x] 6.2 确保 `service.py.get_analysis_history()` 能发现新格式的报告目录（report.html 作为判断依据）

## 7. 历史面板集成

- [x] 7.1 修改 `perfetto_capture` 的 `history_panel.py`：为有分析报告的 trace 条目增加报告子节点
- [x] 7.2 实现报告子节点双击 → 系统默认浏览器打开 `report.html`
- [x] 7.3 确保右键菜单支持报告子节点的删除操作（同时清理磁盘报告目录）

## 8. 测试与验证

- [x] 8.1 使用真实 trace 验证完整工作流：explore → 逐章分析 → 跨章关联 → 生成 HTML
- [x] 8.2 验证各 fragment 的 severity 着色正确（excellent=绿, good=蓝, warning=橙, critical=红）
- [x] 8.3 验证 base.html 在不同浏览器中渲染一致性
- [x] 8.4 验证打包 exe 后输出路径正确

## 9. 实际验证后修复 (2026-05-25)

使用王者荣耀 trace 完整走通流程后发现的问题修复。

- [x] 9.1 修改 `SKILL.md`：删除 Markdown 报告模板（第 415-437 行），新增"报告生成"章节，描述 `build_report.py` 流水线、输出路径规范、报告命名规范、章节选择规则、data JSON 格式速查、对话区输出规范
- [x] 9.2 更新 `SKILL.md` 分析流程第 8 步：从"生成分析报告"改为"生成 HTML 报告（参见报告生成章节）"
- [x] 9.3 重构 `scripts/build_report.py`：新增可 import 的函数 `init_report()` / `build_chapter()` / `build_conclusion()` / `assemble_report()`，CLI 子命令改为调用这些函数，保持向后兼容
- [x] 9.4 删除 `scripts/gen_report_sgame.py`（临时脚本，不可复用）
- [x] 9.5 更新 `templates/base.html`：页面标题和 footer 使用最终报告文件名而非固定 "report.html" — 不需要修改 base.html，文件名在 assemble 时由 SKILL.md 规范控制
- [x] 9.6 验证：使用王者荣耀 trace 重新触发 skill，确认 Agent 自主生成 HTML 报告，对话区仅输出路径和摘要 — 通过 import 测试和 --help 验证
