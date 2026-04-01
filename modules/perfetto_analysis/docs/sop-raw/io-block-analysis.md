# IO Block 问题分析

> 来源: https://thundersoft.feishu.cn/docx/NeN9dKK5woMMcZxgXvrct02QnOc
> 转写时间: 2026-04-01
> 状态: 原始文档（未加工）
> 分类建议: SOP → sop/io-block-analysis.md

## 目录

- [概述](#概述)
- [抓取日志](#抓取日志)
  - [本地抓取配置](#本地抓取配置)
  - [转换格式](#转换格式)
- [日志分析](#日志分析)
- [获取 IO block 读取的文件](#获取-io-block-读取的文件)
- [判断当前阶段是否存在其他线程在大量 IO 操作](#判断当前阶段是否存在其他线程在大量-io-操作)
- [IO block 是否是由高负载引起](#io-block-是否是由高负载引起)

## 概述

目前遇到的 IO block 问题，通常的做法是把读取的一些系统文件加到 pinner 里面，所载内存的 mLock 中，防止因内存不足被回收掉。

本篇提供：
1. 获取 IO 具体读取文件的方法
2. 判断当前 IO 是高负载引起还是其他线程同时 IO 操作导致的分析方法

## 抓取日志

### 本地抓取配置

通过 `config.pbtx` 配置抓取 IO 相关的 ftrace events：

```
ftrace_events: "sched/sched_switch"
ftrace_events: "power/suspend_resume"
ftrace_events: "sched/sched_process_exit"
ftrace_events: "sched/sched_process_free"
ftrace_events: "task/task_newtask"
ftrace_events: "task/task_rename"
ftrace_events: "f2fs/f2fs_sync_file_enter"
ftrace_events: "f2fs/f2fs_sync_file_exit"
ftrace_events: "f2fs/f2fs_write_begin"
ftrace_events: "f2fs/f2fs_write_end"
ftrace_events: "f2fs/f2fs_readpage"
ftrace_events: "f2fs/f2fs_readpages"
ftrace_events: "f2fs/f2fs_sync_fs"
ftrace_events: "block/block_rq_issue"
ftrace_events: "block/block_rq_complete"
```

> 注意：需要同时抓取 f2fs 和 block 层的事件，才能完整定位 IO 问题。

### 转换格式

抓取 perfetto 后需要转化为 `trace.systrace` 格式，以便使用文本搜索定位 IO 相关事件。

## 日志分析

在 trace 中定位 IO block：查看目标进程/线程的状态泳道，D-State（Uninterruptible Sleep IO）即为 IO block 阶段。选中 D-State 区域可查看持续时长和关联信息。

示例：camera 冷启动阶段出现 IO block。

## 获取 IO block 读取的文件

1. **获取线程号**：从 systrace 上确认 IO block 线程的 tid（如 3153）

2. **搜索 readpages 事件**：在 `trace.systrace` 文件中搜索 `<tid>.*erofs_readpages`（如 `3153.*erofs_readpages`），找到对应的文件读取事件

3. **获取 inode id**：关注搜索结果中的 `nid`（inode id）字段

4. **映射文件名**：获取系统文件的 inode 映射表（需 root）：
```bash
adb root
adb shell
find /system /vendor /product /data -exec stat -c '%d %i %s %n' {} \; > /sdcard/inode.txt
adb pull /sdcard/inode.txt
```

   生成的 `inode.txt` 包含指定分区所有文件的 inode id 和文件大小。可按需增加其他分区（如 system_ext）。

5. **匹配文件**：用 nid 在 `inode.txt` 中搜索，确认具体读取的文件

6. **对比分析**：
   - 比较测试机和对比机读取的文件是否一致
   - 比较文件大小是否一致（文件越大，IO 量越大）
   - 文件大小在 `inode.txt` 的第三列

## 判断当前阶段是否存在其他线程在大量 IO 操作

1. **确定关注的时间窗口**：在 systrace 上选取 IO block 区域，记录起止时间

2. **计算 trace 绝对时间**：
   - trace 开始时间（如 65618.211499）
   - IO block 开始的相对时间（如 1s 758ms 21us 807ns）
   - 计算绝对时间窗口（如 65619.969 - 65620.612）

3. **搜索 block_rq_insert**：在 `trace.systrace` 中搜索 `block_rq_insert` 关键字

4. **筛选时间窗口**：在关注时间窗口内的 `block_rq_insert` 条目

5. **对比分析**：
   - 将测试机和对比机在同一阶段的 IO 请求进行对比
   - 关注 `bytes` 值衡量 IO 量
   - 确认是否有异常线程在大量发起 IO

## IO block 是否是由高负载引起

追踪 Uninterruptible Sleep (IO) 的唤醒关系，检查唤醒线程是否存在长时间 Runnable 状态（CPU 排队）：

- 如果 waker 线程在长时间 Runnable → CPU 负载高，IO 完成信号延迟送达
- 如果 waker 线程正常 Running → IO 硬件/驱动层面慢
