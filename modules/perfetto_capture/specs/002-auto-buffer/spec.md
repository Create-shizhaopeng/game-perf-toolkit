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

采用**方案 A：自动计算 buffer 大小**，根据 `duration_sec` 和已选 atrace categories 
数量，自动推算合理的 `buffer_size_kb`，使 RING_BUFFER 尽量能容纳用户期望时长的数据。

## 与双模抓取引擎的关系

自动计算的 `buffer_size_kb` 写入 TraceConfig 的 ring buffer 配置，与设备侧使用 **Snapshot（`--detach` + `--clone`）** 还是 **Autobuffer（`--background`）** 无关：两种模式共用同一套 buffer 体量估算；双模由 `probe_perfetto_capabilities()` 与 `CaptureMode` 在引擎层选择（详见 [001-migration/spec.md](../001-migration/spec.md)）。

## 功能需求

### FR-001: 基于 duration 自动计算 buffer

- `buffer_size_kb` 根据以下参数自动计算：
  - `duration_sec`：用户设定的期望抓取时长
  - `category_count`：已选 atrace categories 数量
  - `rate_factor`：每个 category 的估算速率因子（KB/s/category）
  - `safety_factor`：安全系数

### FR-002: 安全系数与上下限

- 安全系数默认 **1.05**（在实测校准速率基础上略留余量）
- 计算结果设下限 8192 KB（8MB），防止 buffer 过小
- 计算结果设上限 524288 KB（512MB），防止 buffer 过大
- 用户可通过配置文件调整安全系数（有效范围以 Pydantic 模型为准）

### FR-003: GUI 联动显示

- `duration_sec` SpinBox 变化时实时更新 `buffer_size_kb` 显示值
- Categories 勾选变化时实时更新 `buffer_size_kb` 显示值
- Buffer 值显示为只读/计算值，带标注"(自动)"
- 提供"手动覆盖"复选框切换到手动模式

### FR-004: 手动覆盖支持

- 用户可勾选"手动设置 Buffer"切换到手动模式
- 手动模式下 Buffer SpinBox 可编辑
- 手动模式下不随 duration/categories 变化
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
    buffer_safety_factor: float = 1.05
    # ... 其余字段不变
```

## 计算公式

```
base_rate_kb_per_sec = 1400  # sched 基线速率 (KB/s)
per_category_rate = 270      # 每个 category 额外速率 (KB/s)

estimated_rate = base_rate_kb_per_sec + category_count × per_category_rate
buffer_size_kb = duration_sec × estimated_rate × safety_factor

buffer_size_kb = clamp(buffer_size_kb, 8192, 524288)
```

**实测校准数据**（设备 HA2DL5M3，游戏运行中，10 秒抓取）：

| 配置 | 大小 (MB) | 总速率 (KB/s) | 每 category (KB/s) |
|------|-----------|--------------|---------------------|
| 1 cat (sched) | 13.21 | 1,353 | 1,353 |
| 3 cats | 13.29 | 1,361 | 454 |
| 7 cats | 13.54 | 1,386 | 198 |
| 19 cats | 60.50 | 6,195 | 326 |

**参数选择依据**：
- `base_rate = 1400`：sched 实测 1,353，向上取整
- `per_category_rate = 270`：(6195-1353)/(19-1) ≈ 269，取 270
- `safety_factor = 1.05`：在已用实测速率拟合的前提下，仅增加约 5% 余量以覆盖短时突发波动（默认值；用户可在配置中调高）

示例：7 categories × 15 秒 × 安全系数 1.05  
→ (1400 + 7×270) × 15 × 1.05 = 51,817.5 KB ≈ 50.6 MB

## 验收标准

| ID | 验收标准 | 通过条件 |
|----|---------|---------|
| AC-01 | 默认模式下 buffer 随 duration 自动更新 | 修改 duration，buffer 值实时变化 |
| AC-02 | 默认模式下 buffer 随 categories 数量更新 | 增减 categories，buffer 值实时变化 |
| AC-03 | 自动计算值在合理范围 | 15s/7cat/默认安全系数 → 约 48–52MB 量级 |
| AC-04 | 上下限生效 | 极短时长不低于 8MB，极长时长不超过 512MB |
| AC-05 | 手动模式可覆盖 | 勾选手动后 buffer 可自由编辑 |
| AC-06 | 配置持久化 | 手动模式和值保存到用户配置，重启恢复 |
| AC-07 | 进程名不丢失 | 高负载场景下抓取的 trace 仍有完整进程名 |
