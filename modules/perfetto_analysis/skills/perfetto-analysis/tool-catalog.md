# Perfetto 分析模块 — Agent 工具目录

## pa_execute_sql

执行 PerfettoSQL 查询的唯一 Agent 工具。

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | 是 | Perfetto trace 文件路径（.perfetto-trace） |
| sql | string | 是 | PerfettoSQL 查询语句 |

### 返回结构

```json
{
  "success": true,
  "rows": [
    {"column_name_1": "value_1", "column_name_2": "value_2"},
    ...
  ],
  "row_count": 10,
  "error": null
}
```

失败时：
```json
{
  "success": false,
  "rows": [],
  "row_count": 0,
  "error": "错误信息"
}
```

### 变量替换规则

SQL 中的 `${variable}` 必须在调用前替换为实际值：

| 语法 | 含义 | 示例 |
|------|------|------|
| `${var}` | 必填参数 | `${package}` → `com.game.xxx` |
| `${var\|default}` | 带默认值 | `${top_k\|15}` → 未提供时用 15 |
| `${var\|NULL}` | 可选，替换为 NULL | `${start_ts\|NULL}` → 未提供时 SQL 中为 NULL |

### SQL 来源

所有 SQL 来自 YAML 技能文件的 `steps[].sql` 字段：
- 原子技能：`atomic/*.skill.yaml` — 单一 SQL
- 组合技能：`composite/*.skill.yaml` — 多步 SQL，步骤间通过 `save_as` 传递数据
- SQL 片段：`fragments/*.sql` — 共享 CTE，需拼接到 SQL 的 WITH 子句

### MCP 暴露

此工具通过 MCP Server（stdio/sse 模式）暴露，名称为 `pa_execute_sql`。
