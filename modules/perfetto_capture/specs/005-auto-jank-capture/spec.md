# Feature Specification: Jank 自动检测与抓取

**Feature Branch**: `005-auto-jank-capture`  
**Spec Location**: `modules/perfetto_capture/specs/005-auto-jank-capture/`  
**Created**: 2026-04-02  
**Status**: Draft  
**Input**: 支持游戏内 jank 自动检测、实时帧率监控和条件触发 trace 抓取

## 目录

- [背景与动机](#背景与动机)
- [User Scenarios & Testing](#user-scenarios--testing)
- [Requirements](#requirements)
- [Clarifications](#clarifications)
- [Success Criteria](#success-criteria)

## 背景与动机

当前 perfetto_capture 模块支持手动触发抓取，但对于游戏性能测试场景：
1. 测试人员无法预知卡顿何时发生，容易错过关键时刻
2. 需要长时间盯着屏幕等待问题复现
3. 抓取的 trace 可能不包含卡顿时刻

本需求旨在实现**自动卡顿检测**：
1. 实时监控游戏帧率
2. 当检测到卡顿（丢帧超阈值）时自动保存 trace
3. 提供实时帧率可视化（PerfDog 风格）

## User Scenarios & Testing

### User Story 1 — 启用 Jank 自动检测 (Priority: P0)

作为测试工程师，我希望在 Perfetto 抓取界面中启用 jank 自动检测，让系统自动抓取卡顿时刻的 trace。

**Independent Test**: 勾选「启用 Jank 自动检测」后，界面显示 jank 监控区域

**Acceptance Scenarios**:

1. **Given** 打开 Perfetto 抓取 Tab, **When** 勾选「启用 Jank 自动检测」, **Then** 在 Atrace Categories 下方显示 Jank 监控配置区域
2. **Given** 已勾选 Jank 检测, **When** 未选择目标应用, **Then** 开始按钮禁用并提示需选择应用
3. **Given** 已选择目标应用, **When** 点击开始, **Then** 同时启动 Perfetto 抓取和帧率监控

---

### User Story 2 — 选择监控目标应用 (Priority: P0)

作为测试工程师，我希望从运行中的应用列表中选择要监控的游戏。

**Independent Test**: 点击应用选择器，显示设备上正在运行的应用列表

**Acceptance Scenarios**:

1. **Given** 设备已连接, **When** 点击应用选择下拉框, **Then** 显示当前运行的应用列表（包名 + 应用名）
2. **Given** 应用列表已显示, **When** 选择一个应用, **Then** 显示该应用的当前帧率
3. **Given** 已选择应用, **When** 该应用退出或切到后台（通过 `dumpsys activity` 检测前台应用变化）, **Then** 显示警告并暂停监控

---

### User Story 3 — 实时帧率监控与可视化 (Priority: P1)

作为测试工程师，我希望看到实时帧率曲线图，了解游戏运行状态。

**Independent Test**: 启动监控后，实时帧率曲线持续更新

**Acceptance Scenarios**:

1. **Given** 监控已启动, **When** 游戏运行中, **Then** 显示实时 FPS 曲线（PerfDog 风格，最近 60 秒）
2. **Given** 实时曲线显示中, **When** 发生丢帧, **Then** 曲线上标记 Jank 点（黄色）和 BigJank 点（红色）
3. **Given** 监控中, **When** 查看统计区域, **Then** 显示平均 FPS、Jank 次数、BigJank 次数

---

### User Story 4 — Jank 触发自动抓取 (Priority: P0)

作为测试工程师，我希望系统在检测到卡顿时自动保存 trace。

**Why this priority**: 核心功能，实现自动化卡顿捕获

**Independent Test**: 人为制造卡顿（如快速切换场景），验证系统自动保存 trace

**Acceptance Scenarios**:

1. **Given** 监控中且 1 秒内丢帧数 > 阈值, **When** 触发 Jank, **Then** 等待 2 秒稳定后自动保存 trace
2. **Given** 触发后的 2 秒内持续卡顿, **When** 继续检测到丢帧, **Then** 延后保存时机（最多延后到 8 秒）
3. **Given** 已保存一个 trace, **When** 达到最大抓取次数, **Then** 停止监控并提示用户
4. **Given** 自动保存触发, **When** 保存完成, **Then** 日志显示「检测到 Jank，已自动保存 trace」

---

### User Story 5 — 暂停抓取判定 (Priority: P1)

作为测试工程师，我希望在场景切换时能手动暂停抓取判定，避免误触发 trace 保存。

**Independent Test**: 点击「暂停判定」按钮后，曲线标注非抓取选区，Jank 不触发保存

**Acceptance Scenarios**:

1. **Given** 监控中, **When** 点击「暂停判定」, **Then** 曲线底部标注非抓取选区，Jank 不触发保存
2. **Given** 暂停判定中, **When** 点击「恢复判定」, **Then** 曲线底部标注抓取选区，恢复正常触发逻辑
3. **Given** 暂停判定中, **When** 帧率统计, **Then** 统计数据继续累计但不纳入触发计算

---

### User Story 6 — 导出帧率数据 (Priority: P2, 可延后)

作为测试工程师，我希望导出帧率统计数据，以便与 PerfDog 数据进行对比分析。

**Independent Test**: 点击导出按钮，生成兼容 PerfDog 格式的 CSV 文件

**Acceptance Scenarios**:

1. **Given** 监控已进行一段时间, **When** 点击导出, **Then** 生成 CSV 文件，格式与 PerfDog 一致
2. **Given** 存在非抓取选区, **When** 导出数据, **Then** 非抓取选区数据行保留但标记为空

---

### User Story 7 — 停止时自动保存 trace (Priority: P1)

作为测试工程师，我希望点击「停止」时系统自动保存当前正在抓取的 trace，而不是提示"未保存 trace"让我困惑。

**Background**: 当前行为是点击「停止」后如果之前没有点击「保存」，会提示"未保存 trace"。用户经常不理解为什么需要先点「保存」再点「停止」。

**Independent Test**: 开始抓取后直接点击停止，验证 trace 被自动保存并导出

**Acceptance Scenarios**:

1. **Given** 正在抓取中, **When** 点击「停止」且之前未点击「保存」, **Then** 系统自动保存当前 trace 段后再停止并导出
2. **Given** 正在抓取中且已保存过几段, **When** 点击「停止」, **Then** 系统自动保存最后一段 + 已保存的段一起导出
3. **Given** 自动保存的 trace, **When** 导出完成, **Then** 日志显示「已自动保存并导出 N 段 trace」

---

### Edge Cases

- 应用切到后台：曲线显示 0 FPS，暂停抓取判定，标注非抓取选区
- 应用恢复前台：等待 5 秒后自动恢复抓取判定，标记抓取选区
- 应用进程被杀：结束监控，自动保存当前 trace 并导出
- 设备断开连接：保存当前 trace，提示用户
- 场景切换导致短暂卡顿：用户可点击暂停按钮暂停抓取判定，避免误触发
- 监控过程中用户手动保存：正常保存，不影响自动检测

## Requirements

### Functional Requirements

#### Jank 检测配置

- **FR-001**: 系统 MUST 在「启用 Ftrace 自定义」同行提供「启用 Jank 自动检测」复选框
- **FR-002**: 勾选后 MUST 在 Atrace Categories 区域下方显示 Jank 监控配置面板
- **FR-003**: 如果 Ftrace 自定义也勾选，Jank 监控面板 MUST 在 Ftrace 面板下方

#### 应用选择

- **FR-004**: 系统 MUST 提供应用选择器，列出设备上正在运行的应用
- **FR-005**: 应用列表 MUST 显示包名和应用名称
- **FR-006**: 系统 SHOULD 支持刷新应用列表
- **FR-006a**: 系统 MUST 通过 `dumpsys activity` 检测目标应用是否在前台
- **FR-006b**: 当目标应用切到后台时，曲线显示 0 FPS，暂停抓取判定（继续帧率统计）
- **FR-006c**: 当目标应用恢复前台时，等待 5 秒后自动恢复抓取判定
- **FR-006d**: 当目标应用进程被杀时，结束监控并自动保存 trace

#### 帧率监控

- **FR-007**: 系统 MUST 使用 `dumpsys gfxinfo <package> framestats` 获取帧数据
- **FR-008**: 采样间隔 SHOULD 为 200ms
- **FR-009**: 系统 MUST 计算并显示实时 FPS（基于最近 1 秒帧数）

#### 丢帧检测

- **FR-010**: 单帧丢帧（Jank）定义：帧耗时 > 33.3ms（约 2 帧周期）
  - 用于曲线标黄点、Jank 计数
- **FR-010a**: BigJank 定义：帧耗时 > 125ms
  - 用于统计展示，不影响触发逻辑
- **FR-011**: 默认丢帧阈值 SHOULD 为 `刷新率 × 5%`（向上取整）：
  - 60 Hz → 3 帧/秒
  - 90 Hz → 5 帧/秒
  - 120 Hz → 6 帧/秒
  - 144 Hz → 7 帧/秒
- **FR-012**: 用户 MUST 可配置丢帧阈值

#### 触发策略

- **FR-013**: 当 1 秒内丢帧数（Jank 数）> 阈值时触发保存流程
- **FR-014**: 触发后等待 2 秒稳定期，检查是否持续卡顿
- **FR-015**: 如持续卡顿（仍超阈值），继续延后（每次 2 秒，最多累计延后到 8 秒）
- **FR-016**: 稳定后（1 秒内 Jank 数 ≤ 阈值）自动保存当前 trace 段

#### 抓取控制

- **FR-017**: 默认最大抓取次数为 3，用户可配置
- **FR-018**: 达到最大次数后自动停止监控
- **FR-019**: 抓取时长与配置的 duration 一致（用于 buffer 估算）

#### 配置锁定

- **FR-019a**: 监控期间 MUST 禁用 Perfetto 抓取配置（Duration、Buffer、Atrace、Ftrace）
- **FR-019b**: 监控期间 SHOULD 允许修改丢帧阈值和最大抓取次数
- **FR-019c**: 监控配置修改 MUST 立即生效（无需重启监控）

#### 实时可视化

- **FR-020**: 系统 MUST 使用 `pyqtgraph` 显示 FPS 实时曲线图（默认最近 60 秒）
- **FR-020a**: 横轴 MUST 支持鼠标滚轮缩放（10~120 秒范围），时间刻度粒度为 1 秒
- **FR-021**: 曲线图 MUST 标记 Jank 事件点（黄色标记）和 BigJank 事件点（红色标记）
- **FR-022**: 系统 MUST 显示统计信息：平均 FPS、Jank 次数、BigJank 次数
- **FR-022a**: 应用切到后台时，曲线 MUST 显示 0 FPS，标注非抓取选区
- **FR-022b**: 曲线底部 MUST 标注「抓取选区」和「非抓取选区」（参考 PerfDog 风格）

#### 抓取判定控制

- **FR-026**: 系统 MUST 提供「暂停判定」按钮，暂停 Perfetto 抓取判定（不暂停帧率统计）
- **FR-027**: 暂停判定期间 MUST 标注为非抓取选区
- **FR-028**: 应用切到后台 MUST 自动暂停抓取判定
- **FR-029**: 应用恢复前台 5 秒后 MUST 自动恢复抓取判定

#### 帧率数据导出

- **FR-030**: 系统 SHOULD 支持导出帧率统计数据
- **FR-031**: 导出格式 MUST 兼容 PerfDog 导出表格式
- **FR-032**: 非抓取选区的数据行 SHOULD 保留但标记为空或 N/A

#### 停止时自动保存

- **FR-023**: 点击「停止」时 MUST 检查是否有未保存的正在运行的 trace
- **FR-024**: 如有未保存的 trace，MUST 先执行保存逻辑，再执行停止和导出
- **FR-025**: 日志 MUST 清晰显示自动保存行为

### Non-Functional Requirements

- **NFR-001**: 帧率监控 CPU 开销 < 5%
- **NFR-002**: 帧率更新延迟 < 500ms
- **NFR-003**: Jank 触发到保存完成 < 3 秒

### Key Entities

- **JankConfig**: Jank 检测配置（丢帧阈值、最大抓取次数、等待时间）
- **FrameStats**: 帧数据统计（FPS、丢帧数、Jank 事件列表）
- **JankEvent**: 单次 Jank 事件（时间戳、丢帧数、帧耗时）
- **MonitorState**: 监控状态（运行中/暂停判定/已停止）
- **CaptureRegion**: 抓取选区（开始时间、结束时间、是否抓取选区）

### UI Layout

```
┌────────────────────────────────────────────────────┐
│  ⚙ 抓取配置                                        │
│  Duration [____]  Buffer [____]  [📂 导入配置]      │
│  ☐ 手动设置 Buffer  ☐ 启用 Ftrace  ☑ 启用 Jank 检测│
├────────────────────────────────────────────────────┤
│  📦 Atrace Categories                              │
│  ☑ sched  ☑ gfx  ☑ view  ☑ input  ☑ freq  ...    │
├────────────────────────────────────────────────────┤
│  🎮 Jank 监控配置                                   │
│  目标应用: [com.tencent.tmgp.cod ▼] [🔄 刷新]      │
│  丢帧阈值: [3] 帧/秒   最大抓取: [3] 次             │
├────────────────────────────────────────────────────┤
│  📊 实时帧率 (PerfDog 风格)                         │
│  ┌──────────────────────────────────────────────┐  │
│  │ FPS ▲                  🟡 Jank  🔴 BigJank   │  │
│  │  60│    ╭──╮    ╭──╮   ╭──╮     ╭──╮       │  │
│  │  30│ ╭──╯  ╰────╯  ╰───╯  ╰─────╯  ╰──     │  │
│  │   0└────────────────────────────────────▶ t │  │
│  └──────────────────────────────────────────────┘  │
│  平均 FPS: 58.3  |  Jank: 5  |  BigJank: 1         │
├────────────────────────────────────────────────────┤
│  📊 状态: 🟢 监控中 (已抓取 1/3)                    │
│  [⏸ 暂停判定] [■ 停止] [📤 导出] [📂 历史]          │
└────────────────────────────────────────────────────┘
```

## Clarifications

### C1: 帧率数据源

**问题**：使用什么方式获取帧率数据？
**决策**：`dumpsys gfxinfo <package> framestats`
- 优点：详细帧耗时数据，可精确计算丢帧
- 缺点：需要指定包名
- 采样间隔：200ms

### C2: 丢帧判定算法

**问题**：如何定义丢帧？
**决策**：采用两级丢帧定义
1. **Jank（单帧丢帧）**：帧耗时 > 33.3ms
   - 用于曲线标黄点、Jank 统计
2. **BigJank**：帧耗时 > 125ms
   - 用于统计展示，不影响触发逻辑
- 参考 PerfDog 的 Jank/BigJank 判定标准

### C3: 触发策略

**问题**：如何避免频繁触发？
**决策**：
1. 1 秒内丢帧数 > 阈值时触发
2. 触发后等待 2 秒稳定期
3. 如持续卡顿，延后保存（最多 8 秒）
4. 不需要最小间隔（trace 不会重叠）

### C4: Perfetto 抓取模式

**问题**：使用什么 Perfetto 抓取模式？
**决策**：复用现有 autobuffer 模式
- 优点：实现简单，不会有 clone 时间窗口问题
- 缺点：设备重启会丢失当前段（可接受）

### C5: 应用刷新率检测

**问题**：如何获取目标应用的刷新率？
**决策**：
1. 优先从 `dumpsys display` 获取当前刷新率
2. 降级方案：默认 60 Hz

### C6: UI 布局位置

**问题**：Jank 监控面板放在哪里？
**决策**：
- 复选框与「启用 Ftrace 自定义」并排
- 配置面板在 Atrace Categories 下方弹出
- 如同时勾选 Ftrace，Jank 面板在 Ftrace 下方

### C7: 配置锁定策略

**问题**：监控期间哪些配置可以修改？
**决策**：
- **禁用修改**：Duration、Buffer、Atrace Categories、Ftrace（需重启 Perfetto）
- **允许修改**：丢帧阈值、最大抓取次数（立即生效）
- 原因：Perfetto 抓取参数在 daemon 启动后无法更改；监控参数是纯软件逻辑可动态调整

### C8: 前台应用检测与状态处理

**问题**：如何检测目标应用是否在前台？如何处理不同状态？
**决策**：
- 使用 `dumpsys activity activities | grep -E "mResumedActivity|topResumedActivity"` 获取当前前台应用
- 采样频率与帧率监控同步（200ms）
- **应用切到后台**：曲线显示 0 FPS，暂停抓取判定，标注非抓取选区
- **应用恢复前台**：等待 5 秒后自动恢复抓取判定，新建抓取选区
- **应用进程被杀**：结束监控，自动保存当前 trace 并导出

### C9: 图表库选择

**问题**：使用什么库实现实时 FPS 曲线图？
**决策**：`pyqtgraph`
- 优点：与 PyQt6 集成好，专为实时数据设计，性能优秀
- 缺点：需要额外依赖
- 备选：matplotlib（功能丰富但实时性能稍差）、自定义 QWidget（最轻量但开发成本高）

### C10: 抓取选区与非抓取选区

**问题**：如何区分抓取选区和非抓取选区？
**决策**：
- 曲线底部使用不同颜色区域标注
- 抓取选区：正常颜色（如绿色/蓝色）
- 非抓取选区：灰色或半透明
- 参考 PerfDog 的选区标注风格

### C11: 后台恢复延迟

**问题**：应用恢复前台后多久恢复抓取判定？
**决策**：5 秒
- 原因：避免切换瞬间的帧率波动导致误触发
- 期间显示帧率但不触发 Jank 保存

### C12: 帧率数据导出格式

**问题**：帧率数据导出格式？
**决策**：兼容 PerfDog Data_v4 格式
- 参考 `tests/res/Elden-*.xlsx` 中的 Data_v4 表
- 字段结构完全保留：Num, time, absTime, monoTime, label, Notes, FPS, Smooth, 1%Low(FPS), TinyJank, SmallJank, Jank, BigJank, Stutter[%], InterFrame
- 当前实现填充：Num, time, FPS, Jank, BigJank（其余为空，后续迭代补充）
- label 字段：非抓取选区为空，每个抓取选区使用唯一 label（如 capture1, capture2）
- 导出格式：xlsx（与 PerfDog 保持一致）
- 优先级：P2

## Success Criteria

### Measurable Outcomes

- **SC-001**: 帧率监控 CPU 开销 < 5%（通过 systrace 验证）
- **SC-002**: 从 Jank 发生到 trace 保存完成 < 10 秒
- **SC-003**: 误触发率 < 10%（连续测试 100 次）
- **SC-004**: 成功捕获 90% 以上的人工制造的卡顿事件

### Test Scenarios

1. 启动监控 → 手动制造卡顿 → 验证自动保存
2. 连续多次卡顿 → 验证延后机制正确工作
3. 达到最大次数 → 验证自动停止
4. 监控中应用退出 → 验证正确处理
5. 点击停止 → 验证自动保存当前 trace
