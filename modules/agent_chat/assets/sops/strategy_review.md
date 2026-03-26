---
title: 策略审查
keywords: [策略, 配置, gameperfconfig, CPU, GPU, 频率, 温控]
description: 审查 gameperfconfig.xml 中的性能策略配置，分析合理性并给出调整建议
recommended_provider: glm
required_tools: [gp_analyze_config]
---

# 策略审查工作流

## 步骤

### Step 1: 收集配置文件

询问用户提供 `gameperfconfig.xml` 文件路径。
也可以通过设备拉取获得。

### Step 2: 解析配置

调用 `gp_analyze_config` 解析 XML 配置文件，获取：
- CPU 集群频点配置
- GPU 频点配置
- 支持的游戏列表
- 各场景的策略参数

### Step 3: 展示策略概览

以结构化方式展示当前配置：
- 各 CPU 集群（小核/中核/大核）的可用频点
- GPU 可用频点
- 针对各游戏、各模式、各温控等级的频率限制

### Step 4: 分析合理性

评估策略配置的合理性：
- 频率限制是否过于激进（可能导致卡顿）
- 频率限制是否过于宽松（可能导致发热/功耗过高）
- 温控策略梯度是否合理
- 不同游戏/模式间的策略差异是否合理

### Step 5: 给出调整建议

提供具体的策略优化建议：
- 需要调整的具体频率参数
- 温控策略优化方向
- 与实际性能数据的对比分析（如有 trace/PerfDog 数据）
