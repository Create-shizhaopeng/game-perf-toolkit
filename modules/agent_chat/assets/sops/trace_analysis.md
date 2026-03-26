---
title: Trace 分析
keywords: [trace, 丢帧, perfetto, 卡顿, jank, 帧率]
description: 使用 Perfetto trace 文件进行丢帧检测和归因分析
recommended_provider: glm
required_tools: [pa_analyze]
---

# Trace 分析工作流

## 步骤

### Step 1: 收集 trace 文件

询问用户提供 Perfetto trace 文件路径（`.perfetto-trace` 格式）。
如果用户拖放文件，自动识别路径。

### Step 2: 确认分析参数

- 目标进程名（留空则自动检测）
- 确认是否需要全维度分析

### Step 3: 执行分析

调用 `pa_analyze` 工具执行完整分析：
- Phase 1：丢帧定位（检测大于一个 vsync 周期的帧）
- Phase 2：多维度归因分析（CPU 频率、Binder、调度延迟等）
- 自动导出 Markdown 报告

### Step 4: 解读结果

从分析结果中提取关键信息：
- 丢帧总数和丢帧率
- 各维度的主要问题
- 最严重的性能瓶颈

### Step 5: 给出结论和建议

基于分析结果，给出：
- 性能状况总体评估
- 主要卡顿原因分析
- 具体的优化建议
- 需要进一步排查的方向
