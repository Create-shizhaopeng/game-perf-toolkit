## Purpose

Defines the directory structure, file format, and progressive disclosure patterns for the Perfetto analysis YAML skill library used by the perfetto-analysis Skill.
## Requirements
### Requirement: YAML 技能库目录结构

perfetto-analysis Skill 目录下 SHALL 包含以下子目录结构，用于组织 YAML 技能文件：

- `atomic/` — 原子技能（单一 SQL 查询或少量关联查询）
- `composite/` — 组合技能（多步骤分析流程，引用 atomic 技能）
- `deep/` — 深度分析技能（需 simpleperf/perf 数据）
- `modules/` — 跨域专家模块（含 app/framework/kernel/hardware 子目录）
- `pipelines/` — 渲染管线检测技能
- `vendors/` — 供应商覆盖（OEM 特定 SQL 和诊断规则）
- `fragments/` — 共享 SQL CTE 片段（.sql 文件）

#### Scenario: Agent 查找 atomic 技能

- **WHEN** Agent 需要执行特定 PerfettoSQL 查询（如检测 jank）
- **THEN** Agent 读取 `atomic/` 目录下对应的 .skill.yaml 文件，获取 SQL 语句，通过 pa_execute_sql 执行

#### Scenario: Agent 查找 composite 技能

- **WHEN** Agent 需要执行多步分析（如 jank 帧详情分析）
- **THEN** Agent 读取 `composite/` 目录下对应的 .skill.yaml 文件，获取步骤列表和参数传递说明，按步骤编排 pa_execute_sql 调用

### Requirement: YAML 技能文件格式

每个 .skill.yaml 文件 SHALL 遵循 SmartPerfetto 的 YAML 技能格式，包含以下核心字段：

- `name` — 技能唯一标识符
- `type` — 技能类型（atomic/composite/deep/pipeline_definition/comparison）
- `category` — 分类（rendering/hardware/system/binder/...）
- `tier` — 优先级（S/A/B）
- `steps` — 执行步骤列表，每个步骤包含 `id`、`type`、`sql`（atomic 类型）或 `skill`（skill 引用类型）
- `inputs` — 输入参数定义
- `output` — 输出结构定义

#### Scenario: Atomic 技能文件格式验证

- **WHEN** Agent 读取一个 atomic 类型的 .skill.yaml 文件
- **THEN** 文件 MUST 包含 `name`、`type: atomic`、至少一个 `steps[].sql` 字段

#### Scenario: Composite 技能文件格式验证

- **WHEN** Agent 读取一个 composite 类型的 .skill.yaml 文件
- **THEN** 文件 MUST 包含 `name`、`type: composite`、多个 `steps`，其中可以有 `type: skill` 的步骤引用其他 YAML 技能

### Requirement: SKILL.md 场景索引表

SKILL.md SHALL 包含场景索引表，将用户问题模式映射到对应的 YAML 技能文件路径和所需参数。

索引表格式：

| 用户问题模式 | YAML 技能路径 | 关键参数 | 返回结构概要 |

#### Scenario: Agent 通过索引定位技能

- **WHEN** Agent 接收到用户问题（如"分析这帧为什么卡顿"）
- **THEN** Agent 通过 SKILL.md 场景索引表找到对应的 composite YAML 技能路径（如 `composite/jank_frame_detail.skill.yaml`）和所需参数（如 package, start_ts, frame_id）

#### Scenario: 索引表覆盖所有分析场景

- **WHEN** 用户提出 Perfetto 相关分析需求
- **THEN** SKILL.md 索引表 SHALL 能引导 Agent 定位到对应的 YAML 技能，覆盖所有已迁移的 atomic/composite/deep/pipelines 技能

### Requirement: 渐进式披露

SKILL.md 和 YAML 技能库 SHALL 实现三级渐进式披露，避免一次性加载所有内容：

- Level 0 (SKILL.md): 能力概览 + 场景索引表
- Level 1 (composite YAML): 执行流程和步骤说明
- Level 2 (atomic YAML): 具体 SQL 查询和返回数据结构

#### Scenario: Agent 按需加载 Level 1

- **WHEN** Agent 通过 SKILL.md 索引确定需要某个 composite 技能
- **THEN** Agent 读取对应的 composite .skill.yaml 文件，获取步骤列表和参数说明

#### Scenario: Agent 按需加载 Level 2

- **WHEN** Agent 在执行 composite 步骤时需要某个 atomic 技能的 SQL
- **THEN** Agent 读取对应的 atomic .skill.yaml 文件，获取 SQL 语句和返回数据结构

### Requirement: SQL 片段复用

`fragments/` 目录下的 .sql 文件 SHALL 包含可复用的 CTE（Common Table Expression）片段，供 atomic 和 composite 技能的 SQL 通过 `sql_fragments` 字段引用。

#### Scenario: Atomic 技能引用 SQL 片段

- **WHEN** 一个 atomic 技能的 step 包含 `sql_fragments: [fragments/target_threads.sql]`
- **THEN** Agent 读取 fragments/target_threads.sql 的内容，将其作为 CTE 拼接到步骤 SQL 的 WITH 子句中

### Requirement: 供应商覆盖

`vendors/` 目录下的 .override.yaml 文件 SHALL 包含特定 OEM 的额外分析步骤和诊断规则，Agent 根据设备供应商信息选择应用。

#### Scenario: Agent 应用供应商覆盖

- **WHEN** Agent 检测到设备为 Qualcomm 平台
- **THEN** Agent 读取 `vendors/qualcomm/startup.override.yaml`，将 additional_steps 中的 SQL 追加执行

### Requirement: Game FPS analysis supports non-FrameTimeline frame detection

The `game_fps_analysis.skill.yaml` SHALL document that games using SurfaceView + OpenGL ES or Vulkan bypass Android FrameTimeline, and SHALL guide the Agent to fall back to `eglSwapBuffers` or `vkQueuePresentKHR` interval analysis.

The skill SHALL include documentation describing:
- When FrameTimeline data is insufficient (< 20% of expected frames)
- How to identify the rendering thread (`UnityGfxDeviceW`, `GameThread`, etc.)
- How to analyze frame intervals from swap buffer slices

#### Scenario: Agent detects insufficient FrameTimeline data

- **WHEN** `actual_frame_timeline_slice` returns significantly fewer frames than expected (e.g., 154 vs ~900 based on swap count)
- **THEN** the Agent reads the skill's alternative detection documentation
- **AND** switches to swap-based frame interval analysis using `eglSwapBuffers` slices from the rendering thread

#### Scenario: Game with Vulkan rendering

- **WHEN** target process contains `vkQueuePresentKHR` slices instead of `eglSwapBuffers`
- **THEN** the Agent uses `vkQueuePresentKHR` intervals for FPS and jank analysis
- **AND** the analysis follows the same interval-based methodology

### Requirement: Game main loop jank covers rendering pipeline slices

The `game_main_loop_jank.skill.yaml` SHALL cover key rendering pipeline slices beyond engine-specific loops, including:

- `dequeueBuffer` — buffer acquisition wait time
- `eglSwapBuffers` — swap/present operation
- `queueBuffer` — buffer submission to SurfaceFlinger
- `GPU completion` + `waitForever` — GPU fence wait time
- `waitForever` on rendering threads — GPU sync point blocking

These slices SHALL be matched by slice name patterns in the SQL `WHERE` clause, not by thread name alone.

#### Scenario: dequeueBuffer becomes the jank root cause

- **WHEN** the game has 934 dequeueBuffer calls on UnityGfxDeviceW with individual durations up to 31.6ms
- **THEN** `game_main_loop_jank` captures these as `engine_work` phase slices
- **AND** the `slow_engine_slices` step lists the longest dequeueBuffer calls with their timestamps and durations

#### Scenario: GPU completion waitForever indicates fence blocking

- **WHEN** the `GPU completion` thread has 932 `waitForever` calls averaging 2.2ms with max 46.2ms
- **THEN** the skill captures `waitForever` slices in the slow slices list
- **AND** the phase is classified as `present_wait` (waiting for GPU to complete rendering)

