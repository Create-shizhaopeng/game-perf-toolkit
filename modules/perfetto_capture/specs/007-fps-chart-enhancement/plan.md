# Implementation Plan: FPS 帧率曲线图表增强

**Branch**: `007-fps-chart-enhancement` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
- [Design](#design)
  - [数据存储重构](#数据存储重构)
  - [交互式视图管理](#交互式视图管理)
  - [鼠标悬停信息展示](#鼠标悬停信息展示)
  - [组件交互流程](#组件交互流程)
- [Data Model](#data-model)

## Summary

修复 FPS 帧率曲线在长时间监控后数据丢失的问题（根因：固定 1500 点环形缓冲区），并增强图表交互能力。核心技术方案：

1. **数据存储**：替换环形缓冲区为分块增长 numpy 数组（初始 1800 点，2 倍扩容），保留完整监控期间数据（受最大监控时长限制，默认 3h，上限 12h）
2. **缩放拖动**：启用 pyqtgraph ViewBox 的 X 轴鼠标交互，添加底部 QScrollBar 同步
3. **跟随模式**：全量视图自动跟随新数据，缩放后切换为手动浏览模式
4. **鼠标悬停**：pyqtgraph CrosshairROI + TextItem 显示时间/帧率/Jank 类型

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: pyqtgraph 0.13+, numpy, PyQt6
**Storage**: 内存（numpy 数组），无持久化
**Testing**: pytest（FpsChartData 单元测试）
**Target Platform**: Windows 10+ / Linux（PyQt6 桌面应用）
**Project Type**: desktop-app（perfetto_capture 模块 GUI 组件）
**Performance Goals**: 100K 数据点更新延迟 < 50ms
**Constraints**: 不影响 service.py / jank_worker.py
**Scale/Scope**: 主要重构 `fps_chart.py`，另涉及 `models.py`（配置字段）、`jank_panel.py`（UI 控件）、`gui_tab.py`（计时器逻辑）

## Constitution Check

| 原则 | 状态 | 说明 |
|------|------|------|
| Plugin-First | ✅ PASS | 变更仅在 perfetto_capture 模块内部 |
| Three-Surface Unity | ✅ PASS | 仅涉及 GUI 层，不影响 service/CLI/Agent API |
| Presentation Separation | ✅ PASS | FpsChartData 是数据逻辑，FpsChartWidget 是展示层，职责清晰 |
| Dependency Inversion | ✅ PASS | 不引入跨模块导入 |
| Open-Closed | ✅ PASS | 不修改框架代码 |
| QThread 信号通信 | ✅ N/A | 不涉及新线程 |
| Pydantic 模型 | ✅ N/A | 不涉及公共 API 变更 |
| UTF-8 编码 | ✅ PASS | 所有输出保持 UTF-8 |

无违规项，无需 Complexity Tracking。

## Project Structure

### Documentation

```text
modules/perfetto_capture/specs/007-fps-chart-enhancement/
├── spec.md
├── plan.md           # 本文件
├── checklists/
│   └── requirements.md
└── tasks.md          # 后续生成
```

### Source Code (affected files)

```text
modules/perfetto_capture/
├── src/
│   ├── fps_chart.py          # 主要变更文件（数据存储、视图交互、悬停信息）
│   ├── models.py             # 新增 max_duration_hours 配置字段
│   ├── jank_panel.py         # 新增"监控时长" QSpinBox
│   └── gui_tab.py            # 新增监控计时器和自动停止逻辑
└── tests/
    ├── test_fps_chart.py      # 新增测试文件
    └── test_capture_region.py # 更新 MockFpsChartData 适配新接口
```

## Design

### 数据存储重构

**现状**：`FpsChartData` 使用 `np.zeros(max_points)` 预分配固定数组，`max_points = 300 * 5 = 1500`。满时执行 `array[:-1] = array[1:]` 左移一位，丢弃最老数据。

**方案**：分块增长 numpy 数组

```python
class FpsChartData:
    INITIAL_CAPACITY = 1800  # 约 6 分钟
    
    def __init__(self) -> None:
        self._capacity = self.INITIAL_CAPACITY
        self._timestamps = np.empty(self._capacity, dtype=np.float64)
        self._fps_values = np.empty(self._capacity, dtype=np.float64)
        self._size = 0  # 实际数据量
        # ...其他字段不变

    def add_stats(self, stats: FrameStats) -> None:
        if self._size >= self._capacity:
            self._grow()
        # 写入数据...

    def _grow(self) -> None:
        new_cap = self._capacity * 2
        new_ts = np.empty(new_cap, dtype=np.float64)
        new_fps = np.empty(new_cap, dtype=np.float64)
        new_ts[:self._capacity] = self._timestamps
        new_fps[:self._capacity] = self._fps_values
        self._timestamps = new_ts
        self._fps_values = new_fps
        self._capacity = new_cap

    def get_curve_data(self) -> tuple[np.ndarray, np.ndarray]:
        return self._timestamps[:self._size], self._fps_values[:self._size]
```

**扩容时机与内存估算**：

| 持续时间 | 数据点数 | 扩容次数 | 数组容量 | 内存(两数组) |
|----------|---------|---------|---------|------------|
| 6 分钟 | 1,800 | 0 | 1,800 | 28 KB |
| 12 分钟 | 3,600 | 1 | 3,600 | 56 KB |
| 24 分钟 | 7,200 | 2 | 7,200 | 112 KB |
| 1 小时 | 18,000 | 4 | 28,800 | 450 KB |
| 2 小时 | 36,000 | 5 | 57,600 | 900 KB |
| 8 小时 | 144,000 | 7 | 230,400 | 3.6 MB |

**关键改动**：
- `get_curve_data()` 返回 `self._timestamps[:self._size]` 的视图（不做 copy），避免重复内存分配
- Jank/BigJank 标记仍用 Python list（数量远小于主数据，无需优化）
- `clear()` 重置 `_size = 0` 并重新分配初始容量数组

### 交互式视图管理

**核心机制**：利用 pyqtgraph `ViewBox` 内置的缩放/拖动能力，叠加跟随模式状态管理。

#### ViewBox 配置

```python
vb = self._plot.getViewBox()
vb.setMouseEnabled(x=True, y=False)    # 仅允许 X 轴交互
vb.setLimits(xMin=0, yMin=0, yMax=200)  # X 下界固定 0，上界动态
vb.enableAutoRange(axis='x', enable=False)  # 禁用自动范围，手动管理
```

#### 跟随模式状态机

```
状态转换:
  FOLLOWING (初始/全量视图)
    ├── 用户缩放/拖动 → BROWSING
    └── 新数据到达 → 自动更新 XRange(0, latest+5)

  BROWSING (用户浏览历史)
    ├── 用户缩放回全量 → FOLLOWING
    └── 新数据到达 → 仅更新 xMax 上限，不移动视图
```

**判定逻辑**：
- 进入 BROWSING：`sigRangeChangedManually` 信号触发时，如果视图范围不等于全量范围
- 返回 FOLLOWING：视图 X 范围涵盖 `[0, latest_data_time]` 时（容差 ±2 秒）

#### 底部滚动条

使用 `QScrollBar(Qt.Orientation.Horizontal)`，与 ViewBox 双向同步：

- **ViewBox → ScrollBar**：`sigRangeChanged` 信号触发时更新 scrollbar 的 `setRange`、`setPageStep`、`setValue`
- **ScrollBar → ViewBox**：`valueChanged` 信号触发时调用 `setXRange` 平移视图
- 滑块宽度反映缩放比例：`pageStep = visible_width / total_width * scrollbar_range`

#### X 轴右边界限制

```python
# 每次新数据到达时更新上限
vb.setLimits(xMax=latest_time + 2)
```

#### Y 轴自适应（缩放后）

```python
# 监听 sigRangeChanged，获取当前可见 X 范围
x_min, x_max = vb.viewRange()[0]
# 筛选范围内的 FPS 数据
mask = (timestamps >= x_min) & (timestamps <= x_max)
visible_fps = fps_values[mask]
if len(visible_fps) > 0:
    y_max = _calc_y_max(visible_fps.max())
    self._plot.setYRange(0, y_max, padding=0.05)
```

### 鼠标悬停信息展示

使用 pyqtgraph 内置的 `SignalProxy` + `InfiniteLine` 实现十字线，`TextItem` 显示信息。

#### 组件构成

```
CrosshairOverlay:
  ├── InfiniteLine(vertical)   # 垂直十字线
  ├── InfiniteLine(horizontal) # 水平十字线
  └── TextItem                 # 信息浮窗
```

#### 数据查找

```python
def _find_nearest_point(self, mouse_x: float) -> int:
    """二分查找最近数据点索引。"""
    timestamps = self._data._timestamps[:self._data._size]
    idx = np.searchsorted(timestamps, mouse_x)
    # 比较左右邻居取更近的
    ...
```

#### 信息格式

- 普通帧：`14:32:05  FPS: 58`
- Jank 帧：`14:32:05  FPS: 23  ⚠ Jank`
- BigJank 帧：`14:32:05  FPS: 12  🔴 BigJank`

时间从 `_start_time + timedelta(seconds=elapsed)` 换算为 24 小时制。

#### 显示/隐藏

- 鼠标进入 PlotWidget 区域：显示十字线
- 鼠标离开 PlotWidget 区域：隐藏十字线和信息框
- 通过 `scene().sigMouseMoved` 和 `leaveEvent` 控制

### 监控时长保护

**方案**：在 `gui_tab.py` 中使用 `QTimer` 监控已运行时长。

- `JankConfig.max_duration_hours` 新增字段（Pydantic，默认 3，ge=1，le=12）
- `JankConfigPanel` 新增 QSpinBox 控件（与现有 Jank 阈值、最大抓取次数同行布局）
- `gui_tab.py` 启动监控时记录起始时间，QTimer 每秒检查是否超过设定时长
- 超时后调用 `_on_stop()`（复用现有停止逻辑），并在日志区记录提示

### 组件交互流程

```
新数据到达 (update_stats)
    │
    ├── FpsChartData.add_stats()     # 写入数据（可能触发扩容）
    │
    ├── if FOLLOWING:
    │   ├── 更新 fps_curve 数据
    │   ├── setXRange(0, latest + 5)  # 全量显示
    │   ├── 根据全量数据计算 Y 轴范围
    │   └── 更新 scrollbar 位置（最右侧）
    │
    ├── if BROWSING:
    │   ├── 更新 fps_curve 数据
    │   ├── 仅更新 xMax 上限限制
    │   ├── 根据可见范围数据计算 Y 轴范围
    │   └── 更新 scrollbar 范围（不改变位置）
    │
    └── 更新 scatter/regions/stats_overlay
```

## Data Model

### FpsChartData（重构）

| 字段 | 类型 | 说明 |
|------|------|------|
| `_capacity` | `int` | 当前数组容量 |
| `_size` | `int` | 实际数据点数量 |
| `_timestamps` | `np.ndarray[float64]` | 时间戳数组（秒，从 0 开始） |
| `_fps_values` | `np.ndarray[float64]` | FPS 值数组 |
| `_start_time` | `datetime \| None` | 首个数据点的绝对时间 |
| `_max_fps_seen` | `float` | 历史最大 FPS |
| `_jank_points` | `list[tuple[float, float]]` | Jank 标记 (elapsed, fps) |
| `_big_jank_points` | `list[tuple[float, float]]` | BigJank 标记 (elapsed, fps) |

### JankConfig（扩展）

| 字段 | 类型 | 说明 |
|------|------|------|
| `max_duration_hours` | `int` | 最大监控时长（小时），默认 3，范围 1-12 |

### FpsChartWidget（新增状态）

| 字段 | 类型 | 说明 |
|------|------|------|
| `_following` | `bool` | 是否处于跟随模式（默认 True） |
| `_scrollbar` | `QScrollBar` | 底部水平滚动条 |
| `_crosshair_v` | `InfiniteLine` | 垂直十字线 |
| `_crosshair_h` | `InfiniteLine` | 水平十字线 |
| `_hover_text` | `TextItem` | 悬停信息浮窗 |
| `_syncing_scrollbar` | `bool` | 防止 scrollbar 与 viewbox 信号循环 |
