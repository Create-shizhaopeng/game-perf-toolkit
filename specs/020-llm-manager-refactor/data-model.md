# Data Model: LLM Manager 模块重构

**Created**: 2026-05-25
**Feature**: [spec.md](spec.md)

## Entity Relationship

```
LLMProvidersConfig (JSON root)
  │
  └── providers: list[ProviderConfig]
        │
        ├── models: list[ModelConfig]
        │
        └── (used by) LLMManager
              │
              └── produces TokenUsageRecord
```

## ProviderConfig

LLM 服务提供方的完整定义。

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `str` | Yes | — | 唯一标识（snake_case），如 `glm`, `claude`, `deepseek` |
| `name` | `str` | Yes | — | 显示名称，如 `"GLM (智谱)"` |
| `base_url` | `str` | No | `""` | 自定义 API 地址，空字符串使用 LiteLLM 默认 |
| `litellm_prefix` | `str` | No | `""` | LiteLLM 模型前缀，如 `"zai/"`, `"openai/"` |
| `api_key` | `str` | No | `""` | API Key（明文存储于本地 JSON） |
| `enabled` | `bool` | No | `True` | 是否在设置面板中显示 |
| `thinking` | `bool` | No | `False` | 是否支持 extended thinking |
| `thinking_budget` | `int` | No | `4000` | Thinking token 预算（min=1024） |
| `models` | `list[ModelConfig]` | Yes | `[]` | 可用模型列表 |
| `default_model` | `str` | No | `""` | 默认模型名（必须存在于 models 中） |

**Validation Rules**:
- `id` MUST be unique across all providers
- `id` MUST match `^[a-z][a-z0-9_]*$`
- `default_model` MUST exist in `models` list
- `thinking_budget` MUST be >= 1024 if `thinking` is True
- `models` MUST NOT be empty if `enabled` is True

## ModelConfig

属于某个 Provider 的模型定义。

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | `str` | Yes | — | 模型名称，如 `"glm-4-plus"`, `"claude-opus-4-7"` |
| `context_window` | `int` | No | `128000` | 上下文窗口 tokens 数 |

**Validation Rules**:
- `name` MUST be unique within the same Provider
- `context_window` MUST be >= 1024

**Display Rules** (GUI 渲染逻辑，非数据约束):
- `context_window >= 1000000` → 标签 `[1M]`
- `context_window >= 200000` → 标签 `[200K]`
- `context_window >= 128000` → 标签 `[128K]`
- `< 128000` → 无标签

## LLMProvidersConfig

JSON 文件根对象。

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `providers` | `list[ProviderConfig]` | Yes | `[]` | Provider 列表 |
| `active_provider` | `str` | No | `""` | 当前选中的 Provider ID |

## TokenUsageRecord

单次 LLM 请求的 Token 用量记录（SQLite 表）。

| Field | Type | Description |
|-------|------|-------------|
| `id` | `INTEGER PK AUTOINCREMENT` | 自增主键 |
| `request_id` | `TEXT NOT NULL` | 请求唯一 ID（UUID4） |
| `conversation_id` | `TEXT` | 对话 ID（由 Agent Chat 传入，可为 NULL） |
| `trace_id` | `TEXT` | Trace 分析任务 ID（由 Agent Chat 传入，可为 NULL） |
| `provider` | `TEXT NOT NULL` | Provider ID |
| `model` | `TEXT NOT NULL` | 模型名称 |
| `prompt_tokens` | `INTEGER NOT NULL DEFAULT 0` | 输入 Token 数 |
| `completion_tokens` | `INTEGER NOT NULL DEFAULT 0` | 输出 Token 数 |
| `timestamp` | `TEXT NOT NULL DEFAULT (datetime('now'))` | 记录时间（ISO 8601） |

**Indexes**:
- `idx_llm_token_conv` ON `conversation_id` — 按对话聚合查询
- `idx_llm_token_trace` ON `trace_id` — 按 trace 聚合查询
- `idx_llm_token_timestamp` ON `timestamp` — 时间范围查询

**Query Examples** (供飞书统计后续使用):
```sql
-- 单次请求
SELECT * FROM llm_token_usage WHERE request_id = ?;

-- 一轮对话用量
SELECT SUM(prompt_tokens + completion_tokens) FROM llm_token_usage WHERE conversation_id = ?;

-- 一次 trace 分析用量
SELECT SUM(prompt_tokens + completion_tokens) FROM llm_token_usage WHERE trace_id = ?;

-- 总用量（按 provider）
SELECT provider, SUM(prompt_tokens + completion_tokens) FROM llm_token_usage GROUP BY provider;
```

## State Transitions

```
Provider 生命周期:

   [创建] ──► enabled: true ──► 在 GUI 下拉列表中可见
    │
    ├──► enabled: false ──► GUI 中隐藏（保留配置）
    │
    └──► [删除] ──► 从 JSON 移除，API Key 不可恢复

Thinking 状态切换:

   thinking: true + Provider selected ──► GUI 显示 Thinking 复选框
   thinking: false + Provider selected ──► GUI 隐藏 Thinking 复选框
   用户勾选/取消 ──► 影响下次 LLM 请求的 thinking 参数

上下文用量:

  新对话 ──► context_used = 0, context_capacity = model.context_window
  LLM 返回 usage ──► context_used += prompt_tokens + completion_tokens
  切换模型 ──► context_used = 0, context_capacity = new_model.context_window
```

## Migration Data Flow

```
旧: toolkit_config.json["llm"]              新: llm_providers.json
  {                                            {
    "provider": "glm",                           "providers": [
    "glm_api_key": "sk-xxx",                       {
    "claude_api_key": "sk-yyy",                      "id": "glm",
    "model_name": "glm-4-plus",                      "api_key": "sk-xxx",
    ...                                              ...
  }                                                 },
                                                     {
                                                       "id": "claude",
                                                       "api_key": "sk-yyy",
                                                       ...
                                                     }
                                                   ],
                                                   "active_provider": "glm"
                                                 }

  迁移完成后:
  toolkit_config.json["llm"]["_migrated_to_llm_providers"] = true
```
