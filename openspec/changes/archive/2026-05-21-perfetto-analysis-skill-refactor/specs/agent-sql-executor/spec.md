## ADDED Requirements

### Requirement: pa_execute_sql 工具定义

perfetto_analysis 模块 SHALL 注册一个名为 `pa_execute_sql` 的 Agent 工具，作为 Skill 的唯一执行通道。

工具参数：
- `trace_path` (string, required): Perfetto trace 文件路径
- `sql` (string, required): PerfettoSQL 查询语句

工具返回：
- 查询结果的 JSON 序列化（行数据列表）
- 执行状态（成功/失败）
- 错误信息（如查询失败）

#### Scenario: Agent 通过 pa_execute_sql 执行查询

- **WHEN** Agent 从 YAML 技能文件中读取到 SQL 查询
- **THEN** Agent 调用 `pa_execute_sql(trace_path="/path/to/trace", sql="SELECT ...")` 执行查询
- **AND** 工具返回查询结果列表

#### Scenario: SQL 执行失败

- **WHEN** Agent 调用 pa_execute_sql 但 SQL 语法错误或 trace 文件不存在
- **THEN** 工具返回错误状态和错误信息，Agent 可据此调整 SQL 或选择其他技能

### Requirement: pa_execute_sql 支持 ${variable} 替换

pa_execute_sql 的 SQL 参数 SHALL 支持 `${variable}` 模板语法，Agent 在调用前将 YAML 技能中的 `${variable}` 替换为实际参数值。

#### Scenario: Agent 替换模板变量后执行

- **WHEN** YAML 技能中的 SQL 包含 `${package}` 占位符
- **THEN** Agent 将 `${package}` 替换为实际包名（如 `com.game.xxx`），然后调用 pa_execute_sql 执行替换后的 SQL

### Requirement: pa_execute_sql 独立于框架

pa_execute_sql 的核心逻辑 SHALL 只依赖 `perfetto` Python 包，不依赖 `toolkit.core` 中的任何模块（app_paths、db_manager 等），确保 Skill 可迁移。

#### Scenario: Skill 脱离框架独立运行

- **WHEN** perfetto-analysis Skill 被迁移到其他项目
- **THEN** pa_execute_sql 只需 `perfetto` Python 包即可工作，无需 lv-game-toolkit 框架

### Requirement: pa_execute_sql 工具描述

pa_execute_sql 的工具描述 SHALL 包含使用指引，告知 Agent：
1. 这是执行 PerfettoSQL 的唯一工具
2. SQL 来源是 YAML 技能文件中的 `steps[].sql` 字段
3. 需要先将 `${variable}` 替换为实际值
4. 返回结果的结构说明

#### Scenario: Agent 读取工具描述理解用法

- **WHEN** Agent 查看 pa_execute_sql 的工具描述
- **THEN** 描述中包含上述 4 点使用指引，Agent 知道如何正确使用该工具
