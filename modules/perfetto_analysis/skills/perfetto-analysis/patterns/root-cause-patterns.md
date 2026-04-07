# 根因模式库

## 目录

- [使用说明](#使用说明)
- [帧卡顿根因](#帧卡顿根因)
  - [VSync 检测全误报](#vsync-检测全误报)
  - [IO Block — 文件未 pin 到内存](#io-block--文件未-pin-到内存)
  - [IO Block — IO 竞争](#io-block--io-竞争)
- [SurfaceFlinger 根因](#surfaceflinger-根因)
  - [HWC Binder 超时](#hwc-binder-超时)
- [CPU 调度根因](#cpu-调度根因)
  - [CPU 调度抢占](#cpu-调度抢占)
- [模式模板](#模式模板)

## 使用说明

本文档记录经过验证的 **症状→根因** 映射模式。Agent 在分析过程中可按需查阅，快速定位已知问题模式。

每个模式包含：症状描述、根因、验证方法、推荐工具链、来源案例。

**新增模式标准**：
- 必须经过至少一次真实 trace 验证
- 必须标注来源案例
- 用户确认后方可录入

---

## 帧卡顿根因

### VSync 检测全误报

- **症状**: 引擎 `pa_detect_jank` 报告多次 jank，但 MCP `detect_jank_frames` 和人工确认均为 0
- **根因**: 引擎 jank_1 阈值过严（1× VSync）或首周期初始化伪影
- **验证**: 人工在 Perfetto UI 比对帧间隔，确认帧实际呈现时间
- **工具链**: `pa_detect_jank` → MCP `detect_jank_frames` → `pa_execute_sql` 比对
- **修复**: 阈值改为 1.5× VSync，首周期跳过判定（P26）
- **来源**: 案例 2026-04-01-lolm-false-positive

### IO Block — 文件未 pin 到内存

- **症状**: 线程进入 D-State（Uninterruptible Sleep IO），持续数毫秒至数十毫秒
- **根因**: 系统文件被内存回收后需从磁盘重新读取，未加入 pinner 白名单的 `mlock`
- **验证**: 通过 inode 映射确认读取的具体文件，对比 pinner 白名单
- **工具链**: `pa_analyze_dimension(io)` → `pa_execute_sql`(D-State 查询) → 设备侧 inode 映射
- **来源**: 团队 SOP — IO Block 问题分析

### IO Block — IO 竞争

- **症状**: 目标线程 D-State 期间，同一时间窗口内多个线程均有大量 D-State
- **根因**: 多线程并发 IO 导致块设备排队，相互阻塞
- **验证**: 统计时间窗口内各线程 D-State 总时长和 `block_rq_insert` 请求量
- **工具链**: `pa_execute_sql`(D-State 统计 + block_rq_insert 量化)
- **来源**: 团队 SOP — IO Block 问题分析

---

## SurfaceFlinger 根因

### HWC Binder 超时

- **症状**: SF 维度显示合成超时，`handleMessageRefresh` 耗时异常
- **根因**: SF 通过 binder 调用 HWC（`HIDL::IComposerClient::executeCommands`）时，HWC 侧处理耗时超过预算（如 `HWCSession::PresentDisplay`、`DRMAtomicReq::Commit`）
- **验证**: 检查 SF 主线程的 `handleMessageRefresh` 中嵌套的 HWC binder 调用耗时；检查 HWC 服务进程（`vendor.qti.hardware.display.composer-service`）中 `HwBinder` 线程的 slice 耗时
- **工具链**: `pa_analyze_dimension(sf)` → `pa_execute_sql`(SF slice 查询) → `pa_execute_sql`(HWC binder 查询)
- **来源**: 团队案例 — SurfaceFlinger 耗时分析

---

## CPU 调度根因

### CPU 调度抢占

- **症状**: 目标线程进入 sleeping/blocked，底部面板显示 `running instead` 指向另一线程
- **根因**: 目标线程与高优先级线程调度到同一 CPU 核，被抢占导致执行中断
- **验证**: 选中 sleeping 区域查看 waker 信息和 `running instead` 线程，确认调度优先级和 CPU 亲和性
- **工具链**: `pa_execute_sql`(thread_state 查询) → 手动 Perfetto UI 查看 `running instead`
- **来源**: 案例 [face-unlock-audio-stutter](../cases/face-unlock-audio-stutter.md)

---

## 模式模板

```markdown
### <模式名称>

- **症状**: <Agent 或用户观察到的现象>
- **根因**: <确认的根本原因>
- **验证**: <如何验证此根因>
- **工具链**: <推荐的工具调用序列>
- **来源**: <案例编号或 trace 信息>
```
