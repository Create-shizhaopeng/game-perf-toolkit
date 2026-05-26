# Service API Contract: LLMManagerService

**Module**: `modules/llm_manager`
**Service Name**: `llm_manager_service`
**Registration**: `ServiceRegistry.register("llm_manager_service", service_instance)`

## Public Methods

### `load_providers() -> LLMProvidersConfig`

从 `data/config/llm_providers.json` 加载完整 Provider 配置。首次调用时若文件不存在，自动执行迁移（从 `toolkit_config.json` 提取旧 API Key 并生成默认配置）。

**Returns**: 已验证的 `LLMProvidersConfig` 实例

**Raises**: `LLMConfigError` — JSON 格式错误或验证失败，内置默认配置作为回退

---

### `save_providers(config: LLMProvidersConfig) -> None`

将 Provider 配置写入 `data/config/llm_providers.json`。执行 Pydantic 验证后原子写入（先写临时文件再替换）。

**Raises**: `LLMConfigError` — 验证失败

---

### `get_active_provider_config() -> tuple[ProviderConfig, ModelConfig]`

返回当前选中 Provider 及其默认模型的配置元组。供 `LLMManager` 初始化 `LiteLLMProvider` 使用。

**Returns**: `(provider_config, model_config)`

**Raises**: `LLMConfigError` — 无 active provider 或 active provider 的 default_model 无效

---

### `get_provider(id: str) -> ProviderConfig | None`

按 ID 查找 Provider。

---

### `add_provider(provider: ProviderConfig) -> None`

添加新 Provider 并保存。若 ID 已存在则覆盖（输出 warning）。

---

### `remove_provider(id: str) -> None`

删除 Provider。若删除的是 active_provider，自动切换为第一个可用 Provider。

---

### `update_provider(provider: ProviderConfig) -> None`

更新已有 Provider 的全部字段并保存。若 ID 不存在则与 `add_provider` 行为一致。

---

### `list_providers(enabled_only: bool = True) -> list[ProviderConfig]`

返回 Provider 列表（供 GUI 下拉框使用）。

---

### `set_active_provider(id: str) -> None`

切换当前选中 Provider。保存到 `active_provider` 字段。

**Emits**: `EventBus.emit("llm.provider_changed", provider_id=id)`

---

### `get_active_model() -> ModelConfig`

返回当前 active provider 的默认模型。

---

### `set_active_model(model_name: str) -> None`

更改当前 Provider 的默认模型。

---

## TokenTracker API

### `record(request_id: str, provider: str, model: str, prompt_tokens: int, completion_tokens: int, conversation_id: str | None = None, trace_id: str | None = None) -> None`

记录一次 LLM 请求的 Token 用量。

---

### `get_usage_by_conversation(conversation_id: str) -> dict`

```python
{"prompt_tokens": int, "completion_tokens": int, "total_tokens": int, "request_count": int}
```

---

### `get_usage_by_trace(trace_id: str) -> dict`

同上结构。

---

### `get_total_usage(provider: str | None = None) -> dict`

```python
{"prompt_tokens": int, "completion_tokens": int, "total_tokens": int, "request_count": int}
```

若指定 provider 则仅统计该 Provider。

## EventBus Events

| Event | Payload | When |
|-------|---------|------|
| `llm.provider_changed` | `{"provider_id": str}` | Provider 切换 |
| `llm.provider_added` | `{"provider_id": str}` | 新增 Provider |
| `llm.provider_removed` | `{"provider_id": str}` | 删除 Provider |

## Error Handling

```python
class LLMConfigError(Exception):
    """LLM 配置异常基类"""
    pass

class LLMConfigValidationError(LLMConfigError):
    """Pydantic 验证失败"""
    pass

class LLMConfigNotFoundError(LLMConfigError):
    """配置文件不存在且无法重建"""
    pass
```
