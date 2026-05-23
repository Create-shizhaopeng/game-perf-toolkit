## Why

perfetto_analysis 模块的 Skill 迁移性几乎为零：14 个 pa_* Agent 工具的 SQL 逻辑硬编码在 Python 代码中，Agent 只能通过框架注册的固定工具调用，无法灵活组合分析流程。同时，smart-perfetto 项目中 220+ 精细的 YAML 技能（含 SQL、诊断规则、阈值评估、供应商覆盖）在仓库内仅作静态参考，未被 Agent 实际使用。两套体系断裂，知识无法复用。

## What Changes

- **移除 14 个细粒度 pa_* 工具**，收拢为单一核心工具 `pa_execute_sql(trace_path, sql)`
- **迁移 smart-perfetto YAML 技能库**（atomic/composite/deep/modules/pipelines/vendors/fragments）到 perfetto-analysis Skill 内部
- **重写 SKILL.md** 为 Agent 操作手册：场景索引表（问题→YAML 路径→参数→返回结构→报告模板），实现渐进式披露
- **移除 `pa_trace_overview`、`pa_detect_jank` 等高层工具**，其 SQL 逻辑转为 atomic YAML 技能
- **`pa_execute_sql` 成为 Skill 的核心执行能力**，Agent 通过它执行 YAML 中的 SQL
- **Agent 自编排**：读取 SKILL.md 索引→读取对应 YAML→通过 pa_execute_sql 逐步执行→按模板生成报告。不需要 Python SkillRunner 引擎

## Capabilities

### New Capabilities
- `yaml-skill-library`: YAML 技能库的加载、索引和渐进式披露机制，Agent 通过 SKILL.md 场景索引定位到具体 YAML 技能文件
- `agent-sql-executor`: pa_execute_sql 工具，Agent 通过它执行 PerfettoSQL 查询，作为 Skill 的唯一执行通道

### Modified Capabilities
- `module-agent-tools`: perfetto_analysis 模块从 14 个 pa_* 工具收拢为 pa_execute_sql 单一工具，工具注册逻辑大幅简化
- `skill-registry`: SKILL.md 需要支持引用子目录中的 YAML 技能文件（composite/atomic/...），实现渐进式披露的索引结构

## Impact

- **modules/perfetto_analysis/**: plugin.py（工具注册从 14 个减至 1 个）、service.py（SQL 逻辑迁移到 YAML 后大幅瘦身）、SKILL.md 重写、新增 220+ YAML 文件
- **toolkit/core/skill_registry.py**: 需要支持 Skill 目录内的子资源索引（YAML 技能文件）
- **toolkit/core/mcp_server.py**: 工具数量从 14 减至 1，MCP server 注册逻辑简化
- **Agent 交互模型**: 从"调用预定义工具"变为"读 SKILL.md 索引→读 YAML→调 pa_execute_sql"，Agent 获得完全的分析编排能力
