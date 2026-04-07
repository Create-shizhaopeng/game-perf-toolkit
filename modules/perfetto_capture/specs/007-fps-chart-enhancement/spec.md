# Feature Specification: FPS 帧率曲线图表增强

**Feature Branch**: `007-fps-chart-enhancement`
**Created**: 2026-04-03
**Status**: Draft
**Input**: 修复帧率曲线长时间监控后前端数据丢失，同时增强图表交互能力（缩放、拖动、悬停信息）

## 目录

- [Clarifications](#clarifications)
- [背景与问题](#背景与问题)
- [User Scenarios & Testing](#user-scenarios--testing)
  - [User Story 1 - 长时间监控数据完整保留](#user-story-1---长时间监控数据完整保留-priority-p1)
  - [User Story 2 - 交互式缩放与拖动](#user-story-2---交互式缩放与拖动-priority-p1)
  - [User Story 3 - 鼠标悬停帧信息展示](#user-story-3---鼠标悬停帧信息展示-priority-p2)
  - [Edge Cases](#edge-cases)
- [Requirements](#requirements)
  - [Functional Requirements](#functional-requirements)
  - [Key Entities](#key-entities)
- [Assumptions](#assumptions)
- [Success Criteria](#success-criteria)

## Clarifications

### Session 2026-04-03

- Q: 用户手动拖到历史区域后，如何恢复跟随模式？ → A: 滚轮缩放回全量视图时自动恢复跟随，不需要额外按钮
- Q: 缩放 X 轴查看局部时，Y 轴如何表现？ → A: Y 轴根据当前可见 X 范围内的数据自适应
- Q: 底部滚动条的样式？ → A: 标准水平滚动条，滑块大小反映缩放比例
- Q: 长时间监控会不会 OOM？ → A: 实际内存开销很小（12h 约 5.5MB），但需加保护机制：可配置最大监控时长（默认 3 小时，上限 12 小时），到期自动停止所有监控和 Perfetto 抓取

## 背景与问题

当前 FPS 图表使用固定 1500 点的环形缓冲区（`max_seconds=300`），采样率约 5 次/秒。超过 5 分钟后旧数据被移出数组，但 X 轴始终从 0 显示，导致：

1. 前端出现无数据空白区域，曲线"断头"
2. 早期帧率数据、Jank 标记和 BigJank 标记永久丢失
3. 用户无法回溯分析监控初期的帧率表现

同时，当前图表禁用了所有鼠标交互（`setMouseEnabled(x=False, y=False)`），用户在长时间监控时无法缩放查看局部细节。

## User Scenarios & Testing

### User Story 1 - 长时间监控数据完整保留 (Priority: P1)

用户启动 Jank 监控后持续运行 1-2 小时（极端场景 8 小时），期间所有帧率数据点、Jank 标记、BigJank 标记必须完整保留。曲线从时间 0 开始始终可见，不会因时间推移而"截断"前端数据。

**Why this priority**: 数据完整性是图表最基本的功能，数据丢失直接导致分析结论不可靠。

**Independent Test**: 模拟连续写入 36000 个数据点（对应 2 小时），验证首尾数据均可访问。

**Acceptance Scenarios**:

1. **Given** 监控已运行 10 分钟（3000 个数据点），**When** 查看图表，**Then** X 轴从 0 开始到当前时间，所有数据点均可见
2. **Given** 监控已运行 2 小时（36000 个数据点），**When** 查看图表，**Then** 首个数据点（t=0）和最新数据点均存在于数据集中
3. **Given** 监控已运行 1 小时且期间产生了 Jank/BigJank 标记，**When** 查看图表，**Then** 所有 Jank 和 BigJank 标记均完整保留

---

### User Story 2 - 交互式缩放与拖动 (Priority: P1)

用户在监控过程中或停止后，可以通过鼠标滚轮缩放图表查看局部帧率细节，也可以左右拖动查看不同时间段的数据。图表底部提供滚动条辅助导航，有明确的边界限制防止拖出数据范围。

**Why this priority**: 长时间监控产生大量数据后，全局视图压缩导致单帧级别抖动不可见，缩放是分析的核心交互。

**Independent Test**: 运行 10 分钟监控后，用鼠标滚轮缩放到某一时间段，验证局部曲线清晰可见。

**Acceptance Scenarios**:

1. **Given** 监控中或停止后，**When** 用户在图表区域滚动鼠标滚轮，**Then** 图表以鼠标位置为中心进行 X 轴缩放，Y 轴不受滚轮影响
2. **Given** 图表已缩放到局部视图，**When** 用户左右拖动图表，**Then** 视图平移，左边界不低于 0，右边界不超过当前最新数据时间
3. **Given** 图表已缩放到局部视图，**When** 用户操作底部滚动条，**Then** 视图跟随滚动条位置平移到对应时间区间
4. **Given** 图表处于缩放状态且监控正在进行中，**When** 新数据到来，**Then** 如果用户正在查看最右侧（跟随模式），视图自动跟随最新数据滚动；如果用户已手动拖到历史区域，视图保持不动不被新数据打断
5. **Given** 图表处于缩放状态，**When** 用户通过滚轮缩放回全量范围，**Then** 图表恢复到显示全部数据并自动恢复跟随模式

---

### User Story 3 - 鼠标悬停帧信息展示 (Priority: P2)

用户将鼠标悬停在图表曲线上时，显示该位置对应的时间戳（24 小时制）和精确帧率数值，便于精确定位问题帧。

**Why this priority**: 提升分析效率，但不影响核心功能。

**Independent Test**: 鼠标移到曲线上某个位置，验证 tooltip 显示正确的时间和帧率值。

**Acceptance Scenarios**:

1. **Given** 图表中有帧率曲线数据，**When** 鼠标悬停在曲线附近，**Then** 显示一个十字线（crosshair）标识当前位置，并在附近显示信息框包含：时间（HH:MM:SS 格式）和帧率值（如 "14:32:05  FPS: 58"）
2. **Given** 鼠标悬停在 Jank 标记附近，**When** 数据点为 Jank 或 BigJank 帧，**Then** 信息框额外标注 "Jank" 或 "BigJank"
3. **Given** 鼠标移出图表区域，**When** 光标离开，**Then** 十字线和信息框自动隐藏

---

### Edge Cases

- 监控启动后 0 个数据点时缩放/拖动操作不应崩溃
- 数据点数量达到 216,000（12 小时上限）时图表渲染和交互仍保持流畅
- 缩放到极小范围（如 1 秒内）时数据点间距清晰可见
- 缩放到极大范围（显示全部 12 小时数据）时曲线仍可辨识
- 监控中用户缩放后新数据持续写入，视图不闪烁或跳动
- 窗口大小变化时滚动条和图表自适应
- 监控到达最大时长时正在进行 Perfetto 抓取，应先保存再停止
- 用户在自动停止前手动停止，不受时长限制影响

## Requirements

### Functional Requirements

- **FR-001**: 数据存储 MUST 采用分块增长 numpy 数组策略，初始容量预分配 1800 点（约 6 分钟），满时以 2 倍扩容
- **FR-002**: 数据存储 MUST 保留完整监控期间所有帧率、时间戳、Jank 标记数据，受限于最大监控时长
- **FR-016**: 系统 MUST 提供可配置的最大监控时长（默认 3 小时，范围 1-12 小时），在左侧配置面板中以 QSpinBox 形式提供
- **FR-017**: 监控到达设定时长后 MUST 自动停止 FPS 监控、Jank 检测和 Perfetto 抓取（如正在抓取则先保存 trace）
- **FR-018**: 自动停止时 MUST 在日志区显示提示信息
- **FR-003**: 渲染 MUST 启用 pyqtgraph 的 `clipToView` 和 `downsample`（peak 模式）以保证长时间数据的渲染性能
- **FR-004**: 图表 MUST 支持鼠标滚轮缩放，仅作用于 X 轴
- **FR-005**: 图表 MUST 支持鼠标左键拖动平移，仅作用于 X 轴
- **FR-006**: 图表 MUST 在底部显示水平滚动条，与视图范围双向同步
- **FR-007**: X 轴左边界 MUST NOT 小于 0，右边界 MUST NOT 大于当前最新数据时间点
- **FR-008**: 用户通过滚轮缩放回全量视图时 MUST 自动恢复跟随模式
- **FR-009**: 监控进行中时，跟随模式下新数据到达时视图 MUST 自动向右滚动，显示全量数据
- **FR-010**: 监控进行中时，用户手动缩放或拖动到局部区域时自动进入非跟随模式，新数据到达时视图 MUST NOT 自动移动
- **FR-011**: 用户缩放 X 轴到局部区间时，Y 轴 MUST 根据当前可见范围内的数据自适应调整，充分利用图表空间
- **FR-012**: 鼠标悬停时 MUST 显示十字线和信息浮窗，包含时间（HH:MM:SS）和帧率值
- **FR-013**: 鼠标悬停在 Jank/BigJank 标记附近时信息浮窗 MUST 标注类型
- **FR-014**: 鼠标移出图表区域时十字线和信息浮窗 MUST 隐藏
- **FR-015**: 100,000 个数据点时图表更新延迟 MUST NOT 超过 50ms

### Key Entities

- **FpsChartData**: 数据管理器，使用分块增长 numpy 数组存储时间戳和帧率值，以及 Jank/BigJank 标记点列表
- **ViewState**: 图表视图状态，包含当前可见范围（x_min, x_max）、缩放比例、是否处于跟随模式

## Assumptions

- 采样率约 5 次/秒（200ms 轮询间隔），长期不变
- 监控时长受用户配置限制（默认 3 小时，最长 12 小时），绝大多数场景不超过 3 小时（54,000 点）
- pyqtgraph 的 `clipToView` + peak 降采样在 10 万级数据量下性能足够
- 分块增长 numpy 数组（2 倍扩容）8 小时约占 2.3MB 内存，可接受
- 现有选区（CaptureRegion）机制不受本次改造影响，仍正常显示

## Success Criteria

### Measurable Outcomes

- **SC-001**: 用户连续监控 2 小时后，首个数据点（t=0）可在图表中通过缩放找到并查看
- **SC-002**: 10 万数据点下，每次图表更新（包含数据写入和渲染）耗时不超过 50ms
- **SC-003**: 用户可在 3 秒内通过缩放和拖动定位到任意时间段的帧率细节
- **SC-004**: 鼠标悬停时信息延迟不超过 100ms，位置精度误差不超过 1 个数据点
