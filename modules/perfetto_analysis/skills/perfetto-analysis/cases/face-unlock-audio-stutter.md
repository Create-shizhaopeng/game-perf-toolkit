# 2026-04-01 人脸解锁音频卡顿

## 目录

- [基本信息](#基本信息)
- [分析路径](#分析路径)
- [根因](#根因)
- [验证](#验证)
- [关联模式](#关联模式)

## 基本信息

| 项目 | 值 |
|------|------|
| 来源 | 团队经验文档 |
| 应用 | mediaserver（音频解码） |
| 场景 | 人脸解锁亮屏过程 |
| 状态 | ✅ 用户确认 |

## 分析路径

1. 在 mediaserver 进程中定位 `NPDecoder_CL` 线程，发现灭屏到亮屏过程中出现 ~250ms sleeping
2. 选中 sleeping 区域，底部面板显示 `running instead: SysUIBg`（com.android.systemui, pid 1433）
3. 三份独立 trace 中均存在 NPDecoder 线程 sleeping，持续时长一致（~250ms）
4. 确认 SysUIBg 在解锁流程中占用 CPU 核心，导致 NPDecoder 被调度抢占

关键线程：
- `NPDecoder_CL`（mediaserver）— 音频解码
- `SysUIBg`（systemui）— 系统 UI 后台任务
- `AudioOut_0:*`（mediaserver）— 音频输出

## 根因

| 问题 | 说明 |
|------|------|
| CPU 调度抢占 | NPDecoder 线程被调度到与 SysUIBg 同一 CPU 核，解锁流程中 SysUIBg 高优先级任务抢占 NPDecoder |
| 影响 | 音频解码中断 ~250ms，导致来电铃声卡顿 |

## 验证

- 多份 trace 复现一致
- sleeping 区域的 waker 信息均指向 SysUIBg

## 关联模式

→ [CPU 调度抢占](../patterns/root-cause-patterns.md#cpu-调度抢占)
