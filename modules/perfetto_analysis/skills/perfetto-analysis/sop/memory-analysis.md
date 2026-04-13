---
scene: memory
display_name: 内存分析
priority_dims: [gc]
secondary_dims: [cpu, thread]
optional_dims: [io]
prefetch:
  - tool: trace_overview
    inject_as: trace_info
---

# 内存分析 SOP

## 目录

- [分析目标](#分析目标)
- [前置检查](#前置检查)
- [分析流程](#分析流程)
- [结果解读](#结果解读)

## 分析目标

检测 Perfetto trace 中的内存泄漏，分析堆内存分布，识别内存增长的根因。

## 前置检查

1. 调用 `pa_trace_overview` 确认 trace 包含目标进程
2. 确认 trace 中包含 heap graph 数据（否则内存分析不可用）
3. 确认用户关注的是内存问题

## 分析流程

1. 调用 `pa_analyze_memory` 执行内存泄漏检测和堆分析
2. 如果检测到泄漏：
   - 查看 `memory_leaks` 中的泄漏对象列表
   - 查看 `heap_dominator` 中的内存支配树
   - 可补充调用 `pa_execute_sql` 查询具体的 heap_graph 表
3. 如果未检测到泄漏：
   - 告知用户未发现明显内存泄漏
   - 可能需要更长时间的 trace 来捕获泄漏模式

## 结果解读

- `memory_leaks` 为 null 表示 trace 不包含 heap graph 数据
- `heap_dominator` 展示内存占用最大的对象及其引用链
- 关注 retained size 最大的对象，它们是优化内存的首要目标

## 深入分析资源

分析过程中需要深入了解时，调用 `pa_read_knowledge` 获取知识资产:
- SQL 查询模板: `pa_read_knowledge("sql-patterns.md")`
