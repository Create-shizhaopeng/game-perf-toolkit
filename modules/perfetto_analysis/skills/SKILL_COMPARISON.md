# perfetto-analysis vs smart-perfetto 对比

## 目录

- [架构定位](#架构定位)
- [分析范围覆盖](#分析范围覆盖)
- [技能粒度对比](#技能粒度对比)
- [场景覆盖详细对比](#场景覆盖详细对比)
- [渲染管线识别](#渲染管线识别)
- [工具链与执行方式](#工具链与执行方式)
- [扩展与定制能力](#扩展与定制能力)
- [知识资产](#知识资产)
- [核心差异总结](#核心差异总结)
- [互补关系分析](#互补关系分析)

---

## 架构定位

| 维度 | perfetto-analysis | smart-perfetto |
|------|---|---|
| **本质** | Agent 技能文档（MCP 驱动的操作手册） | 结构化技能引擎（YAML + SQL 驱动的流水线） |
| **执行体** | Claude Agent 调用 `pa_*` 工具链 → MCP / 引擎 | Node.js 后端解析 YAML 步骤 → 执行 SQL → 合成结论 |
| **触发方式** | LLM 语义匹配 `description` 字段 | 关键词/正则匹配 + 意图检测 API（`/api/skills/detect-intent`） |
| **运行环境** | Claude Code / agent_chat 会话 | Node.js 后端服务（REST API + CLI） |
| **输出格式** | Markdown 分析报告（Agent 生成） | 结构化 JSON（带 thresholds / diagnostics / suggestions） |
| **决策机制** | Agent 按 SOP 文档逐步推理 | YAML 定义的条件分支 + `for_each` 循环 + 变量引用 |
| **文件形态** | Markdown 文档 | YAML 配置文件（`*.skill.yaml`）+ SQL 片段 |

---

## 分析范围覆盖

| 维度 | perfetto-analysis | smart-perfetto | 胜出 |
|------|---|---|---|
| **场景 SOP** | 9 个场景 SOP | 28 个 composite + 80+ atomic skill | smart-perfetto |
| **渲染管线** | 5 类手动识别（表格匹配） | 31 个 pipeline skill 自动检测（含评分机制） | smart-perfetto |
| **厂商适配** | 无 | Pixel / Samsung / OPPO / vivo / 小米 / Honor，继承 + 覆盖机制 | smart-perfetto |
| **跨域推理** | 无（Agent 自行判断） | 9 个模块专家系统，带对话协议 + 假设-验证循环 | smart-perfetto |
| **深度分析** | 10 维度分析 | deep 层（调用栈、CPU Profiling）+ 假设验证 | smart-perfetto |
| **功耗分析** | 无 | Battery drain、Thermal throttling、Wattson 功耗归因 | smart-perfetto |
| **网络/中断** | 无 | Network analysis、IRQ analysis、LMK kill 归因 | smart-perfetto |
| **多 trace 对比** | subagent 隔离分析 | multi_trace_result_comparison skill | smart-perfetto |
| **自有工具链** | 16 个 pa_* 工具 + MCP / 引擎 | 纯 SQL 查询（依赖 Perfetto SQL 引擎） | 各有侧重 |
| **案例库/模式库** | 2 个案例 + 5 个根因模式 | 无独立案例库（厂商 override 覆盖真实场景） | perfetto-analysis |
| **SOP 文档** | 9 个场景 SOP，含详细步骤指引 | 2 个 SOP（startup / scrolling），但 YAML 本身自解释 | 各有侧重 |

---

## 技能粒度对比

| 层级 | perfetto-analysis | smart-perfetto |
|------|---|---|
| **最小单元** | `pa_analyze_dimension(dimension)` 调用 | 单条 SQL 查询（1 atomic skill = 1 SQL） |
| **组合层** | SOP 文件（9 个，按场景组织 Markdown） | Composite skill（多步骤 YAML，支持 `for_each` 循环 / 条件分支 / 变量引用） |
| **深度层** | 无独立层 | Deep skill（调用栈级、CPU Profiling） |
| **模块层** | 无 | Modules（4 层 9 个专家：App / Framework / Kernel / Hardware，带 `dialogue.capabilities` / `findingsSchema` / `suggestionsSchema`） |
| **厂商层** | 无 | Vendors（继承 + 覆盖机制，`extends` 语法） |
| **管线层** | 渲染管线表格（手动匹配特征） | Pipelines（31 个自动检测 skill，带 `detection` 评分 + `teaching` 教学内容 + `auto_pin` 轨道固定） |
| **配置层** | 无（硬编码在 Markdown 中） | `config/` 目录（`conclusion_scene_templates.yaml` 等，结论模板可配置） |
| **总文件数** | ~20 个 Markdown 文件 | ~220 个文件（136 YAML + 3 SQL + 4 Markdown + 31 pipeline + ~30 vendors/modules） |
| **维护方式** | 手动编辑 Markdown | YAML 定义 + 验证器（`npm run skill:validate`）+ 测试器（`npm run skill:test`） |

---

## 场景覆盖详细对比

### 场景 SOP 对照表

| 场景 | perfetto-analysis SOP | smart-perfetto Composite | smart-perfetto Atomic（部分） |
|------|---|---|---|
| **卡顿/掉帧** | `jank-analysis.md` | `jank_frame_detail.skill.yaml`、`scrolling_analysis.skill.yaml` | `consumer_jank_detection`、`frame_production_gap`、`frame_overrun_summary`、`frame_ui_time_breakdown`、`pipeline_4feature_scoring` |
| **启动性能** | `startup-analysis.md` | `startup_analysis.skill.yaml`、`startup_detail.skill.yaml` | `startup_binder_in_range`、`startup_breakdown_in_range`、`startup_class_loading_in_range`、`startup_critical_tasks`、`startup_events_in_range`、`startup_freq_rampup`、`startup_gc_in_range`、`startup_hot_slice_states`、`startup_jit_analysis`、`startup_main_thread_states_in_range`、`startup_slow_reasons`、`startup_thread_blocking_graph` 等 15+ |
| **ANR/无响应** | `anr-analysis.md` | `anr_analysis.skill.yaml`、`anr_detail.skill.yaml` | `anr_context_in_range`、`anr_main_thread_blocking` |
| **内存问题** | `memory-analysis.md` | `memory_analysis.skill.yaml` | `memory_growth_detector`、`memory_pressure_in_range`、`memory_rss_high_watermark`、`native_heap_breakdown`、`page_fault_in_range` |
| **CPU/线程** | 维度分析（Step 4/5） | `cpu_analysis.skill.yaml` | `cpu_topology_detection`、`cpu_topology_view`、`cpu_utilization_per_period`、`cpu_freq_timeline`、`cpu_idle_analysis`、`cpu_load_in_range`、`cpu_cluster_load_in_range`、`cpu_time_per_frame`、`linux_sched_latency_distribution`、`linux_runqueue_depth_timeline` |
| **Binder** | 维度分析 | `binder_analysis.skill.yaml`、`binder_detail.skill.yaml` | `binder_in_range`、`binder_blocking_in_range`、`binder_root_cause`、`binder_storm_detection`、`blocking_chain_analysis` |
| **SurfaceFlinger** | `jank-analysis.md` SF 维度 | `surfaceflinger_analysis.skill.yaml` | `sf_composition_in_range`、`sf_layer_count_in_range`、`sf_frame_consumption` |
| **输入时延** | `input-latency.md` | `click_response_analysis.skill.yaml`、`click_response_detail.skill.yaml` | `input_events_in_range`、`input_to_frame_latency`、`touch_to_display_latency`、`scroll_response_latency` |
| **IO 阻塞** | `io-block-analysis.md` | `block_io_analysis.skill.yaml`、`io_pressure.skill.yaml` | `main_thread_file_io_in_range`、`futex_wait_distribution`、`cache_miss_impact` |
| **响应时延** | `response-latency.md` | `click_response_analysis.skill.yaml` | `main_thread_sched_latency_in_range`、`main_thread_states_in_range`、`main_thread_slices_in_range` |
| **转屏/配置变更** | `rotation-analysis.md` | `navigation_analysis.skill.yaml` | `app_lifecycle_in_range`、`textureview_producer_frame_timing` |
| **通用/不明确** | `general-analysis.md` | `scene_reconstruction.skill.yaml`、`state_timeline.skill.yaml` | `device_state_snapshot`、`device_state_timeline`、`app_process_starts_summary` |
| **热节流** | — | `thermal_throttling.skill.yaml`、`thermal_throttling_chain.skill.yaml` | `thermal_predictor` |
| **功耗分析** | — | `power_consumption_overview.skill.yaml`、`battery_drain_attribution.skill.yaml` | `battery_charge_timeline`、`battery_doze_state_timeline`、`wattson_app_startup_power`、`wattson_rails_power_breakdown`、`wattson_thread_power_attribution` |
| **GC 分析** | 维度分析 | `gc_analysis.skill.yaml` | `gc_events_in_range` |
| **锁竞争** | 维度分析 | `lock_contention_analysis.skill.yaml` | `lock_contention_in_range` |
| **GPU 分析** | 维度分析 | `gpu_analysis.skill.yaml` | `gpu_metrics`、`gpu_freq_in_range`、`gpu_frequency_analysis`、`gpu_render_in_range`、`gpu_power_state_analysis`、`mali_gpu_power_state`、`fence_wait_decomposition`、`present_fence_timing` |
| **网络分析** | — | `network_analysis.skill.yaml` | — |
| **中断分析** | — | `irq_analysis.skill.yaml` | `linux_irq_summary` |
| **LMK 分析** | — | `lmk_analysis.skill.yaml` | `lmk_kill_attribution`、`oom_adjuster_score_timeline` |
| **多 trace 对比** | subagent 隔离 | `multi_trace_result_comparison.skill.yaml` | — |
| **滑动分析** | — | `scrolling_analysis.skill.yaml`、`scroll_session_analysis.skill.yaml` | （见卡顿类） |
| **Flutter** | 渲染管线表格 | `flutter_scrolling_analysis.skill.yaml` | `rn_bridge_to_frame_jank`、`rn_fabric_render_jank` |
| **WebView** | 渲染管线表格 | `webview_drawfunctor_jank_chain.skill.yaml` | `webview_v8_analysis` |
| **Compose** | — | `compose_recomposition_hotspot.skill.yaml` | — |
| **系统挂起/唤醒** | — | `suspend_wakeup_analysis.skill.yaml` | `wakelock_tracking`、`kernel_wakelock_summary` |

**数量对比**：perfetto-analysis 覆盖 **9 个场景**；smart-perfetto 覆盖 **28 个 composite + 80+ atomic + 31 pipelines + 9 modules = 140+ 技能**。

---

## 渲染管线识别

| 维度 | perfetto-analysis | smart-perfetto |
|------|---|---|
| **识别方式** | 表格手动匹配（根据 `RenderThread`、`eglSwapBuffers`、`vkQueuePresentKHR` 等线程名特征） | 31 个 pipeline skill，每个带 `detection` 评分机制（`required_signals` AND + `exclude_if` OR + `scoring_signals` 加权） |
| **覆盖管线数** | 5 类 | 31 种 |
| **管线家族** | HWUI / 游戏 EGL / 游戏 Vulkan / Flutter / WebView | HWUI（6 种）/ Surface（4 种）/ Graphics API（3 种）/ Flutter（3 种）/ WebView（5 种）/ React Native（3 种）/ Specialized（7 种） |
| **教学内容** | 无 | `teaching` 字段（Mermaid 序列图 + 线程角色 + 关键 slice） |
| **自动固定轨道** | 无 | `auto_pin` 字段（正则匹配轨道名 + 优先级 + 智能过滤 SQL） |
| **React Native** | 无 | RN Old Arch / New Arch Fabric / RN Skia（3 种） |
| **Blast Buffer** | 无 | SurfaceView Blast / Android View Standard Blast |
| **VRR/LTPO** | 无 | Variable Refresh Rate pipeline + `vrr_detection` atomic |

### smart-perfetto 管线检测评分示例

```yaml
detection:
  required_signals:                 # 必须全部满足
    - thread: "RenderThread"
      min_count: 1
    - slice_pattern: "Choreographer*"
      min_count: 1
  scoring_signals:                  # 加权评分
    - signal: blast_buffer
      slice_pattern: "*BLAST*"
      weight: 30
      min_count: 1
  exclude_if:                       # 任一命中则排除
    - thread: "CrRendererMain"      # WebView 渲染器
```

---

## 工具链与执行方式

### perfetto-analysis 工具链

```
Agent 调用 pa_* 工具
  ├─ pa_trace_overview       → 引擎（trace 元数据）
  ├─ pa_detect_jank          → 引擎（VSync 帧检测）
  ├─ pa_analyze_dimension    → MCP 优先 / 引擎降级（10 维度）
  ├─ pa_execute_sql          → MCP（任意 SQL）
  ├─ pa_find_slices          → MCP（slice 模式搜索）
  ├─ pa_analyze_anr          → MCP（ANR 检测）
  ├─ pa_analyze_memory       → MCP（内存泄漏）
  ├─ pa_read_knowledge       → 文件系统（两级加载：目录/锚点）
  ├─ pa_cpu_overview         → MCP（CPU 全局概览）
  ├─ pa_thread_state_summary → MCP（线程状态分布）
  ├─ pa_cpu_freq_analysis    → MCP（频率分析）
  ├─ pa_compress_results     → 本地（结果压缩）
  ├─ pa_analyze              → 引擎（全流程 + 报告）
  ├─ pa_parse                → 引擎（仅 Phase 1）
  └─ pa_history              → DB（历史记录）
```

- **自动路由**：pa_* 工具内部优先 MCP，失败降级引擎
- **结果压缩**：自动压缩 MCP 返回数据，防止上下文膨胀
- **链式记录**：每次调用记录 step chain，用于历史回溯

### smart-perfetto 执行流程

```
用户问题 → /api/skills/detect-intent
  → 匹配 Skill triggers（keywords / patterns）
  → 选择对应 Skill（atomic / composite / deep / module）
  → 检测厂商（trace 内容匹配 vendor tag）
  → 加载 vendor override（如有）
  → 执行 steps（逐条 SQL，支持 for_each / 变量引用 / 子查询）
  → 应用 thresholds 判断 severity
  → 生成 diagnostics
  → 输出结构化结果
```

- **SQL 驱动**：每个 step 是一条 SQL 查询，结果存入变量供后续步骤引用
- **循环支持**：`for_each` 遍历前一步结果
- **阈值判断**：`thresholds` 定义 excellent / good / warning / critical
- **诊断规则**：`diagnostics` 定义 condition + severity + suggestions
- **变量系统**：`${package}` / `${item.xxx}` / `${prev.xxx}` / `${vendor}`

---

## 扩展与定制能力

| 维度 | perfetto-analysis | smart-perfetto |
|------|---|---|
| **新增场景** | 创建新的 `.md` SOP 文件 + 更新 SKILL.md 路由表 | 创建 `.skill.yaml` 文件（自动加载） |
| **新增维度** | 修改引擎代码 `src/engine/` 或添加 MCP SQL | 新增 atomic skill（1 SQL = 1 skill） |
| **厂商适配** | 无 | `vendors/` 目录，`extends` 继承机制覆盖阈值/步骤 |
| **阈值调整** | 硬编码在 Markdown 中 | `config/` 集中管理（`conclusion_scene_templates.yaml`） |
| **SQL 复用** | `sql-patterns.md`（手动复制） | `fragments/` 目录（SQL CTE 片段） |
| **验证机制** | 无（人工检查 Markdown） | `npm run skill:validate`（YAML 语法 + SQL 语法 + 变量引用） |
| **测试机制** | 无 | `npm run skill:test -- --trace xxx`（指定 trace 执行） |
| **自定义技能** | 无独立目录 | `custom/` 目录（用户可自由编辑） |
| **API 管理** | 无 | CRUD API（`/api/admin/skills`）+ 热重载（`/api/admin/skills/reload`） |

---

## 知识资产

| 类型 | perfetto-analysis | smart-perfetto |
|------|---|---|
| **案例库** | 2 个案例（LoLM 误报、Face Unlock 音频卡顿）+ 模板 | 无独立案例库 |
| **根因模式** | 5 个模式（VSync 误报、IO Block x2、HWC 超时、CPU 抢占）+ 模板 | 无独立模式库（但厂商 override 含真实场景适配） |
| **SQL 模板** | `sql-patterns.md`（手动查阅） | `fragments/`（3 个 SQL 片段：`target_threads.sql`、`thread_states_quadrant.sql`、`vsync_config.sql`） |
| **设备调优** | `ref/device-tuning.md` | — |
| **环境配置** | `ref/environment-setup.md` | — |
| **设备调优** | `ref/device-tuning.md` | 内置在 atomic skill 中（如 `cpu_cluster_load`、`thermal_predictor`） |

---

## 核心差异总结

### perfetto-analysis 的特点

1. **Agent 操作手册**：用自然语言告诉 Agent 按什么顺序调用什么工具，适合 LLM 驱动的交互式分析
2. **工具链深度绑定**：16 个 pa_* 工具提供自动路由、降级、压缩、链式记录，无需手动写 SQL
3. **知识沉淀**：案例库 + 根因模式库记录了真实 trace 的验证经验
4. **轻量易改**：~20 个 Markdown 文件，直接编辑即可，无编译/验证流程
5. **批量编排**：subagent 隔离策略 + compact 模式，防止多 trace 上下文膨胀

### smart-perfetto 的特点

1. **技能执行引擎**：YAML 定义的技能是可直接执行的流水线，不是操作指南
2. **精细度高**：80 个 atomic skill = 80 个独立 SQL 查询，可任意组合成 composite
3. **自动化检测**：渲染管线 31 种自动评分检测，不需要人工识别特征
4. **厂商生态**：6 家厂商的 override 机制，支持继承覆盖，适配 Android 碎片化
5. **跨域推理**：假设-验证循环 + 模块间对话协议（scheduler 发现异常 → 自动建议查 binder）
6. **覆盖范围极广**：功耗、热节流、网络、中断、LMK、系统挂起唤醒等，远超 perfetto-analysis
7. **工程化成熟**：validate + test + API + 热重载 + 自定义目录

---

## 互补关系分析

| 能力 | perfetto-analysis | smart-perfetto | 互补点 |
|------|---|---|---|
| **自然语言交互** | 擅长（Agent 对话） | 弱（API/CLI） | perfetto-analysis 可作为 smart-perfetto 的前端交互层 |
| **自动化 SQL 执行** | 弱（需 Agent 手写 SQL 或调 pa_*） | 擅长（预定义流水线） | smart-perfetto 的 SQL 可沉淀为 pa_* 工具或 MCP 工具 |
| **场景覆盖** | 9 个核心场景 | 140+ 技能 | perfetto-analysis 可引用 smart-perfetto 的 composite 结果 |
| **知识沉淀** | 案例库 + 模式库 | 无 | perfetto-analysis 的案例可作为 smart-perfetto 的阈值校准数据 |
| **渲染管线** | 5 类表格匹配 | 31 种自动检测 | smart-perfetto 的 pipeline 检测结果可注入 perfetto-analysis 的 Step 3 |
| **批量分析** | subagent 隔离 | 无独立编排 | perfetto-analysis 的批量编排能力可调度 smart-perfetto 的 SQL 技能 |
| **厂商适配** | 无 | 6 家厂商 | smart-perfetto 的 vendor override 可提升 perfetto-analysis 分析精度 |

**最佳协作方式**：smart-perfetto 提供结构化的 SQL 技能库作为**执行后端**，perfetto-analysis 提供自然语言交互和案例模式库作为**分析前端**——用户用自然语言描述问题，perfetto-analysis 进行场景路由后，调用 smart-perfetto 的预定义 SQL 技能执行分析，再结合案例库和模式库进行归因判断。
