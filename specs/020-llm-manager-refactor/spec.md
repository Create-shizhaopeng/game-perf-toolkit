# Feature Specification: LLM Manager 模块重构 — 多 Provider 配置化 + 精简设置 + Thinking + Token 后台统计 + 上下文用量显示

**Feature Branch**: `020-llm-manager-refactor`

**Created**: 2026-05-25

**Status**: Draft

**Input**: User description: "抽离 LLM 管理为独立子模块，支持多 Provider 自定义 URL 配置、Thinking 特性、Token 多维后台统计，精简设置面板"

## Clarifications

### Session 2026-05-25

- Q: Thinking budget 是否需要在 UI 中暴露？ → A: 不需要。thinking budget 写死在 Provider 配置中（如 `thinking_budget: 4000`），UI 只显示 Thinking 开关，参考 Claude Code 的隐藏设计。
- Q: Token 记录的 conversation_id 由谁管理？ → A: conversation_id 和 trace_id 由调用方（Agent Chat）传入，llm_manager 模块只负责存储，不自行生成或管理这些 ID，保持模块间代码解耦。

## 架构设计图

### 1. 用例图

```
┌──────────────────────────────────────────────────────────────────────┐
│                         LLM Manager 系统                              │
│                                                                      │
│  ┌─────────┐                                                        │
│  │  用户    │                                                        │
│  └────┬────┘                                                        │
│       │                                                              │
│       ├─► 管理 LLM Provider ────┐                                    │
│       │   (增删改 / 启用禁用)    │                                    │
│       │                         ▼                                    │
│       │                  ┌──────────────┐                           │
│       │                  │ llm_providers │                           │
│       │                  │   .json       │                           │
│       │                  └──────────────┘                           │
│       │                                                              │
│       ├─► 配置自定义 API 地址 ──► LiteLLM api_base                    │
│       │                                                              │
│       ├─► 选择模型 ──────────►  Agent Chat 调用 LLM                   │
│       │   (含 [1M] 上下文区分)                                        │
│       │                                                              │
│       ├─► 开启/关闭 Thinking ─► Anthropic extended thinking API       │
│       │                                                              │
│       ├─► 查看上下文用量 ────► 状态栏圆环 + hover tooltip              │
│       │                                                              │
│       └─► Token 后台记录 ────► SQLite (后续飞书统计)                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 2. 模块关系图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              toolkit/ (框架层)                            │
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────────┐                       │
│  │  MainWindow      │    │  TitleBar             │                       │
│  │  _status_bar ◄───┼────┤  SettingsButton       │                       │
│  │  _bottom_panel   │    │  → log submenu (已有)  │                       │
│  └──────┬───────────┘    └──────────────────────┘                       │
│         │                                                                 │
│         │ 读取 llm_status_widget                                           │
│         ▼                                                                 │
│  ┌──────────────────┐    ┌──────────────────────┐                       │
│  │ LLMStatusWidget  │    │  LLMSettingsDialog    │                       │
│  │ (精简: 仅圆环+    │    │  (精简: Provider下拉  │                       │
│  │  模型名, hover    │    │   Model下拉, Thinking  │                       │
│  │  显示tooltip)     │    │   开关, 管理按钮)      │                       │
│  └──────────────────┘    └──────┬───────────────┘                       │
│                                  │ "管理 Provider" 按钮                   │
│                                  ▼                                        │
│  ┌──────────────────┐    ┌──────────────────────┐                       │
│  │  LLMManager      │    │  LiteLLMProvider      │                       │
│  │  (精简: 仅管理    │    │  (接收 api_base +     │                       │
│  │   active provider │    │   thinking 参数)      │                       │
│  │   初始化 provider) │    └──────────────────────┘                       │
│  └────────┬─────────┘                                                    │
│           │ 依赖                                                          │
│           ▼                                                              │
│  ┌──────────────────┐                                                    │
│  │  ConfigManager   │  ← 仍管理 toolkit_config.json 运行时配置            │
│  └──────────────────┘                                                    │
└──────────────────────────────────────────────────────────────────────────┘
           │
           │ ServiceRegistry 注册
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      modules/llm_manager/ (新增模块)                      │
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────────┐                       │
│  │  plugin.py       │    │  service.py            │                       │
│  │  BasePlugin      │    │  LLMManagerService     │                       │
│  │  → register svc  │    │  ├─ load_providers()   │                       │
│  │  → register GUI  │    │  ├─ save_providers()   │                       │
│  │  → register tools│    │  ├─ get_active_config()│                       │
│  └──────────────────┘    │  └─ CRUD providers     │                       │
│                          └──────┬───────────────┬─┘                       │
│                                 │               │                         │
│              ┌──────────────────┘               └──────────────┐          │
│              ▼                                                 ▼          │
│  ┌──────────────────────┐                        ┌──────────────────┐   │
│  │  models.py           │                        │  token_tracker.py │   │
│  │  ProviderConfig      │                        │  TokenTracker     │   │
│  │  ModelConfig         │                        │  ├─ record()      │   │
│  │  LLMProvidersConfig  │                        │  ├─ get_usage()   │   │
│  └──────────────────────┘                        │  └─ SQLite 持久化  │   │
│                                                  └──────────────────┘   │
│  ┌──────────────────────┐                                                 │
│  │  provider_dialog.py  │                                                 │
│  │  ProviderManageDialog│                                                 │
│  │  (Provider CRUD GUI) │                                                 │
│  └──────────────────────┘                                                 │
│                                                                          │
│  ┌──────────────────────┐                                                 │
│  │  strings_gui.py      │  ← 用户可见中文字符串                            │
│  │  strings_service.py  │  ← 服务层字符串                                  │
│  └──────────────────────┘                                                 │
└──────────────────────────────────────────────────────────────────────────┘
           │
           │ 读写
           ▼
┌──────────────────────┐    ┌──────────────────────┐
│  data/config/        │    │  data/db/             │
│  llm_providers.json  │    │  llm_token_usage.db   │
│  (Provider 定义 +     │    │  (Token 用量记录)      │
│   API Key + 模型列表)  │    │                       │
└──────────────────────┘    └──────────────────────┘
           │
           │ 传递 conversation_id
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      modules/agent_chat/ (Agent 模块)                     │
│                                                                          │
│  ┌──────────────────────┐    ┌──────────────────────┐                   │
│  │  service.py          │    │  gui_tab.py           │                   │
│  │  AgentService        │    │  AgentTab             │                   │
│  │  _run_loop() ────────┼────┤  → LLM 设置按钮       │                   │
│  │  调用 LiteLLMProvider │    │  → 打开精简设置面板    │                   │
│  │  传入 conversation_id │    │                       │                   │
│  │  传入 trace_id        │    │                       │                   │
│  └──────────────────────┘    └──────────────────────┘                   │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3. 数据流图

```
                       用户操作
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   编辑 JSON 配置    GUI 设置面板    GUI Provider 管理
   (手动编辑)      (选择/开关)     (增删改 Provider)
          │               │               │
          └───────────────┼───────────────┘
                          │
                          ▼
              ┌─────────────────────┐
              │  llm_providers.json  │  ← 权威数据源
              │  (data/config/)      │
              └──────────┬──────────┘
                         │
                         │ 加载 + 验证 (Pydantic)
                         ▼
              ┌─────────────────────┐
              │  LLMManagerService  │
              │  (modules/llm_      │
              │   manager/service)  │
              └──────────┬──────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
      active_provider  models[]   thinking config
      + api_key        列表        + budget
            │            │            │
            └────────────┼────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   LLMManager        │  ← 框架层 (toolkit/core/llm/)
              │   初始化 Provider    │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  LiteLLMProvider    │
              │  ├─ api_base = url  │
              │  ├─ thinking param  │
              │  └─ model name      │
              └──────────┬──────────┘
                         │
                         │  litellm.acompletion()
                         ▼
              ┌─────────────────────┐
              │  外部 LLM API       │
              │  (GLM/Claude/...)   │
              └──────────┬──────────┘
                         │
                         │ response (含 usage)
                         ▼
              ┌─────────────────────┐
              │  返回给 Agent Chat   │
              └──────────┬──────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
      usage 数据    text 内容    thinking blocks
            │
            ▼
    ┌─────────────────┐
    │  TokenTracker    │
    │  record(p_tokens,│
    │   c_tokens,      │
    │   conv_id,       │
    │   trace_id)      │
    └────────┬─────────┘
             │
             ▼
    ┌─────────────────┐      ┌─────────────────┐
    │  SQLite          │      │  ContextRing     │
    │  llm_token_usage │      │  Widget          │
    │  (后台记录,       │      │  (状态栏圆环      │
    │   后续飞书统计)    │      │   实时显示百分比)  │
    └─────────────────┘      └─────────────────┘
```

### 4. 时序图 — LLM 请求全流程

```
  AgentChat       LLMManager    LLMMgrService  LiteLLMProvider  TokenTracker
    │                 │              │               │              │
    │  1. 发起对话     │              │               │              │
    │────────────────►│              │               │              │
    │                 │              │               │              │
    │                 │ 2. 获取当前   │               │              │
    │                 │   Provider    │               │              │
    │                 │─────────────►│               │              │
    │                 │              │               │              │
    │                 │ 3. 返回       │               │              │
    │                 │   config      │               │              │
    │                 │◄─────────────│               │              │
    │                 │              │               │              │
    │                 │ 4. stream_chat(model, msgs,  │              │
    │                 │    api_base, thinking,       │              │
    │                 │    api_key, conv_id)         │              │
    │                 │─────────────────────────────►│              │
    │                 │              │               │              │
    │                 │              │   5. litellm.acompletion()   │
    │                 │              │   (带 api_base + thinking)   │
    │                 │              │               │              │
    │                 │              │   ═══════ LLM API ════════  │
    │                 │              │               │              │
    │                 │  6. stream chunks              │              │
    │                 │◄─────────────────────────────│              │
    │                 │              │               │              │
    │ 7. text chunks  │              │               │              │
    │◄────────────────│              │               │              │
    │                 │              │               │              │
    │                 │  8. usage (prompt + completion tokens)      │
    │                 │─────────────────────────────────────────────►│
    │                 │              │               │              │
    │                 │              │               │  9. SQL INSERT│
    │                 │              │               │  (conv_id,    │
    │                 │              │               │   trace_id,   │
    │                 │              │               │   provider,   │
    │                 │              │               │   model,      │
    │                 │              │               │   p_tokens,   │
    │                 │              │               │   c_tokens)   │
    │                 │              │               │              │
    │ 10. 更新上下文   │              │               │              │
    │    用量显示      │              │               │              │
    │◄────────────────│              │               │              │
```

### 5. 时序图 — Provider CRUD (GUI)

```
  用户          LLMSettingsDialog   ProviderManageDialog  LLMMgrService   llm_providers.json
   │                 │                    │                    │                │
   │ 1. 打开设置      │                    │                    │                │
   │────────────────►│                    │                    │                │
   │                 │                    │                    │                │
   │                 │ 2. 加载 provider   │                    │                │
   │                 │   列表             │                    │                │
   │                 │───────────────────────────────────────►│                │
   │                 │                    │                    │                │
   │                 │ 3. 返回列表        │                    │                │
   │                 │◄───────────────────────────────────────│                │
   │                 │                    │                    │                │
   │ 4. 点击          │                    │                    │                │
   │   "管理Provider" │                    │                    │                │
   │────────────────►│                    │                    │                │
   │                 │                    │                    │                │
   │                 │ 5. 打开对话框       │                    │                │
   │                 │───────────────────►│                    │                │
   │                 │                    │                    │                │
   │                 │                    │ 6. 加载完整配置     │                │
   │                 │                    │───────────────────►│                │
   │                 │                    │                    │                │
   │                 │                    │ 7. 返回配置         │                │
   │                 │                    │◄───────────────────│                │
   │                 │                    │                    │                │
   │ 8. 编辑 Provider  │                    │                    │                │
   │   (修改URL/Key/   │                    │                    │                │
   │    模型列表)       │                    │                    │                │
   │─────────────────────────────────────►│                    │                │
   │                 │                    │                    │                │
   │ 9. 保存修改       │                    │                    │                │
   │─────────────────────────────────────►│                    │                │
   │                 │                    │                    │                │
   │                 │                    │ 10. 验证 + 保存     │                │
   │                 │                    │───────────────────►│                │
   │                 │                    │                    │                │
   │                 │                    │          11. 写入JSON              │
   │                 │                    │                    │───────────────►│
   │                 │                    │                    │                │
   │                 │                    │ 12. 保存成功        │                │
   │                 │                    │◄───────────────────│                │
   │                 │                    │                    │                │
   │ 13. 关闭对话框    │                    │                    │                │
   │                 │                    │                    │                │
   │                 │ 14. 刷新 Provider   │                    │                │
   │                 │    下拉列表         │                    │                │
   │                 │◄───────────────────────────────────────│                │
```

### 6. 类图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        toolkit/core/llm/ (框架层 — 精简后)                 │
│                                                                          │
│  ┌──────────────────────┐    ┌──────────────────────────┐               │
│  │  LLMManager (QObject)│    │  LiteLLMProvider          │               │
│  ├──────────────────────┤    ├──────────────────────────┤               │
│  │ - _config: LLMConfig │    │ - api_key: str            │               │
│  │ - _session_tokens    │    │ - model: str              │               │
│  │ - _provider_config   │◄───│ - provider_id: str        │               │
│  ├──────────────────────┤    │ - api_base: str | None    │  ← 新增       │
│  │ + set_provider(id)   │    │ - thinking: dict | None   │  ← 新增       │
│  │ + stream_chat()      │    ├──────────────────────────┤               │
│  │ + record_tokens(n)   │    │ + stream_chat(messages,   │               │
│  │ + get_context_ratio()│    │   api_base=, thinking=)   │               │
│  │ + reset_session()    │    │ + count_tokens()          │               │
│  └──────────────────────┘    └──────────────────────────┘               │
│           │                                                                 │
│           │ uses                                                            │
│           ▼                                                                 │
│  ┌──────────────────────┐                                                  │
│  │  LLMConfig (精简后)   │                                                  │
│  ├──────────────────────┤                                                  │
│  │ + provider: str       │  ← 放宽为任意字符串                              │
│  │ + model_name: str     │                                                  │
│  │ - glm_api_key: REMOVED│  ← 移除，API Key 迁移到 llm_providers.json       │
│  │ - claude_api_key: REMOVED│                                               │
│  │ - temperature: REMOVED│  ← 移除                                         │
│  │ - max_tokens: REMOVED │  ← 移除                                         │
│  │ - smart_switch: REMOVED│  ← 移除                                        │
│  │ - token_budget: REMOVED│  ← 移除                                        │
│  │ - budget_alert: REMOVED│  ← 移除                                        │
│  └──────────────────────┘                                                  │
└──────────────────────────────────────────────────────────────────────────┘
           │
           │ ServiceRegistry.get("llm_manager_service")
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    modules/llm_manager/src/ (新增模块)                     │
│                                                                          │
│  ┌──────────────────────────┐    ┌──────────────────────────┐           │
│  │  LLMManagerService        │    │  ProviderConfig (Pydantic)│           │
│  ├──────────────────────────┤    ├──────────────────────────┤           │
│  │ - _config_path: Path      │    │ + id: str                │           │
│  │ - _providers: list[Prov]  │    │ + name: str              │           │
│  │ - _active_provider: str   │    │ + base_url: str = ""     │           │
│  ├──────────────────────────┤    │ + litellm_prefix: str     │           │
│  │ + load() -> ProvidersConfig│   │ + api_key: str = ""      │           │
│  │ + save(config)            │    │ + enabled: bool = True   │           │
│  │ + get_provider(id) -> Prov│    │ + thinking: bool         │           │
│  │ + add_provider(prov)      │    │ + thinking_budget: int   │           │
│  │ + remove_provider(id)     │    │ + models: list[Model]    │           │
│  │ + update_provider(prov)   │    │ + default_model: str     │           │
│  │ + get_active() -> tuple   │    └──────────────────────────┘           │
│  │ + set_active(id)          │              │                             │
│  └───────────┬──────────────┘              │ contains                     │
│              │                             ▼                             │
│              │ owns            ┌──────────────────────────┐              │
│              ├────────────────┤  ModelConfig (Pydantic)   │              │
│              │                ├──────────────────────────┤              │
│              │                │ + name: str               │              │
│              │                │ + context_window: int     │              │
│              │                └──────────────────────────┘              │
│              │                                                           │
│              │ owns                                                       │
│              ▼                                                           │
│  ┌──────────────────────────┐                                            │
│  │  TokenTracker             │                                            │
│  ├──────────────────────────┤                                            │
│  │ - _db: DatabaseManager   │                                            │
│  ├──────────────────────────┤                                            │
│  │ + record(request_id,     │                                            │
│  │    conversation_id,       │  ← 由调用方传入 (Agent Chat)               │
│  │    trace_id,              │  ← 由调用方传入                            │
│  │    provider, model,       │                                            │
│  │    prompt_tokens,         │                                            │
│  │    completion_tokens)     │                                            │
│  │ + get_total_usage()       │                                            │
│  │ + get_usage_by_conv(id)   │                                            │
│  │ + get_usage_by_trace(id)  │                                            │
│  └──────────────────────────┘                                            │
│                                                                          │
│  ┌──────────────────────────┐                                            │
│  │  ProviderManageDialog     │                                            │
│  │  (继承 ToolkitDialog)     │                                            │
│  ├──────────────────────────┤                                            │
│  │ - _service: LLMMgrService│                                            │
│  │ - _list: QListWidget     │                                            │
│  │ - _edit_panel: QWidget   │                                            │
│  ├──────────────────────────┤                                            │
│  │ + _on_select_provider()  │                                            │
│  │ + _on_add_provider()     │                                            │
│  │ + _on_save_changes()     │                                            │
│  │ + _on_delete_provider()  │                                            │
│  │ + _on_add_model()        │                                            │
│  │ + _on_remove_model()     │                                            │
│  └──────────────────────────┘                                            │
│                                                                          │
│  ┌──────────────────────────┐                                            │
│  │  plugin.py               │                                            │
│  │  (继承 BasePlugin)       │                                            │
│  ├──────────────────────────┤                                            │
│  │ + get_plugin_info()      │                                            │
│  │ + register_gui_tab()     │  → None (无独立 Tab)                        │
│  │ + register_agent_tools() │  → [] (暂不暴露 Agent 工具)                  │
│  │ + register_skills()      │  → []                                      │
│  │ + on_startup(ctx)        │  → 注册 LLMManagerService                   │
│  │ + on_shutdown()          │  → 清理资源                                 │
│  └──────────────────────────┘                                            │
└──────────────────────────────────────────────────────────────────────────┘
           │
           │ GUI 层交互
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      toolkit/gui/ (GUI 层 — 精简)                         │
│                                                                          │
│  ┌──────────────────────────┐    ┌──────────────────────────┐           │
│  │  LLMSettingsDialog        │    │  ContextRingWidget       │           │
│  │  (继承 ToolkitDialog)     │    │  (QWidget, 18x18)        │           │
│  ├──────────────────────────┤    ├──────────────────────────┤           │
│  │ - _provider_combo        │    │ - _ratio: float           │           │
│  │ - _model_combo           │    │ - _fg: QColor #89b4fa    │           │
│  │ - _thinking_check        │    ├──────────────────────────┤           │
│  │ - _service: LLMMgrService│    │ + set_ratio(0.0~1.0)     │           │
│  ├──────────────────────────┤    │ + paintEvent() (QPainter) │           │
│  │ + _load_providers()      │    └──────────────────────────┘           │
│  │ + _on_provider_changed() │                                            │
│  │ + _on_manage_clicked()   │                                            │
│  │ + _on_save()             │                                            │
│  └──────────────────────────┘                                            │
│                                                                          │
│  ┌──────────────────────────┐                                            │
│  │  LLMStatusWidget         │                                            │
│  │  (QWidget)               │                                            │
│  ├──────────────────────────┤                                            │
│  │ - _ring: ContextRing     │                                            │
│  │ - _model_label: QLabel   │                                            │
│  │ - _ring.setToolTip()     │  ← hover 显示精确数字                       │
│  ├──────────────────────────┤                                            │
│  │ + set_ratio(r)           │                                            │
│  │ + set_model(name)        │                                            │
│  │ REMOVED: _token_label    │  ← 移除文字标签                             │
│  │ REMOVED: color logic     │  ← 移除绿/黄/红颜色                         │
│  └──────────────────────────┘                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

### 7. 配置迁移时序图

```
  应用启动        LLMManagerService     旧 toolkit_config.json    新 llm_providers.json
     │                    │                      │                       │
     │ 1. on_startup()    │                      │                       │
     │───────────────────►│                      │                       │
     │                    │                      │                       │
     │                    │ 2. 检查 llm_providers.json                   │
     │                    │   是否存在？                                  │
     │                    │──────────────────────────────────────────────►│
     │                    │                      │                       │
     │                    │ 3. 不存在 ← 首次启动   │                       │
     │                    │◄─────────────────────────────────────────────│
     │                    │                      │                       │
     │                    │ 4. 读取旧配置          │                       │
     │                    │─────────────────────►│                       │
     │                    │                      │                       │
     │                    │ 5. 提取 API Keys      │                       │
     │                    │   glm_api_key         │                       │
     │                    │   claude_api_key      │                       │
     │                    │◄─────────────────────│                       │
     │                    │                      │                       │
     │                    │ 6. 从内置模板生成       │                       │
     │                    │   llm_providers.json   │                       │
     │                    │   填充迁移的 API Keys   │                       │
     │                    │──────────────────────────────────────────────►│
     │                    │                      │                       │
     │                    │ 7. 写入 _llm_migrated: true                   │
     │                    │─────────────────────►│                       │
     │                    │                      │                       │
     │ 8. 启动完成         │                      │                       │
     │◄───────────────────│                      │                       │
```

### 图例说明

| 符号 | 含义 |
|------|------|
| `◄──►` | 双向关联 / 调用 |
| `────►` | 单向调用 / 数据流 |
| `-` | 私有属性/方法 |
| `+` | 公开属性/方法 |
| `REMOVED` | 本次重构中移除的项 |
| `← 新增` | 本次重构中新增的项 |
| `═══` | 外部系统边界 |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 配置自定义 LLM Provider (Priority: P1)

用户希望通过 JSON 配置文件或 GUI 对话框，添加和管理多个 LLM Provider（如 GLM、Claude、DeepSeek、Ollama 等），每个 Provider 拥有独立的 API 地址、API Key 和模型列表。用户可以通过 GUI 或手动编辑 JSON 两种方式配置 Provider。

**Why this priority**: 这是本次重构的核心 —— 将原本硬编码的 2 个 Provider 扩展为可配置的多 Provider 体系，是一切其他功能的基础。

**Independent Test**: 手动编辑 `data/config/llm_providers.json` 添加一个 Provider，启动应用后在设置面板中看到新增的 Provider 可选，选择后能正常发起对话。

**Acceptance Scenarios**:

1. **Given** 应用首次启动，**When** 检查配置文件，**Then** `data/config/llm_providers.json` 自动生成，包含 GLM 和 Claude 两个默认 Provider，从旧 `toolkit_config.json` 迁移已有的 API Key。
2. **Given** 用户编辑 JSON 新增了一个 Provider（含 base_url、models、api_key），**When** 重启应用或触发重载，**Then** 设置面板 Provider 下拉列表中显示该新 Provider。
3. **Given** 用户通过 Provider 管理对话框添加了一个新 Provider，**When** 保存后，**Then** JSON 配置文件更新，下拉列表即时刷新。
4. **Given** 某 Provider 的 `enabled: false`，**When** 查看设置面板 Provider 下拉列表，**Then** 该 Provider 不显示。

---

### User Story 2 - 自定义 Provider API 地址 (Priority: P1)

用户需要为任意 Provider 修改其默认的 API 基础地址（base_url）。当用户通过代理、私有部署或兼容端点使用 LLM 时，将请求路由到用户指定的 URL，而非官方默认地址。

**Why this priority**: 解决实际使用中的代理/私有部署/兼容端点需求，与 P1-1 同等重要。

**Independent Test**: 在配置中将 Claude 的 base_url 改为代理地址，发送请求后请求到达代理而非 api.anthropic.com。

**Acceptance Scenarios**:

1. **Given** Provider 配置了 `base_url`，**When** 发送 LLM 请求，**Then** 请求发送到该 base_url 而非 LiteLLM 默认地址。
2. **Given** Provider 未配置 `base_url`（空字符串），**When** 发送请求，**Then** 使用 LiteLLM 为该 Provider 的默认官方地址。
3. **Given** 用户修改了已有 Provider 的 `base_url`，**When** 保存并重载，**Then** 后续请求使用新地址。

---

### User Story 3 - 模型上下文尺寸区分 (Priority: P2)

用户在为 Provider 配置模型时，可以标注每个模型的上下文窗口大小。在设置面板的模型下拉列表中，[1M] 级别的大上下文模型应有醒目标签区分，便于用户根据任务选择合适的模型。

**Why this priority**: 提升模型选择效率，避免用户用低上下文模型分析大文件导致出错。

**Independent Test**: 配置文件中 claude-opus-4-7 的 context_window 设为 1000000，在模型下拉列表中该项显示 "[1M] claude-opus-4-7"。

**Acceptance Scenarios**:

1. **Given** Provider 配置了多个模型，每个模型有不同的 `context_window`，**When** 打开设置面板模型下拉列表，**Then** 模型名旁显示上下文窗口标识（如 `[1M]`、`[200K]`、`[128K]`）。
2. **Given** 某个模型的 context_window 小于 100000，**When** 渲染下拉列表，**Then** 不显示特殊标签。

---

### User Story 4 - Thinking 特性支持 (Priority: P2)

用户希望在使用支持 extended thinking 的模型（如 Claude Opus/Sonnet）时，能够开启 thinking 功能，让模型在回答前进行深度推理。对于不支持 thinking 的模型（如 GLM），该选项自动隐藏。

**Why this priority**: thinking 是提高分析质量的关键功能，但依赖于 Provider 支持，优先级低于基础配置体系。

**Independent Test**: 选择 Claude 模型，开启 Thinking，发送请求后观察响应中包含 thinking 推理内容块。

**Acceptance Scenarios**:

1. **Given** 当前选择的 Provider 的 `thinking: true`，**When** 打开设置面板，**Then** 显示「启用扩展思考」复选框。
2. **Given** 当前选择的 Provider 的 `thinking: false`，**When** 打开设置面板，**Then** Thinking 复选框完全隐藏。
3. **Given** 用户开启了 Thinking，**When** 发送请求，**Then** 系统使用 Provider 配置中预设的 `thinking_budget` 默认值（如 4000），请求中包含 thinking 参数。
4. **Given** 用户开启 Thinking 后关闭了 Thinking，**When** 发送请求，**Then** 请求中不包含 thinking 参数。

---

### User Story 5 - 精简的 LLM 设置面板 (Priority: P2)

用户打开 LLM 设置对话框时，只看到最核心的 3 个控件：Provider 选择、Model 选择、Thinking 开关。temperature、max_tokens、智能切换、token 预算、告警阈值等字段全部移除，降低认知负担。

**Why this priority**: UI 精简是用户体验改善，依赖于 P1 的 Provider 配置体系先完成。

**Independent Test**: 打开 LLM 设置面板，确认只显示 Provider 下拉 + Model 下拉 + Thinking 开关 + 管理 Provider 按钮 + 保存按钮。

**Acceptance Scenarios**:

1. **Given** 用户打开 LLM 设置对话框，**When** 查看面板内容，**Then** 仅显示 Provider 选择、Model 选择、Thinking 开关、「管理 Provider」按钮、「保存」按钮。
2. **Given** 旧版配置中还有 temperature、smart_switch 等字段，**When** 启动新版应用，**Then** 这些字段被忽略，不影响正常运行。

---

### User Story 6 - Token 用量后台记录 (Priority: P3)

系统需要在后台持续记录每次 LLM 请求的 Token 用量（输入/输出 Token 数），并关联对话 ID 和 Trace 分析任务 ID。记录数据存储在 SQLite 中，后续飞书登录系统接入后可关联用户 ID 做用量统计。

**Why this priority**: 为后续飞书集成的用量统计做准备，当前不涉及 UI 展示，优先级低于用户可感知的功能。

**Independent Test**: 发送一次 LLM 请求后，查询 SQLite 数据库 `llm_token_usage` 表，确认新增了一条记录，包含 provider、model、prompt_tokens、completion_tokens、conversation_id 等字段。

**Acceptance Scenarios**:

1. **Given** 用户发起一次 Agent 对话，**When** LLM 返回响应（含 usage 信息），**Then** 系统向 `data/db/llm_token_usage.db` 写入一条记录，包含 request_id / conversation_id / provider / model / prompt_tokens / completion_tokens / timestamp。
2. **Given** 用户对一份 Trace 文件发起分析，**When** 分析过程中多次调用 LLM，**Then** 所有调用的 Token 记录均关联同一个 trace_id。
3. **Given** 数据库记录已累计，**When** 后续接入飞书登录后，**Then** 可通过 SQL 按 user_id / conversation_id / trace_id 等维度聚合统计。

---

### User Story 7 - 状态栏上下文用量显示 (Priority: P2)

用户在底部状态栏可以看到一个圆环指示器，填充比例代表当前对话已用 Token 占模型上下文窗口的百分比。鼠标悬停圆环时显示精确数字 tooltip。

**Why this priority**: 解决用户在使用大文件分析时不知道上下文还剩多少的痛点。不用复杂文字和颜色，一个环就能直观传达用量比例。

**Independent Test**: 选择 `glm-4-plus`（128K 上下文），发起对话消耗约 5K tokens。状态栏圆环约 4% 填充。hover 显示 "5,120 / 128,000 tokens (4.0%)"。

**Acceptance Scenarios**:

1. **Given** 用户选择了模型，**When** 查看状态栏，**Then** 圆环显示当前上下文用量百分比填充。
2. **Given** 用户 hover 在圆环上，**When** tooltip 弹出，**Then** 显示 "已用 / 总容量 (百分比)"。
3. **Given** 用户开启新对话，**When** 查看状态栏，**Then** 圆环填充重置为 0%。

---

### Edge Cases

- 用户手动编辑 JSON 时格式错误（非法 JSON 或必填字段缺失）→ 启动时给出明确错误提示，回退到内置默认配置。
- 用户删除当前正在使用的 Provider → 自动切换回第一个可用的 Provider。
- 用户删除了某 Provider 下的全部模型 → 该 Provider 显示但不可用，提示「未配置模型」。
- `llm_providers.json` 文件被意外删除 → 下次启动自动从模板重建默认配置。
- 多个 Provider 配置了相同的 `id` → 后出现的覆盖前者，启动时输出 warning 日志。
- Thinking 开启后模型返回的 thinking block 超长 → 超出的 thinking tokens 不影响最终的 response，正常处理。
- 对话上下文接近模型上限（>95%）→ 圆环接近满填充，用户 hover 发现用量告急，应手动开启新对话或切换更大上下文的模型。
- 用户未配置任何 Provider 的 API Key → 状态栏不显示圆环，显示「未配置」；设置面板正常打开，Provider/Model 下拉正常显示，但 Agent Chat 发送消息时提示「请先配置 API Key」并打开设置面板。
- 模型未配置 `context_window` → 圆环无法计算比例，默认显示空环。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 在 `data/config/llm_providers.json` 中以 JSON 格式存储所有 LLM Provider 配置（id、name、base_url、litellm_prefix、api_key、enabled、thinking、models）。
- **FR-002**: 系统 MUST 支持配置文件中定义多个 LLM Provider，每个 Provider 可拥有独立的 API 地址和 API Key。
- **FR-003**: 系统 MUST 将 LLM 配置管理逻辑从 `toolkit/core/llm/` 抽离到 `modules/llm_manager/` 独立模块中。
- **FR-004**: 每个 Provider MUST 支持配置多个模型，每个模型包含 name 和 context_window 属性。
- **FR-005**: 模型下拉列表中，上下文窗口 ≥ 1000000 的模型 MUST 标注 `[1M]` 前缀；≥ 128000 的 MUST 标注对应大小标签（如 `[200K]`、`[128K]`）；< 128000 的不标注。
- **FR-006**: 系统 MUST 支持通过 `base_url` 字段覆盖任意 Provider 的默认 API 地址，请求路由到用户指定的 URL 而非官方默认地址。
- **FR-007**: 系统 MUST 支持通过 `thinking` 字段控制每个 Provider 的 extended thinking 能力，仅在 `thinking: true` 时在设置面板显示 Thinking 开关。
- **FR-008**: 设置面板 MUST 精简为 Provider 选择、Model 选择、Thinking 开关（条件显示）、管理 Provider 按钮、保存按钮，共 3-5 个控件。
- **FR-009**: 系统 MUST 移除 temperature、max_tokens、智能切换（smart_switch）、token 预算（token_budget）、预算告警阈值（budget_alert_threshold）的所有设置面板 UI 和底层配置逻辑。
- **FR-010**: 系统 MUST 在后台将每次 LLM 请求的 Token 用量持久化存储，记录字段包括：request_id、conversation_id、trace_id、provider、model、prompt_tokens、completion_tokens、timestamp。conversation_id 和 trace_id 由调用方（如 Agent Chat）传入，llm_manager 模块不自行生成或管理这些 ID，保持模块解耦。
- **FR-011**: 详细的多维度 Token 统计数据（按 conversation/trace/provider 维度聚合）MUST NOT 在 GUI 中展示为图表、统计面板或数据表格，仅做后台记录供后续飞书集成做统计分析。状态栏的上下文用量实时显示见 FR-016~018。
- **FR-012**: 系统 MUST 首次启动时检测 `llm_providers.json` 是否存在，若不存在则从内置模板生成（含 GLM 和 Claude 默认配置），并从旧 `toolkit_config.json["llm"]` 迁移已有的 API Key。
- **FR-013**: 用户 MUST 能够通过 GUI Provider 管理对话框（增删改）和手动编辑 JSON 配置文件两种方式管理 Provider。
- **FR-014**: 每个 Provider 的 API Key MUST 存储在其 JSON 配置中，不再使用独立的 API Key 字段。
- **FR-015**: LLMConfig 的 provider 字段 MUST 放宽为任意字符串，不再通过正则限制为 `glm|claude`。
- **FR-016**: 底部状态栏 MUST 以圆环指示器显示当前对话上下文用量占模型上下文窗口的百分比填充，鼠标悬停圆环时 MUST 显示精确数字 tooltip（格式：`已用 / 总容量 (百分比)`）。
- **FR-017**: 上下文用量圆环 MUST NOT 在旁显示文字标签（避免与 hover tooltip 重复），也 MUST NOT 使用颜色区分（统一单色填充）。
- **FR-018**: 切换模型或开启新对话时，上下文用量 MUST 重置为零。

### Key Entities

- **Provider 配置**: LLM 服务提供方的完整定义，包含 id（唯一标识）、name（显示名称）、base_url（自定义 API 地址）、litellm_prefix（LiteLLM 路由前缀）、api_key、enabled（启用/禁用）、thinking（是否支持扩展思考）、models（可用模型列表）、default_model（默认模型）。
- **Model 配置**: 属于某个 Provider 的具体模型，包含 name（模型名称）、context_window（上下文窗口 tokens 数）。
- **Token 用量记录**: 单次 LLM 请求的用量快照，包含 request_id、conversation_id、trace_id、provider、model、prompt_tokens、completion_tokens、timestamp。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户可以在 2 分钟内通过编辑 JSON 文件或使用 GUI 对话框完成一个新 LLM Provider 的添加和启用。
- **SC-002**: 设置面板的控件数量从当前的 9+ 个减少到 ≤ 5 个（Provider 选择、Model 选择、Thinking 开关、管理按钮、保存按钮）。
- **SC-003**: 每次 LLM 请求完成后，Token 用量记录在 1 秒内完成持久化。
- **SC-004**: 切换到自定义 base_url 的 Provider 后，LLM 请求正确路由到新地址，无需修改任何代码。
- **SC-005**: Thinking 功能对支持的模型可用，开启后能正常完成多步工具调用任务，thinking content blocks 正确解析不丢失。
- **SC-006**: 配置文件损坏或缺失时，系统在 5 秒内降级到内置默认配置并正常启动，不崩溃。
- **SC-007**: 状态栏上下文用量显示在每次 LLM 响应后 500ms 内更新，用户无需手动刷新。（定性验收，不强制性能测试）
- **SC-008**: 用户切换模型或开启新对话时，圆环填充在 200ms 内重置并更新。（定性验收，不强制性能测试）

## Assumptions

- 用户通过 LiteLLM 统一调用 LLM，新增的自定义 Provider 必须是 LiteLLM 支持的 Provider 或有 OpenAI 兼容端点。
- LiteLLM 的 `api_base` 参数可用于覆盖所有支持 Provider 的默认 API 地址。
- Anthropic extended thinking API 通过 LiteLLM 的 `thinking` 参数原生支持。
- SQLite 数据库已通过 `DatabaseManager` 统一管理，Token 用量表迁移走标准流程。
- 飞书登录和用户系统尚未实现，Token 记录预留 `user_id` 等字段但当前不填充。
- 模块名为 `llm_manager`，遵循 `modules/<name>/` 标准结构，通过 plugin.py 注册到框架。
- 配置文件 `llm_providers.json` 的读写权限由系统用户保证。
