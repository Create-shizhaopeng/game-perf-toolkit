# 002-auto-buffer: 基于抓取时长自动计算 Buffer 大小

## 目录

- [背景与动机](#背景与动机)
- [需求概述](#需求概述)
- [与双模抓取引擎的关系](#与双模抓取引擎的关系)
- [功能需求](#功能需求)
  - [FR-001: 基于 duration 自动计算 buffer](#fr-001-基于-duration-自动计算-buffer)
  - [FR-002: 安全系数与上下限](#fr-002-安全系数与上下限)
  - [FR-003: GUI 联动显示](#fr-003-gui-联动显示)
  - [FR-004: 手动覆盖支持](#fr-004-手动覆盖支持)
  - [FR-005: 双缓冲区保留进程名](#fr-005-双缓冲区保留进程名)
- [数据模型变更](#数据模型变更)
- [计算公式](#计算公式)
  - [分档与 tag 计数](#分档与-tag-计数)
- [验收标准](#验收标准)

## 背景与动机

当前 `perfetto_capture` 模块的 `buffer_size_kb` 和 `duration_sec` 是两个独立参数，
但用户实际关心的是**抓取时长**，而非底层 buffer 大小。

在 RING_BUFFER 模式下，系统负载不同时事件生成速率差异很大（1-10+ MB/s），
固定 buffer 无法保证用户期望的抓取时长：
- 低负载：32MB 可存 30+ 秒
- 高负载：32MB 可能只存 3 秒

用户需要一种机制让 `duration_sec` 控制实际抓取时长。

## 需求概述

采用**方案 A：自动计算 buffer 大小**，根据 `duration_sec`、已选 atrace categories 数量及
ftrace events 数量（合计为 tag 总数），自动推算合理的 `buffer_size_kb`，使 RING_BUFFER 尽量能容纳用户期望时长的数据。

## 与双模抓取引擎的关系

自动计算的 `buffer_size_kb` 写入 TraceConfig 的 ring buffer 配置，与设备侧使用 **Snapshot（`--detach` + `--clone`）** 还是 **Autobuffer（`--background`）** 无关：两种模式共用同一套 buffer 体量估算；双模由 `probe_perfetto_capabilities()` 与 `CaptureMode` 在引擎层选择（详见 [001-migration/spec.md](../001-migration/spec.md)）。

## 功能需求

### FR-001: 基于 duration 自动计算 buffer

- `buffer_size_kb` 根据以下参数自动计算：
  - `duration_sec`：用户设定的期望抓取时长
  - **tag 总数**：已选 **atrace categories 数量** 与 **ftrace events 数量** 之和（二者均计入负载）
  - `LIGHT_RATE_KB_PER_SEC`：轻载档基线速率（KB/s）
  - `HEAVY_PER_CAT_RATE_KB`：超过轻载阈值后，每多一个 tag 的附加速率（KB/s/tag）
  - `safety_factor`：安全系数
- `calculate_buffer_size(...)` 支持显式传入 `ftrace_count`；未传时从配置中的 `advanced.ftrace_events` 读取

### FR-002: 安全系数与上下限

- 安全系数默认 **1.2**（在实测校准速率基础上留余量，覆盖突发）
- 计算结果设下限 **91136 KB（约 89 MB）**，防止 buffer 过小
- 计算结果设上限 **512000 KB（500 MB）**，防止 buffer 过大
- 用户可通过配置文件调整安全系数（有效范围以 Pydantic 模型为准）

### FR-003: GUI 联动显示

- `duration_sec` SpinBox 变化时实时更新 `buffer_size_kb` 显示值
- Categories 勾选变化时实时更新 `buffer_size_kb` 显示值
- **Ftrace Events** 复选框勾选/取消或具体 event 勾选变化时，同样触发 buffer 重新计算
- Buffer SpinBox 取值范围 **91136～512000 KB**（约 89 MB～500 MB）；未勾选「手动设置 Buffer」时为 **只读**（`setReadOnly(True)`），与计算值联动
- 自动模式下 Buffer 带标注「(自动)」；提供「手动覆盖」复选框切换到可编辑模式
- 抓取中（`_set_capturing`）切换状态时，须正确处理手动覆盖开关与只读态，避免误改计算值

### FR-004: 手动覆盖支持

- 用户可勾选「手动设置 Buffer」切换到手动模式
- 手动模式下 Buffer SpinBox **可编辑**（解除只读）；未勾选时保持只读并与自动计算联动（见 FR-003）
- 手动模式下不随 duration、categories、ftrace 勾选变化而改写用户固定值
- 手动设置的值持久化到用户配置

### FR-005: 双缓冲区保留进程名

- 维持已实现的双缓冲区策略
- buffer 0（主 ftrace 数据）使用自动计算的大小
- buffer 1（process_stats/packages_list）固定 4096 KB
- 确保进程名在任何负载下不丢失

## 数据模型变更

```python
class CaptureConfig(BaseModel):
    duration_sec: int = 15
    buffer_size_kb: int | None = None  # None 表示自动计算
    buffer_manual_override: bool = False  # True 时使用 buffer_size_kb 固定值
    buffer_safety_factor: float = 1.2
    # ... 其余字段不变
```

## 计算公式

记 **tag 总数** `total_tags = len(atrace_categories) + len(ftrace_events)`；`calculate_buffer_size` 的 `ftrace_count` 参数对应上式中的 ftrace 项（未传则从配置读取）。

```
LIGHT_RATE_KB_PER_SEC = 9200       # 轻载档基线 (KB/s)，来自实测 90 MB / 10 s
HEAVY_PER_CAT_RATE_KB = 2600       # 每多一个 tag 的附加速率 (KB/s)
LIGHT_CAT_THRESHOLD = 7            # 轻载档 tag 上限（含）

若 total_tags ≤ 7:
    estimated_rate = LIGHT_RATE_KB_PER_SEC
否则:
    heavy_count = total_tags - LIGHT_CAT_THRESHOLD
    estimated_rate = LIGHT_RATE_KB_PER_SEC + heavy_count × HEAVY_PER_CAT_RATE_KB

raw_kb = int(duration_sec × estimated_rate × safety_factor)
buffer_size_kb = clamp(raw_kb, MIN_BUFFER_KB, MAX_BUFFER_KB)
其中 MIN_BUFFER_KB = 91136，MAX_BUFFER_KB = 512000
```

### 分档与 tag 计数

- **tag** 同时包含 atrace category 与 ftrace event，二者均增加 trace 写入负载，须一并计入 `total_tags`。
- **轻载档**（`total_tags ≤ 7`）：仅使用基线速率 9200 KB/s。
- **重载档**（`total_tags > 7`）：对超出 7 的每个 tag 追加 2600 KB/s（由多 category 实测曲线等比缩放得到）。

**实测校准数据**（游戏场景，重新标定）：

| 数据点 | 说明 |
|--------|------|
| **90 MB / 10 s** | 约 **9200 KB/s**，作为 7 个 atrace category 典型负载下的基线速率 |

**参数选择依据**：
- `LIGHT_RATE_KB_PER_SEC = 9200`：由 **90 MB / 10 s** 换算（≈ 9.2 MB/s）
- `HEAVY_PER_CAT_RATE_KB = 2600`：高 category 数场景下相对轻载档的增量，与历史多 cat 实测趋势一致并缩放
- `safety_factor` 默认 **1.2**：在标定速率上预留约 20% 余量以覆盖波动（可在配置中调整）

示例：**7 个 atrace categories**、**0 个 ftrace event**、`duration_sec = 15`、**安全系数 1.2**（轻载档）  
→ `9200 × 15 × 1.2 = 165600` KB ≈ **161.7 MB**

## 验收标准

| ID | 验收标准 | 通过条件 |
|----|---------|---------|
| AC-01 | 默认模式下 buffer 随 duration 自动更新 | 修改 duration，buffer 值实时变化 |
| AC-02 | 默认模式下 buffer 随 tag 负载更新 | 增减 categories 或 ftrace events，buffer 值实时变化 |
| AC-03 | 自动计算值在合理范围 | 15s / 7 atrace categories / 无 ftrace / 默认安全系数 1.2 → 约 **160–170 MB** 量级 |
| AC-04 | 上下限生效 | 自动计算结果不低于 **约 89 MB（91136 KB）**，不高于 **500 MB（512000 KB）** |
| AC-05 | 手动模式可覆盖 | 勾选手动后 buffer 可自由编辑 |
| AC-06 | 配置持久化 | 手动模式和值保存到用户配置，重启恢复 |
| AC-07 | 进程名不丢失 | 高负载场景下抓取的 trace 仍有完整进程名 |
