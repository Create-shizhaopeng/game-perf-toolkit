# Implementation Plan: Jank 自动检测与抓取

## 目录

- [技术上下文](#技术上下文)
- [架构设计](#架构设计)
- [数据模型](#数据模型)
- [实现阶段](#实现阶段)
- [关键决策](#关键决策)
- [风险评估](#风险评估)

**Feature Branch**: `005-auto-jank-capture`  
**Created**: 2026-04-02  
**Spec Reference**: `spec.md`, `ui-design.md`  

---

## 技术上下文

### 现有技术栈

- **GUI 框架**: PyQt6
- **图表库**: pyqtgraph（新增依赖）
- **数据存储**: SQLite（共享数据库 + 模块数据库）
- **配置管理**: Pydantic 模型 + JSON
- **ADB 操作**: `toolkit.core.adb_manager`
- **事件通信**: EventBus
- **后台线程**: QThread + pyqtSignal

### 新增依赖

| 依赖 | 版本 | 用途 |
|-----|-----|-----|
| pyqtgraph | >=0.13.0 | 实时 FPS 曲线图 |
| numpy | >=1.24 | pyqtgraph 依赖，数据处理 |

### 现有代码入口

| 文件 | 说明 |
|-----|-----|
| `src/gui_tab.py` | GUI Tab 实现，需新增 Jank 复选框和监控面板 |
| `src/service.py` | 业务逻辑，需新增帧率监控和触发逻辑 |
| `src/models.py` | 数据模型，需新增 Jank 相关模型 |
| `src/capture_worker.py` | 现有 Perfetto 抓取 Worker |

### ADB 命令依赖

| 命令 | 用途 |
|-----|-----|
| `dumpsys gfxinfo <pkg> framestats` | 获取帧耗时数据 |
| `dumpsys display` | 获取屏幕刷新率 |
| `dumpsys activity activities` | 检测前台应用 |
| `pm list packages -3` | 列出第三方应用 |

---

## 架构设计

### 组件关系

```
┌───────────────────────────────────────────────────────────────────────┐
│                             GUI Layer                                  │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ PerfettoTab                                                      │  │
│  │  ├─ ☑ 启用 Jank 检测 ─────▶ JankConfigPanel                     │  │
│  │  │                          ├─ AppSelector (QComboBox)           │  │
│  │  │                          ├─ ThresholdSpinBox                  │  │
│  │  │                          └─ MaxCaptureSpinBox                 │  │
│  │  │                                                               │  │
│  │  └─ JankMonitorWidget ◀─── FpsChartWidget (pyqtgraph)           │  │
│  │       ├─ FPS 曲线                                                │  │
│  │       ├─ Jank/BigJank 标记                                       │  │
│  │       └─ 统计区（平均 FPS、Jank、BigJank）                        │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬──────────────────────────────────────┘
                                 │ signals/slots
┌────────────────────────────────▼──────────────────────────────────────┐
│                           Service Layer                                │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ JankMonitorService                                               │  │
│  │  ├─ start_monitor(package: str) → None                          │  │
│  │  ├─ stop_monitor() → None                                       │  │
│  │  ├─ get_running_apps() → List[AppInfo]                          │  │
│  │  ├─ get_display_refresh_rate() → int                            │  │
│  │  └─ is_app_foreground(package: str) → bool                      │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ FrameStatsParser                                                 │  │
│  │  ├─ parse_framestats(output: str) → List[FrameData]             │  │
│  │  ├─ calculate_fps(frames: List[FrameData]) → float              │  │
│  │  └─ detect_janks(frames: List[FrameData]) → List[JankEvent]     │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬──────────────────────────────────────┘
                                 │
┌────────────────────────────────▼──────────────────────────────────────┐
│                          Worker Layer (QThread)                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ JankMonitorWorker(QThread)                                       │  │
│  │  ├─ 200ms 轮询 dumpsys gfxinfo                                   │  │
│  │  ├─ 检测前台应用状态                                              │  │
│  │  ├─ 发射 frame_stats_ready(FrameStats) 信号                      │  │
│  │  ├─ 发射 jank_triggered(JankEvent) 信号                          │  │
│  │  └─ 发射 app_state_changed(bool) 信号                            │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

### 帧率监控时序图

```
JankMonitorWorker                 Service                    GUI
       │                            │                         │
       ├──[200ms]──────────────────▶│                         │
       │  adb shell dumpsys gfxinfo │                         │
       │◀─────── framestats output ─┤                         │
       │                            │                         │
       │  parse_framestats()        │                         │
       │  detect_janks()            │                         │
       │                            │                         │
       ├─── frame_stats_ready ─────▶├─── update_chart ───────▶│
       │                            │                         │
       │  [if jank_count > threshold]                         │
       ├─── jank_triggered ────────▶├─── start_save_timer ───▶│
       │                            │                         │
       │  [2-8 秒稳定期]             │                         │
       │                            ├─── save_current_trace ─▶│
       │                            │                         │
```

### 触发状态机

```
                 ┌────────────────────────────────────────┐
                 │                                        │
                 ▼                                        │
┌─────────┐  jank_count > threshold  ┌─────────────┐      │
│ IDLE    │ ──────────────────────▶  │ TRIGGERED   │      │
└─────────┘                          └──────┬──────┘      │
     ▲                                      │             │
     │                                      │ 2 秒后      │
     │                                      ▼             │
     │                               ┌─────────────┐      │
     │                               │ STABILIZING │ ─────┤ 仍然卡顿
     │                               └──────┬──────┘      │ (延后 2s，最多 8s)
     │                                      │             │
     │            稳定                      │             │
     │ ◀────────────────────────────────────┘             │
     │                                                    │
     └── save_trace() ◀───────────────────────────────────┘
```

---

## 数据模型

### Pydantic 模型

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class MonitorState(str, Enum):
    IDLE = "idle"
    MONITORING = "monitoring"
    TRIGGERED = "triggered"
    STABILIZING = "stabilizing"
    SAVING = "saving"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"

class FrameData(BaseModel):
    """单帧数据"""
    timestamp_ns: int
    frame_duration_ms: float
    is_jank: bool = False
    is_big_jank: bool = False

class FrameStats(BaseModel):
    """帧数据统计（每 200ms 更新）"""
    timestamp: datetime
    fps: float
    jank_count: int
    big_jank_count: int
    frames: list[FrameData] = []

class JankEvent(BaseModel):
    """单次 Jank 触发事件"""
    timestamp: datetime
    jank_count: int
    avg_frame_time_ms: float
    max_frame_time_ms: float

class JankConfig(BaseModel):
    """Jank 检测配置"""
    enabled: bool = False
    target_package: str = ""
    jank_threshold: int = 3  # 帧/秒
    max_captures: int = 3
    stabilize_delay_sec: int = 2
    max_stabilize_sec: int = 8
    
    # 运行时状态（不持久化）
    class Config:
        extra = "ignore"

class AppInfo(BaseModel):
    """应用信息"""
    package_name: str
    app_name: str | None = None
    is_foreground: bool = False

class MonitorStats(BaseModel):
    """监控统计信息"""
    avg_fps: float = 0.0
    total_jank_count: int = 0
    total_big_jank_count: int = 0
    capture_count: int = 0
    monitor_duration_sec: float = 0.0

class CaptureRegion(BaseModel):
    """抓取选区"""
    start_time: datetime
    end_time: datetime | None = None
    is_capture: bool = True  # True=抓取选区, False=非抓取选区
    label: str = ""  # 如 "capture1", "capture2"

class FrameExportRow(BaseModel):
    """导出数据行（兼容 PerfDog Data_v4 格式）"""
    num: int
    time: int  # 毫秒
    abs_time: int | None = None
    mono_time: int | None = None
    label: str = ""
    notes: str = ""
    fps: float | None = None
    smooth: float | None = None
    low_1_percent_fps: float | None = None
    tiny_jank: int | None = None
    small_jank: int | None = None
    jank: int | None = None
    big_jank: int | None = None
    stutter_percent: float | None = None
    inter_frame: float | None = None
```

### 与现有模型的关系

```python
# src/models.py 扩展
class CaptureConfig(BaseModel):
    # ... 现有字段 ...
    jank: JankConfig = Field(default_factory=JankConfig)
```

---

## 实现阶段

### Phase 1: 核心服务层

1. **新建 `src/jank_parser.py`**：帧数据解析器
   - `parse_framestats(output: str) → List[FrameData]`
   - `calculate_fps(frames: List[FrameData]) → float`
   - `detect_janks(frames: List[FrameData], threshold_ms: float) → List[JankEvent]`

2. **新建 `src/jank_service.py`**：Jank 监控服务
   - `get_running_apps() → List[AppInfo]`
   - `get_display_refresh_rate() → int`
   - `is_app_foreground(package: str) → bool`

3. **扩展 `src/models.py`**：添加 Jank 相关模型

### Phase 2: 后台 Worker

1. **新建 `src/jank_worker.py`**：监控 Worker（QThread）
   - 200ms 轮询 `dumpsys gfxinfo`
   - 检测前台应用状态
   - 触发状态机管理
   - 信号发射：`frame_stats_ready`, `jank_triggered`, `app_state_changed`

2. **集成到现有 capture 流程**
   - 与 `CaptureWorker` 协同工作
   - 触发时调用 `service.save_trace()`

### Phase 3: GUI 组件

1. **新建 `src/jank_panel.py`**：配置面板
   - `JankConfigPanel`：复选框 + 配置区
   - `AppSelector`：应用选择下拉框

2. **新建 `src/fps_chart.py`**：实时图表
   - `FpsChartWidget`：pyqtgraph 曲线图
   - Jank/BigJank 标记
   - 横轴缩放支持

3. **新建 `src/jank_stats.py`**：统计显示
   - `MonitorStatsWidget`：平均 FPS、Jank、BigJank 计数

4. **扩展 `src/gui_tab.py`**：集成 Jank 组件
   - 添加复选框
   - 配置锁定逻辑
   - 状态栏更新

### Phase 4: 停止时自动保存

1. **修改 `src/service.py`**：
   - 新增 `stop_with_auto_save()` 方法
   - 检查是否有未保存的 trace
   - 自动保存后停止

2. **修改 `src/gui_tab.py`**：
   - 停止按钮点击时调用新方法
   - 日志显示自动保存行为

### Phase 5: 抓取选区与暂停

1. **修改 `src/jank_worker.py`**：
   - 添加 `pause_capture_detection()` 方法
   - 添加 `resume_capture_detection()` 方法
   - 管理 `CaptureRegion` 列表

2. **修改 `src/fps_chart.py`**：
   - 添加选区底部彩色条显示
   - 绿色 = 抓取选区，灰色 = 非抓取选区

3. **修改 `src/gui_tab.py`**：
   - 在图表区域添加「暂停判定」按钮
   - 连接暂停/恢复信号

### Phase 6: 数据导出（P2）

1. **新建 `src/frame_exporter.py`**：
   - `export_to_xlsx(data: List[FrameExportRow], path: Path)`
   - 兼容 PerfDog Data_v4 格式
   - 非抓取选区 label 为空

2. **修改 `src/gui_tab.py`**：
   - 添加「导出」按钮
   - 调用 exporter 生成文件

### Phase 7: 测试与优化

1. **编写单元测试**
   - `test_jank_parser.py`：帧数据解析测试
   - `test_jank_service.py`：服务层测试
   - `test_jank_worker.py`：Worker 信号测试
   - `test_frame_exporter.py`：导出格式测试

2. **性能验证**
   - 监控 CPU 开销（目标 < 5%）
   - 帧率更新延迟（目标 < 500ms）

---

## 关键决策

### D1: 帧数据解析算法

**决策**：解析 `dumpsys gfxinfo <pkg> framestats` 的 PROFILEDATA 块

```
---PROFILEDATA---
Flags,IntendedVsync,Vsync,OldestInputEvent,...,FrameCompleted
0,123456789,123456789,9223372036854775807,...,123567890
...
```

- 帧耗时 = `FrameCompleted - IntendedVsync`
- Jank 判定：帧耗时 > 33.3ms
- BigJank 判定：帧耗时 > 125ms

### D2: FPS 计算方法

**决策**：基于最近 1 秒内的帧数

```python
def calculate_fps(frames: List[FrameData], window_ms: int = 1000) -> float:
    recent_frames = [f for f in frames if f.timestamp_ns > cutoff]
    return len(recent_frames) / (window_ms / 1000)
```

### D3: 前台应用检测

**决策**：解析 `dumpsys activity activities` 输出

```python
def is_app_foreground(package: str) -> bool:
    output = adb.shell("dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'")
    return package in output
```

### D4: 曲线数据结构

**决策**：使用 numpy 数组 + 滚动窗口

```python
class FpsChartData:
    def __init__(self, max_seconds: int = 120):
        # 预分配数组
        self.timestamps = np.zeros(max_seconds * 5)  # 200ms 间隔
        self.fps_values = np.zeros(max_seconds * 5)
        self.jank_markers = []  # (timestamp, fps) 元组列表
        self.current_idx = 0
```

### D5: 配置锁定实现

**决策**：使用 `setEnabled(False)` + 视觉提示

```python
def lock_capture_config(self):
    self._duration_spin.setEnabled(False)
    self._buffer_spin.setEnabled(False)
    self._atrace_panel.setEnabled(False)
    self._ftrace_panel.setEnabled(False)
    self._target_app_combo.setEnabled(False)
    self._status_label.setText("🔒 监控中")
    
def unlock_capture_config(self):
    self._duration_spin.setEnabled(True)
    # ... 恢复所有控件
```

### D6: pyqtgraph 图表配置

**决策**：使用 `PlotWidget` + 实时更新

```python
from pyqtgraph import PlotWidget, mkPen

class FpsChartWidget(PlotWidget):
    def __init__(self):
        super().__init__()
        self.setBackground('w')
        self.setLabel('left', 'FPS')
        self.setLabel('bottom', 'Time (s)')
        self.setXRange(-60, 0)
        self.setYRange(0, 120)
        
        # FPS 曲线
        self.fps_curve = self.plot(pen=mkPen(color='#6C9BCF', width=2))
        
        # Jank 标记（黄色）
        self.jank_scatter = self.plot(pen=None, symbol='o', 
                                       symbolBrush='#FABF42', symbolSize=8)
        
        # BigJank 标记（红色）
        self.bigjank_scatter = self.plot(pen=None, symbol='o',
                                          symbolBrush='#F85149', symbolSize=10)
```

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|-----|-----|---------|
| dumpsys 命令延迟波动 | 帧率数据不准确 | 使用时间戳校正，丢弃异常数据 |
| 高频轮询导致 CPU 开销 | 影响测试准确性 | 优化解析算法，监控开销 |
| 应用切后台检测延迟 | 误触发 Jank | 增加前台状态缓冲时间 |
| pyqtgraph 内存泄漏 | 长时间监控崩溃 | 限制数据点数量，定期清理 |
| 触发与保存时机冲突 | trace 数据不完整 | 使用状态机严格管理 |
| 多线程信号竞争 | 数据不一致 | 使用 Qt 信号队列，避免直接共享状态 |
