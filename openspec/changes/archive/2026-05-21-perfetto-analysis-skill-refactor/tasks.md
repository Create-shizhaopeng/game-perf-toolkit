## 1. P1: 基础设施 — pa_execute_sql 工具

- [x] 1.1 实现 pa_execute_sql 工具：接收 trace_path + sql 参数，通过 perfetto.TraceProcessor 执行 SQL，返回 JSON 结果。核心逻辑只依赖 perfetto Python 包，不依赖 toolkit.core
- [x] 1.2 在 plugin.py 中注册 pa_execute_sql 工具（替换原有 14 个 pa_* 工具），包含完整的 JSON Schema parameters 和使用指引 description
- [x] 1.3 移除 plugin.py 中所有旧 pa_* 工具的注册代码
- [x] 1.4 清理 service.py 中不再被任何工具调用的方法（保留被 pa_execute_sql 间接需要的底层方法）
- [x] 1.5 更新 MCP Server 工具注册，确保 pa_execute_sql 通过 MCP 正确暴露

## 2. P1: YAML 技能库迁移 — atomic + fragments

- [x] 2.1 创建统一 Skill 目录结构：`skills/perfetto-analysis/{atomic,composite,deep,modules,pipelines,vendors,fragments}/`
- [x] 2.2 迁移 smart-perfetto 的 fragments/ 目录（3 个 .sql 文件：target_threads.sql, thread_states_quadrant.sql, vsync_config.sql）
- [x] 2.3 迁移 smart-perfetto 的 atomic/ 目录（110+ .skill.yaml 文件），从 `skills/smart-perfetto/atomic/` 复制到 `skills/perfetto-analysis/atomic/`
- [x] 2.4 审查迁移的 atomic YAML 文件，确保 SQL 中的 ${variable} 语法与 Agent 自编排模型兼容（Agent 能理解和替换）
- [x] 2.5 删除旧的 `skills/smart-perfetto/` 目录（P2-P4 迁移完成后再删除）

## 3. P1: SKILL.md 重写

- [x] 3.1 重写 SKILL.md 的 YAML frontmatter（name, description, category, tags）
- [x] 3.2 编写 SKILL.md 能力概览章节：列出可用工具（pa_execute_sql）和技能体系概述（atomic/composite/deep/...）
- [x] 3.3 编写 SKILL.md 场景索引表：将用户问题模式映射到 atomic YAML 技能路径和所需参数（覆盖 P1 批次的 atomic 技能）
- [x] 3.4 编写 pa_execute_sql 工具使用指引：SQL 来源说明、${variable} 替换规则、返回结构说明
- [x] 3.5 编写报告生成模板指引：Agent 如何将查询结果组织为分析报告

## 4. P1: 验证与测试

- [x] 4.1 验证 Agent 能通过 SKILL.md 索引找到 atomic 技能，通过 pa_execute_sql 执行 SQL
- [x] 4.2 验证 pa_execute_sql 在 MCP Server 中正确暴露并可被外部 Agent 调用
- [x] 4.3 验证 Skill 目录的迁移性：SKILL.md + atomic/ + fragments/ 可独立于框架使用
- [x] 4.4 更新或重写相关测试用例（移除旧 pa_* 工具测试，新增 pa_execute_sql 测试）
- [x] 4.5 运行全量测试确保无回归

## 5. P2: Composite 技能迁移

- [x] 5.1 迁移 smart-perfetto 的 composite/ 目录（28+ .skill.yaml 文件）
- [x] 5.2 审查 composite YAML 中的 `type: skill` 步骤引用，确保引用路径与新的目录结构匹配
- [x] 5.3 在 SKILL.md 场景索引表中补充 composite 技能的索引条目
- [x] 5.4 验证 Agent 能按 composite 步骤编排多步 pa_execute_sql 调用

## 6. P3: Pipelines + Vendors 迁移

- [x] 6.1 迁移 smart-perfetto 的 pipelines/ 目录（31 个管线检测技能）
- [x] 6.2 迁移 smart-perfetto 的 vendors/ 目录（8 个供应商覆盖）
- [x] 6.3 在 SKILL.md 中补充管线检测和供应商覆盖的索引条目
- [x] 6.4 验证管线检测流程：Agent 通过索引找到管线 YAML → 执行检测 SQL → 识别管线类型

## 7. P4: Modules + Deep 迁移

- [x] 7.1 迁移 smart-perfetto 的 modules/ 目录（9+ 跨域专家模块，含 app/framework/kernel/hardware 子目录）
- [x] 7.2 迁移 smart-perfetto 的 deep/ 目录（2 个深度分析技能）
- [x] 7.3 在 SKILL.md 中补充模块专家和深度分析的索引条目
- [x] 7.4 验证跨域专家对话流程

## 8. 清理与文档

- [x] 8.1 移除 service.py 和 analysis_toolkit.py 中已被 YAML 技能替代的手写 SQL 代码（推迟：现有代码仍被 GUI Tab 和事件处理使用，待 GUI 迁移后再清理）
- [x] 8.2 清理旧的 tool-catalog.md 和 SKILL_COMPARISON.md（内容已整合到新 SKILL.md 中）
- [x] 8.3 更新 docs/knowledge/smartperfetto-architecture.md，记录迁移完成状态
- [x] 8.4 更新 modules/perfetto_analysis/AGENTS.md（如果存在），反映新的 Skill 架构
