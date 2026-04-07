# Task Breakdown: Jank 自动检测与抓取

## 目录

- [任务总览](#任务总览)
- [Phase 1: 核心服务层](#phase-1-核心服务层)
- [Phase 2: 后台 Worker](#phase-2-后台-worker)
- [Phase 3: GUI 组件](#phase-3-gui-组件)
- [Phase 4: 停止时自动保存](#phase-4-停止时自动保存)
- [Phase 5: 抓取选区与暂停](#phase-5-抓取选区与暂停)
- [Phase 6: 数据导出 (P2)](#phase-6-数据导出-p2)
- [Phase 7: 测试与优化](#phase-7-测试与优化)
- [任务依赖图](#任务依赖图)

**Feature Branch**: `005-auto-jank-capture`  
**Created**: 2026-04-02  
**Plan Reference**: `plan.md`  
**Est. Total Tasks**: 31

---

## 任务总览

```
Phase 1: 核心服务层      [T01-T05]  ████░░░░░░░░░░░░░░░░░░░░  5 tasks
Phase 2: 后台 Worker     [T06-T08]  ██████░░░░░░░░░░░░░░░░░░  3 tasks
Phase 3: GUI 组件        [T09-T17]  ████████████░░░░░░░░░░░░  9 tasks
Phase 4: 停止时自动保存  [T18-T19]  ██████████████░░░░░░░░░░  2 tasks
Phase 5: 抓取选区与暂停  [T25-T28]  ██████████████████░░░░░░  4 tasks
Phase 6: 数据导出 (P2)   [T29-T30]  ████████████████████░░░░  2 tasks (可延后)
Phase 7: 测试与优化      [T20-T24]  ████████████████████████  6 tasks
```

---

## Phase 1: 核心服务层

### T01: 新增 Jank 相关 Pydantic 模型

**文件**: `src/models.py`

**任务**:
- [ ] 添加 `MonitorState` 枚举（IDLE, MONITORING, TRIGGERED, STABILIZING, SAVING, PAUSED, COMPLETED, ERROR）
- [ ] 添加 `FrameData` 模型（timestamp_ns, frame_duration_ms, is_jank, is_big_jank）
- [ ] 添加 `FrameStats` 模型（timestamp, fps, jank_count, big_jank_count, frames）
- [ ] 添加 `JankEvent` 模型（timestamp, jank_count, avg_frame_time_ms, max_frame_time_ms）
- [ ] 添加 `JankConfig` 模型（enabled, target_package, jank_threshold, max_captures, stabilize_delay_sec, max_stabilize_sec）
- [ ] 添加 `AppInfo` 模型（package_name, app_name, is_foreground）
- [ ] 添加 `MonitorStats` 模型（avg_fps, total_jank_count, total_big_jank_count, capture_count, monitor_duration_sec）

**验收**: 模型类可实例化，字段类型正确

---

### T02: 扩展 CaptureConfig 模型

**文件**: `src/models.py`

**任务**:
- [ ] 在 `CaptureConfig` 中添加 `jank: JankConfig` 字段
- [ ] 设置默认值：enabled=False, jank_threshold=3, max_captures=3
- [ ] 确保配置序列化/反序列化兼容

**依赖**: T01

**验收**: 配置加载保存后 jank 配置字段不丢失

---

### T03: 新建帧数据解析器

**文件**: `src/jank_parser.py`（新建）

**任务**:
- [ ] 创建 `FrameStatsParser` 类
- [ ] 实现 `parse_framestats(output: str) -> List[FrameData]`：解析 `dumpsys gfxinfo framestats` 输出
- [ ] 实现 `calculate_fps(frames: List[FrameData], window_ms: int) -> float`：计算最近 N 毫秒的 FPS
- [ ] 实现 `detect_janks(frames: List[FrameData]) -> Tuple[int, int]`：返回 (jank_count, big_jank_count)
- [ ] Jank 判定：帧耗时 > 33.3ms
- [ ] BigJank 判定：帧耗时 > 125ms

**依赖**: T01

**验收**: 解析真实设备输出的 framestats 数据，计算结果准确

---

### T04: 新建 Jank 监控服务

**文件**: `src/jank_service.py`（新建）

**任务**:
- [ ] 创建 `JankMonitorService` 类
- [ ] 实现 `get_running_apps() -> List[AppInfo]`：获取设备上正在运行的第三方应用
- [ ] 实现 `get_display_refresh_rate() -> int`：从 `dumpsys display` 解析屏幕刷新率
- [ ] 实现 `is_app_foreground(package: str) -> bool`：检测指定应用是否在前台
- [ ] 实现 `get_default_jank_threshold(refresh_rate: int) -> int`：计算默认丢帧阈值（刷新率 × 5%）

**依赖**: T01

**验收**: 在真实设备上测试各方法返回正确结果

---

### T05: 实现刷新率检测和阈值计算

**文件**: `src/jank_service.py`

**任务**:
- [ ] 实现 `_parse_refresh_rate(output: str) -> int`：解析 dumpsys display 输出
- [ ] 支持多种设备格式（三星、小米、OPPO 等）
- [ ] 降级策略：解析失败返回 60Hz
- [ ] 阈值计算公式：`ceil(refresh_rate * 0.05)`
  - 60 Hz → 3 帧/秒
  - 90 Hz → 5 帧/秒
  - 120 Hz → 6 帧/秒
  - 144 Hz → 7 帧/秒

**依赖**: T04

**验收**: 在不同品牌设备上测试刷新率检测

---

## Phase 2: 后台 Worker

### T06: 新建 Jank 监控 Worker

**文件**: `src/jank_worker.py`（新建）

**任务**:
- [ ] 创建 `JankMonitorWorker(QThread)` 类
- [ ] 定义信号：
  - `frame_stats_ready(FrameStats)`
  - `jank_triggered(JankEvent)`
  - `app_state_changed(bool, str)`（is_foreground, message）
  - `monitor_error(str)`
- [ ] 实现 `start_monitor(package: str, threshold: int)`
- [ ] 实现 `stop_monitor()`
- [ ] 实现 200ms 轮询循环

**依赖**: T03, T04

**验收**: Worker 启动后持续发射 frame_stats_ready 信号

---

### T07: 实现前台应用检测

**文件**: `src/jank_worker.py`

**任务**:
- [ ] 在轮询循环中检测前台应用状态
- [ ] 应用切到后台：发射 `app_state_changed(False, "应用后台")`
- [ ] 应用恢复前台：发射 `app_state_changed(True, "应用恢复")`
- [ ] 应用进程退出：发射 `app_state_changed(False, "应用已退出")` 并设置 `should_stop=True`

**依赖**: T06

**验收**: 切换应用后信号正确发射

---

### T08: 实现触发状态机

**文件**: `src/jank_worker.py`

**任务**:
- [ ] 实现 `TriggerStateMachine` 类
- [ ] 状态：IDLE → TRIGGERED → STABILIZING → (回到 IDLE 或 保存)
- [ ] TRIGGERED: 检测到 jank_count > threshold
- [ ] STABILIZING: 等待 2 秒稳定期
- [ ] 持续卡顿：延后（每次 2 秒，最多累计 8 秒）
- [ ] 稳定后：发射 `jank_triggered` 信号

**依赖**: T06

**验收**: 模拟 Jank 触发，状态机正确转换

---

## Phase 3: GUI 组件

### T09: 新建 Jank 配置面板

**文件**: `src/jank_panel.py`（新建）

**任务**:
- [ ] 创建 `JankConfigPanel(QWidget)` 类
- [ ] 添加标题栏「🎮 Jank 监控配置」
- [ ] 添加应用选择器 `QComboBox`（可搜索）
- [ ] 添加刷新按钮
- [ ] 添加丢帧阈值 `QSpinBox`（范围 1-30，默认 3）
- [ ] 添加最大抓取次数 `QSpinBox`（范围 1-10，默认 3）
- [ ] 添加当前刷新率显示 `QLabel`

**依赖**: T01

**验收**: 面板组件可独立渲染，样式与主界面一致

---

### T10: 实现应用选择器

**文件**: `src/jank_panel.py`

**任务**:
- [ ] 实现 `AppSelector(QComboBox)` 类
- [ ] 格式：`应用名 (包名)` 或仅 `包名`（无应用名时）
- [ ] 实现 `refresh_apps(apps: List[AppInfo])` 方法
- [ ] 实现 `get_selected_package() -> str | None` 方法
- [ ] 空列表显示：`(无运行中的应用)`

**依赖**: T09

**验收**: 下拉框显示正确的应用列表

---

### T11: 新建 FPS 图表组件

**文件**: `src/fps_chart.py`（新建）

**任务**:
- [ ] 创建 `FpsChartWidget(PlotWidget)` 类
- [ ] 设置白色背景
- [ ] 设置 X 轴标签 "Time (s)"，Y 轴标签 "FPS"
- [ ] 设置默认 X 范围 [-60, 0]，Y 范围 [0, 120]
- [ ] 添加 FPS 曲线（蓝色，宽度 2px）
- [ ] 添加 Jank 散点（黄色 #FABF42，大小 8px）
- [ ] 添加 BigJank 散点（红色 #F85149，大小 10px）

**依赖**: 无（独立组件）

**验收**: 图表可独立渲染，样式正确

---

### T12: 实现图表数据更新

**文件**: `src/fps_chart.py`

**任务**:
- [ ] 实现 `FpsChartData` 类：管理 numpy 数组
- [ ] 实现 `add_frame_stats(stats: FrameStats)` 方法
- [ ] 实现滚动窗口逻辑（默认 60 秒）
- [ ] 实现 `clear()` 方法
- [ ] 实现图表实时更新

**依赖**: T11

**验收**: 持续调用 add_frame_stats 后图表平滑滚动

---

### T13: 实现图表横轴缩放

**文件**: `src/fps_chart.py`

**任务**:
- [ ] 启用 pyqtgraph 内置的鼠标滚轮缩放
- [ ] 限制缩放范围：10 秒 ~ 120 秒
- [ ] 缩放后保持实时滚动
- [ ] 时间刻度粒度：1 秒

**依赖**: T12

**验收**: 滚轮缩放后图表范围正确，刻度自动调整

---

### T14: 新建统计显示组件

**文件**: `src/jank_stats.py`（新建）

**任务**:
- [ ] 创建 `MonitorStatsWidget(QWidget)` 类
- [ ] 水平布局：`📈 平均 FPS: XX.X  │  🟡 Jank: X  │  🔴 BigJank: X`
- [ ] 实现 `update_stats(stats: MonitorStats)` 方法
- [ ] 设置字体和颜色

**依赖**: T01

**验收**: 统计显示样式正确

---

### T15: 集成 Jank 复选框到 GUI Tab

**文件**: `src/gui_tab.py`

**任务**:
- [ ] 在「启用 Ftrace 自定义」同行添加「启用 Jank 检测」复选框
- [ ] 复选框状态变化时显示/隐藏 Jank 配置面板
- [ ] 面板位置：Atrace Categories 下方（如同时勾选 Ftrace，在 Ftrace 下方）

**依赖**: T09

**验收**: 勾选复选框后面板正确显示

---

### T16: 集成 FPS 图表和统计组件

**文件**: `src/gui_tab.py`

**任务**:
- [ ] 监控开始后显示 `FpsChartWidget` 和 `MonitorStatsWidget`
- [ ] 连接 Worker 的 `frame_stats_ready` 信号到图表更新
- [ ] 连接 Worker 的 `app_state_changed` 信号到状态处理
- [ ] 监控停止后隐藏图表区域

**依赖**: T11, T12, T14

**验收**: 监控期间图表实时更新

---

### T17: 实现配置锁定逻辑

**文件**: `src/gui_tab.py`

**任务**:
- [ ] 监控开始时锁定：Duration、Buffer、Atrace、Ftrace、目标应用
- [ ] 监控开始时允许修改：丢帧阈值、最大抓取次数
- [ ] 状态栏显示「🔒 监控中」
- [ ] 监控停止后解锁所有配置

**依赖**: T15

**验收**: 监控期间锁定的配置项变为禁用状态

---

## Phase 4: 停止时自动保存

### T18: 实现停止时自动保存

**文件**: `src/service.py`

**任务**:
- [ ] 新增 `stop_with_auto_save() -> int`：检查并保存未保存的 trace
- [ ] 返回自动保存的 trace 数量
- [ ] 日志输出：「已自动保存并导出 N 段 trace」

**依赖**: 无（独立于 Jank 功能）

**验收**: 开始抓取后直接点击停止，trace 被自动保存

---

### T19: 集成自动保存到 GUI

**文件**: `src/gui_tab.py`

**任务**:
- [ ] 修改停止按钮点击事件
- [ ] 调用 `service.stop_with_auto_save()`
- [ ] 根据返回值更新日志显示
- [ ] 更新状态栏为「🟢 就绪」

**依赖**: T18

**验收**: 停止后日志显示自动保存信息

---

## Phase 5: 抓取选区与暂停

### T25: 新增 CaptureRegion 模型

**文件**: `src/models.py`

**任务**:
- [ ] 添加 `CaptureRegion` 模型（start_time, end_time, is_capture, label）
- [ ] 添加 `FrameExportRow` 模型（兼容 PerfDog Data_v4 格式）

**依赖**: T01

**验收**: 模型可实例化

---

### T26: 实现抓取判定暂停/恢复

**文件**: `src/jank_worker.py`

**任务**:
- [ ] 添加 `_capture_regions: list[CaptureRegion]` 状态
- [ ] 添加 `pause_capture_detection()` 方法：创建新的非抓取选区
- [ ] 添加 `resume_capture_detection()` 方法：结束非抓取选区，开始新抓取选区
- [ ] 应用切到后台时自动调用 `pause_capture_detection()`
- [ ] 应用恢复前台 5 秒后自动调用 `resume_capture_detection()`

**依赖**: T06

**验收**: 暂停/恢复后选区列表正确更新

---

### T27: 实现选区底部彩色条

**文件**: `src/fps_chart.py`

**任务**:
- [ ] 在图表底部添加选区可视化区域（高度约 10px）
- [ ] 抓取选区：绿色 (#4CAF50)
- [ ] 非抓取选区：灰色 (#9E9E9E)
- [ ] 实现 `update_regions(regions: list[CaptureRegion])` 方法

**依赖**: T11, T25

**验收**: 切换暂停/恢复时底部彩色条正确更新

---

### T28: 集成暂停按钮到图表区域

**文件**: `src/gui_tab.py`

**任务**:
- [ ] 在图表区域上方或侧边添加「⏸ 暂停判定」按钮
- [ ] 暂停时按钮变为「▶ 恢复判定」
- [ ] 连接按钮到 Worker 的暂停/恢复方法
- [ ] 显示暂停状态提示

**依赖**: T16, T26

**验收**: 点击按钮后图表底部彩色条和按钮状态正确更新

---

## Phase 6: 数据导出 (P2)

### T29: 新建帧数据导出器

**文件**: `src/frame_exporter.py`（新建）

**任务**:
- [ ] 创建 `FrameExporter` 类
- [ ] 实现 `export_to_xlsx(data: list[FrameExportRow], regions: list[CaptureRegion], path: Path)`
- [ ] 生成兼容 PerfDog Data_v4 格式的 xlsx 文件
- [ ] 非抓取选区数据行 label 为空，抓取选区使用 "capture1", "capture2" 等

**依赖**: T25

**验收**: 导出的 xlsx 可用 PerfDog 工具解析

---

### T30: 集成导出按钮到 GUI

**文件**: `src/gui_tab.py`

**任务**:
- [ ] 在底部按钮行添加「📤 导出」按钮
- [ ] 监控停止后启用导出按钮
- [ ] 点击后弹出保存对话框
- [ ] 调用 `FrameExporter.export_to_xlsx()` 生成文件

**依赖**: T29

**验收**: 点击导出后生成 xlsx 文件

---

## Phase 7: 测试与优化

### T20: 帧数据解析器测试

**文件**: `tests/test_jank_parser.py`（新建）

**任务**:
- [ ] 测试 `parse_framestats()` 解析多种格式
- [ ] 测试 `calculate_fps()` 计算准确性
- [ ] 测试 `detect_janks()` Jank/BigJank 判定

**依赖**: T03

---

### T21: 监控服务测试

**文件**: `tests/test_jank_service.py`（新建）

**任务**:
- [ ] 测试 `get_display_refresh_rate()` 多种设备输出
- [ ] 测试 `get_default_jank_threshold()` 阈值计算
- [ ] 测试 `is_app_foreground()` 前台检测

**依赖**: T04, T05

---

### T22: 触发状态机测试

**文件**: `tests/test_jank_worker.py`（新建）

**任务**:
- [ ] 测试状态转换：IDLE → TRIGGERED → STABILIZING
- [ ] 测试延后逻辑（最多 8 秒）
- [ ] 测试稳定后触发保存

**依赖**: T08

---

### T23: 性能验证

**文件**: `tests/test_jank_performance.py`（新建）

**任务**:
- [ ] 测量 200ms 轮询的 CPU 开销
- [ ] 验证开销 < 5%（NFR-001）
- [ ] 测量帧率更新延迟
- [ ] 验证延迟 < 500ms（NFR-002）
- [ ] 测量 Jank 触发到 trace 保存完成的延迟
- [ ] 验证延迟 < 3 秒（NFR-003，不含稳定期）

**依赖**: T06

---

### T31: 选区与导出测试

**文件**: `tests/test_capture_region.py`（新建）

**任务**:
- [ ] 测试 CaptureRegion 模型
- [ ] 测试暂停/恢复选区切换
- [ ] 测试后台恢复 5 秒延迟
- [ ] 测试导出 xlsx 格式正确性

**依赖**: T25, T26, T29

---

### T24: 添加 pyqtgraph 依赖

**文件**: `pyproject.toml`

**任务**:
- [ ] 在 dependencies 中添加 `pyqtgraph >= 0.13.0`
- [ ] 运行 `pip install -e .` 验证安装
- [ ] 更新 `requirements.txt`（如有）

**依赖**: 无

**验收**: `import pyqtgraph` 成功

---

## 任务依赖图

```
T01 ─┬─▶ T02
     │
     ├─▶ T03 ─┬─▶ T06 ─┬─▶ T07
     │        │        │
     │        │        └─▶ T08
     │        │
     ├─▶ T04 ─┴─▶ T05
     │
     └─▶ T25 ─▶ T26 ─▶ T28
              │
              └─▶ T27 ─▶ T29 ─▶ T30

T09 ─┬─▶ T10
     │
     └─▶ T15 ─▶ T17

T11 ─▶ T12 ─▶ T13
  │
  └─▶ T27

T14

T15 ◀────────────────────────────┐
  │                              │
  └─▶ T16 ◀── T11, T12, T14      │
                                 │
T06, T07, T08 ──────────────────▶│

T18 ─▶ T19

T03 ─▶ T20
T04, T05 ─▶ T21
T08 ─▶ T22
T06 ─▶ T23
T25, T26, T29 ─▶ T31
T24 (独立)
```

---

## 执行顺序建议

**P1 任务（必须实现）**：

1. **先执行**: T24（添加依赖）、T01（模型定义）
2. **并行开发**:
   - 服务层：T02 → T03 → T04 → T05
   - GUI 组件：T09 → T10、T11 → T12 → T13、T14
3. **集成**: T06 → T07 → T08 → T15 → T16 → T17
4. **功能完善**: T18 → T19
5. **选区功能**: T25 → T26 → T27 → T28
6. **测试**: T20 → T21 → T22 → T23

**P2 任务（可延后）**：

7. **数据导出**: T29 → T30 → T31
