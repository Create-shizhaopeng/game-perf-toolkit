# Tasks: FPS 帧率曲线图表增强

**Input**: Design documents from `modules/perfetto_capture/specs/007-fps-chart-enhancement/`
**Prerequisites**: plan.md (required), spec.md (required)

## 目录

- [Format](#format)
- [Phase 1: Foundational](#phase-1-foundational)
- [Phase 2: User Story 1 - 长时间监控数据完整保留 (P1)](#phase-2-user-story-1---长时间监控数据完整保留-p1--mvp)
- [Phase 3: User Story 2 - 交互式缩放与拖动 (P1)](#phase-3-user-story-2---交互式缩放与拖动-p1)
- [Phase 4: User Story 3 - 鼠标悬停帧信息展示 (P2)](#phase-4-user-story-3---鼠标悬停帧信息展示-p2)
- [Phase 5: 监控时长保护](#phase-5-监控时长保护-p1)
- [Phase 6: Polish](#phase-6-polish--cross-cutting-concerns)
- [Dependencies & Execution Order](#dependencies--execution-order)
- [Implementation Strategy](#implementation-strategy)

## Format

`[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 所属用户故事（US1, US2, US3）
- 所有文件路径相对于 `modules/perfetto_capture/`

---

## Phase 1: Foundational

**Purpose**: 无本阶段独立任务。本特性无需新增依赖或基础设施，直接在现有 `fps_chart.py` 上重构。

---

## Phase 2: User Story 1 - 长时间监控数据完整保留 (P1) 🎯 MVP

**Goal**: 替换固定环形缓冲区为分块增长 numpy 数组，保留全部历史数据

**Independent Test**: 模拟 36000 个数据点写入，验证首尾数据均可访问

### Implementation

- [x] T001 [US1] 重构 `FpsChartData.__init__` 为分块增长模式：初始容量 1800，使用 `np.empty` 预分配，新增 `_capacity` 和 `_size` 字段，移除 `_max_points` 和 `_current_idx` in `src/fps_chart.py`
- [x] T002 [US1] 重构 `FpsChartData.add_stats`：使用 `_size` 索引写入，满时调用 `_grow()` 扩容 in `src/fps_chart.py`
- [x] T003 [US1] 新增 `FpsChartData._grow` 方法：2 倍扩容逻辑，分配新数组并复制旧数据 in `src/fps_chart.py`
- [x] T004 [US1] 更新 `FpsChartData.get_curve_data`：返回 `_timestamps[:_size]` 视图（不 copy）in `src/fps_chart.py`
- [x] T005 [US1] 更新 `elapsed_seconds`、`latest_fps` 属性：使用 `_size` 替代 `_current_idx` in `src/fps_chart.py`
- [x] T006 [US1] 更新 `FpsChartData.clear`：重置 `_size = 0`，重新分配初始容量数组 in `src/fps_chart.py`
- [x] T007 [US1] 为 `FpsChartWidget._fps_curve` 启用 `clipToView=True` 和 `downsample`（peak 模式）in `src/fps_chart.py`

### Tests

- [x] T008 [P] [US1] 新增 `test_chart_data_no_data_loss` 测试：写入 36000 点后验证首尾数据完整 in `tests/test_fps_chart.py`
- [x] T009 [P] [US1] 新增 `test_chart_data_grow` 测试：验证扩容时数据不丢失，容量正确翻倍 in `tests/test_fps_chart.py`
- [x] T010 [P] [US1] 新增 `test_chart_data_clear` 测试：验证 clear 后重新写入数据正常 in `tests/test_fps_chart.py`
- [x] T011 [P] [US1] 新增 `test_chart_data_jank_markers_preserved` 测试：长时间运行后 Jank/BigJank 标记全部保留 in `tests/test_fps_chart.py`

**Checkpoint**: 此时 FPS 曲线可无上限存储全部数据，长时间监控无数据丢失

---

## Phase 3: User Story 2 - 交互式缩放与拖动 (P1)

**Goal**: 启用 X 轴缩放拖动、底部滚动条、跟随/浏览模式切换

**Independent Test**: 运行 10 分钟监控后，鼠标滚轮缩放到局部区间，验证曲线清晰可见

### Implementation

- [x] T012 [US2] 更新 ViewBox 配置：`setMouseEnabled(x=True, y=False)`，启用 X 轴交互 in `src/fps_chart.py`
- [x] T013 [US2] 新增 `_following` 状态字段和跟随模式判定逻辑：连接 `sigRangeChangedManually` 信号，检测视图是否覆盖全量数据 in `src/fps_chart.py`
- [x] T014 [US2] 重构 `_update_chart`：区分 FOLLOWING 和 BROWSING 模式的视图更新逻辑 in `src/fps_chart.py`
  - FOLLOWING：`setXRange(0, latest + 5)` 全量显示
  - BROWSING：仅更新 `xMax` 上限，不移动视图
- [x] T015 [US2] 新增 Y 轴自适应逻辑：在视图范围变化时，根据可见 X 范围内的数据动态调整 Y 轴范围 in `src/fps_chart.py`
- [x] T016 [US2] 新增底部 `QScrollBar(Horizontal)` 并双向绑定 ViewBox：
  - ViewBox `sigRangeChanged` → 更新 scrollbar range/value/pageStep
  - ScrollBar `valueChanged` → 调用 `setXRange` 平移视图
  - 新增 `_syncing_scrollbar` 防信号循环 in `src/fps_chart.py`
- [x] T017 [US2] 动态更新 ViewBox X 轴上限：每次新数据到达时 `setLimits(xMax=latest + 2)` in `src/fps_chart.py`
- [x] T018 [US2] 实现滚轮缩放回全量自动恢复跟随：在 `sigRangeChanged` 回调中检测当前视图是否覆盖全量数据范围（容差 ±2 秒），若是则设 `_following = True` in `src/fps_chart.py`

### Tests

- [x] T019 [P] [US2] 新增 `test_following_mode_default` 测试：初始状态为跟随模式 in `tests/test_fps_chart.py`
- [x] T020 [P] [US2] 新增 `test_browsing_mode_no_auto_scroll` 测试：浏览模式下新数据不移动视图 in `tests/test_fps_chart.py`

**Checkpoint**: 此时图表支持缩放拖动，有滚动条，跟随/浏览模式正常切换

---

## Phase 4: User Story 3 - 鼠标悬停帧信息展示 (P2)

**Goal**: 鼠标悬停显示十字线和帧信息浮窗

**Independent Test**: 鼠标移到曲线上，验证 tooltip 显示正确的时间和帧率

### Implementation

- [x] T021 [US3] 新增十字线组件：在 `_setup_ui` 中创建两条 `InfiniteLine`（垂直+水平），默认隐藏 in `src/fps_chart.py`
- [x] T022 [US3] 新增信息浮窗 `TextItem`：配置字体、背景色、定位策略 in `src/fps_chart.py`
- [x] T023 [US3] 新增 `_find_nearest_point` 方法：使用 `np.searchsorted` 二分查找最近数据点 in `src/fps_chart.py`
- [x] T024 [US3] 连接 `scene().sigMouseMoved` 信号：转换坐标后更新十字线位置和信息浮窗内容（时间 HH:MM:SS + FPS + Jank 类型）in `src/fps_chart.py`
- [x] T025 [US3] 实现鼠标离开隐藏：重写 `leaveEvent` 或监听 hover 状态，离开时隐藏十字线和信息框 in `src/fps_chart.py`
- [x] T026 [US3] Jank/BigJank 标记检测：在 `_find_nearest_point` 结果中检查该时间点是否在 jank_points 或 big_jank_points 中，信息框追加类型标注 in `src/fps_chart.py`

### Tests

- [x] T027 [P] [US3] 新增 `test_find_nearest_point` 测试：验证二分查找精度 in `tests/test_fps_chart.py`
- [x] T028 [P] [US3] 新增 `test_hover_time_format` 测试：验证时间格式为 HH:MM:SS in `tests/test_fps_chart.py`

**Checkpoint**: 鼠标悬停显示完整帧信息，含 Jank 类型标注

---

## Phase 5: 监控时长保护 (P1)

**Goal**: 可配置最大监控时长，到期自动停止

**Independent Test**: 设置最大时长 1 分钟，验证到期后自动停止

### Implementation

- [x] T029 [US1] 在 `JankConfig` 模型中新增 `max_duration_hours` 字段（默认 3，范围 1-12）in `src/models.py`
- [x] T030 [US1] 在 JankConfigPanel 配置区新增"监控时长" QSpinBox（1-12 小时，默认 3）in `src/jank_panel.py`
- [x] T031 [US1] 在 `gui_tab.py` 中添加监控计时器，到达时长后调用 `_on_stop()` 并记录日志 in `src/gui_tab.py`

### Tests

- [x] T032 [P] [US1] 新增 `test_max_duration_config` 测试：验证配置字段范围约束 in `tests/test_fps_chart.py`

**Checkpoint**: 监控到期自动停止，防止无限运行

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 性能验证和边缘场景处理

- [x] T033 性能验证：创建基准测试，100K 数据点下验证 `add_stats` + `_update_chart` 总耗时 < 50ms in `tests/test_fps_chart.py`
- [x] T034 边缘场景处理：验证 0 数据点时缩放/拖动不崩溃，极小/极大缩放范围正常 in `tests/test_fps_chart.py`
- [x] T035 更新现有 `test_capture_region.py` 中的 `MockFpsChartData` 适配新接口 in `tests/test_capture_region.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Foundational)**: 无任务，跳过
- **Phase 2 (US1 数据存储)**: 无前置依赖，立即开始
- **Phase 3 (US2 缩放拖动)**: 依赖 Phase 2 完成（需要新的数据接口）
- **Phase 4 (US3 悬停信息)**: 依赖 Phase 2 完成，可与 Phase 3 并行
- **Phase 5 (监控时长)**: 依赖 Phase 2 完成，可与 Phase 3/4 并行
- **Phase 6 (Polish)**: 依赖 Phase 2-5 完成

### User Story Dependencies

- **US1 (数据存储)**: 独立，无其他 US 依赖
- **US2 (缩放拖动)**: 依赖 US1 的 `get_curve_data` 和 `_size` 接口
- **US3 (悬停信息)**: 依赖 US1 的数据存储接口，与 US2 无直接依赖

### Parallel Opportunities

- T008-T011 可并行执行（独立测试用例）
- T019-T020 可并行执行
- T027-T028 可并行执行
- Phase 3 和 Phase 4 的实现部分可并行（前提是 Phase 2 完成）

---

## Implementation Strategy

### MVP First (US1 Only)

1. 完成 T001-T007：重构 FpsChartData 数据存储
2. 完成 T008-T011：验证数据完整性
3. **STOP and VALIDATE**: 启动应用，运行 10+ 分钟确认数据不丢失
4. 提交 MVP

### Incremental Delivery

1. US1 → 数据完整（MVP）
2. US2 → 缩放拖动 + 滚动条 + 跟随模式
3. US3 → 悬停信息展示
4. Polish → 性能验证 + 边缘场景

---

## Notes

- 主要变更集中在 `src/fps_chart.py`，另涉及 `models.py`、`jank_panel.py`、`gui_tab.py`
- T001-T006 是连续修改同一个类，建议作为一个连续任务组执行
- 测试文件 `tests/test_fps_chart.py` 为新增文件
- 不涉及 `service.py` 或 `jank_worker.py` 的变更
