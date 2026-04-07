# 人脸解锁音频卡顿

> 来源: https://thundersoft.feishu.cn/docx/T9Vqd8ObRoFo4Dxfyd2cKn7Pnfh
> 转写时间: 2026-04-01
> 状态: 原始文档（未加工）
> 分类建议: 案例 → cases/

## 问题描述

人脸解锁流程中系统整体负载不高，在 systrace 中可以看到 mediaserver 中 NPDecoder 相关线程在从灭屏到亮屏的过程中有一段 sleeping。在其中一份 systrace 中指明了 running instead：SysUIBg 线程，此线程在 system ui 中，具体作用不清楚，需要找 system ui 相关的同事了解。

三份 systrace 中都存在 NPDecoder 线程陷入 sleeping 状态的情况，持续时长 250ms 左右，推测这个是解锁来电音频卡顿的原因。

## Trace 分析细节

### NPDecoder 线程状态

Trace 中可看到 3 个 `NPDecoder_CL` 线程。其中一个在灭屏到亮屏的过程中出现了一段红色（sleeping）区域，持续约 250ms。

选中该 sleeping 区域后，底部详情面板显示：
- **Running process**: com.android.systemui (pid 1433)
- **Running thread**: SysUIBg
- **Thread State**: D (Uninterruptible Sleep) 或 S (Sleeping)
- **Args**: `{comm: "SysUIBg", tid: 1538, prio: 130, state/AndoScheduled: "W"}`

### 关键线程

在 mediaserver 进程中可看到以下线程受到影响：
- `Screen Main`
- `audio MF`
- `AudioOut_0:767`、`AudioOut_0:170`
- `NPDecoder 2424`

## 根因推测

NPDecoder 线程被调度到与 SysUIBg 同一 CPU 核上，由于 SysUIBg 在解锁流程中的任务导致 NPDecoder 被抢占，造成音频解码中断约 250ms，导致音频卡顿。

## 分析方法提炼

1. 确认问题线程：在 mediaserver 进程中查找音频相关线程（NPDecoder、AudioOut）
2. 选中 sleeping/blocked 区域，查看底部 Thread State 面板中的 waker 信息
3. 确认 `running instead` 指向的线程，追踪该线程所属进程和正在执行的任务
4. 评估调度优先级和 CPU 亲和性是否导致抢占
