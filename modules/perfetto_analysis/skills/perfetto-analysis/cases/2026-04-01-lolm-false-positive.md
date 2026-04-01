# 2026-04-01 lolm 游戏 jank 误检分析

## 目录

- [基本信息](#基本信息)
- [分析路径](#分析路径)
- [根因](#根因)
- [修复](#修复)
- [验证](#验证)

## 基本信息

| 项目 | 值 |
|------|------|
| Trace | TB522FU_SM8750P_20260401_140747.perfetto-trace |
| 设备 | SM8750P |
| 应用 | com.tencent.lolm |
| 刷新率 | 60Hz |
| 帧数 | 889 |
| 状态 | ✅ 用户确认 |

## 分析路径

1. `pa_trace_overview` → 889 帧, 60Hz, game 类型
2. MCP `detect_jank_frames` → 0 次丢帧（无 FrameTimeline 数据）
3. MCP `cpu_utilization_profiler` → CPU 数据正常
4. `pa_detect_jank`（引擎）→ 5 次丢帧
5. 人工 Perfetto UI 确认 → 无实际卡顿
6. 分析引擎 parser.py 的 jank 判定逻辑 → 定位三个问题

## 根因

| 问题 | 说明 |
|------|------|
| jank_1 阈值过严 | App Deadline Missed 判定 `> 1× VSync`（16.67ms），17ms 正常帧被误报 |
| jank_3 窗口不合理 | SF Composition Missed 使用固定 1ms 窗口，与刷新率无关 |
| 首周期无守卫 | trace 第一个 VSync 周期 buffer 状态未稳态，jank_3 触发初始化伪影 |

## 修复

文件：`modules/perfetto_analysis/src/engine/parser.py`

| 修改项 | 之前 | 之后 |
|--------|------|------|
| jank_1 阈值 | `> stand_ms` (1×) | `> stand_ms * 1.5` |
| jank_3 窗口 | `pre_vt + 1_000_000` (1ms) | `pre_vt + int(stand_ms * 0.5 * 1e6)` |
| 首周期 | 无守卫 | `skip_jank = prev_cycle_ns == 0` |

## 验证

| Trace | 修复前 | 修复后 | 人工判定 |
|-------|--------|--------|----------|
| lolm 游戏（60Hz） | 5 次 | 0 次 | 0 次 ✅ |
| Launcher 慢划（120Hz） | 5 次 | 3 次 | 有丢帧 ✅ |
| 单元测试 | 73 pass | 73 pass | ✅ |

踩坑经验已记录：P26（doc/experience/development-pitfalls.md）
