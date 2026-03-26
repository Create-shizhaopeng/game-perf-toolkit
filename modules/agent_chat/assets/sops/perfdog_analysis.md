---
title: PerfDog 分析
keywords: [perfdog, fps, jank, 内存, 功耗, 性能]
description: 分析 PerfDog 导出的性能数据，评估 FPS、内存、功耗等关键指标
recommended_provider: glm
required_tools: [pdi_load_report, pdi_summarize]
---

# PerfDog 分析工作流

## 步骤

### Step 1: 收集数据文件

询问用户提供 PerfDog 导出的 Excel 文件路径（`.xlsx` 格式）。

### Step 2: 加载报告

调用 `pdi_load_report` 加载并解析 PerfDog 数据。

### Step 3: 汇总分析

调用 `pdi_summarize` 获取关键性能指标摘要：
- FPS 统计（均值/最小值/最大值/P1）
- Jank 率
- 内存峰值
- 功耗均值

### Step 4: 解读关键指标

基于汇总数据分析性能表现：
- FPS 稳定性评估
- Jank 频率和严重程度
- 内存使用趋势
- 功耗水平判断

### Step 5: 给出优化建议

根据分析结果提供：
- 性能瓶颈定位
- FPS 提升建议
- 内存优化方向
- 功耗控制策略
