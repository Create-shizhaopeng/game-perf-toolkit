# Research: 历史文件选中联动 Agent 对话上下文

## 目录

- [Decision 1: 事件契约沿用 EventBus 解耦](#decision-1-事件契约沿用-eventbus-解耦)
- [Decision 2: 上下文按会话隔离](#decision-2-上下文按会话隔离)
- [Decision 3: 多文件上下文采用路径去重](#decision-3-多文件上下文采用路径去重)
- [Decision 4: 注入策略为“拼接到用户消息尾部”](#decision-4-注入策略为拼接到用户消息尾部)
- [Decision 5: 删除交互支持 x + backspace-delete](#decision-5-删除交互支持-x--backspace-delete)
- [Decision 6: Agent 未初始化时先缓存事件](#decision-6-agent-未初始化时先缓存事件)

## Decision 1: 事件契约沿用 EventBus 解耦

### Decision
历史面板通过 `history.send_to_agent` 事件向 Agent Chat 发送上下文，不做模块间直接调用。

### Rationale
- 符合插件解耦原则，避免 `perfetto_capture` 直接依赖 `agent_chat` 实现。
- 便于未来其他模块（如 `perfetto_analysis`）复用同一发送机制。

### Alternatives considered
- 直接调用 `agent_tab` 方法：耦合高，破坏模块边界。
- 通过全局单例共享状态：可测试性差。

## Decision 2: 上下文按会话隔离

### Decision
上下文以会话 ID 为作用域管理；新会话默认空上下文，不继承其他会话。

### Rationale
- 与用户澄清一致，避免跨会话污染。
- 便于回放会话历史时恢复当时上下文语义。

### Alternatives considered
- 全局单例上下文：实现简单但容易误注入。
- 仅当前窗口上下文：会话切换语义不清晰。

## Decision 3: 多文件上下文采用路径去重

### Decision
支持多文件上下文，按 `file_path` 去重；重复发送同一路径不重复追加。

### Rationale
- 保持 UI 清晰，避免上下文膨胀。
- 满足“多文件分析”场景。

### Alternatives considered
- 仅单文件：无法覆盖批量对比分析诉求。
- 允许重复项：会增加用户困扰和 token 噪音。

## Decision 4: 注入策略为“拼接到用户消息尾部”

### Decision
发送消息时将活跃文件路径列表拼接到用户本轮消息尾部。

### Rationale
- 满足用户澄清结论，改动面最小。
- 不依赖 provider 特定 metadata 协议，兼容现有 LLM provider。

### Alternatives considered
- system prompt 注入：一致性更强，但不符合当前澄清。
- provider metadata：跨 provider 适配复杂。

## Decision 5: 删除交互支持 x + backspace-delete

### Decision
ContextBar 中每个文件项支持点击 `×` 删除；选中项支持 Backspace/Delete 删除。

### Rationale
- 同时覆盖鼠标与键盘高效操作。
- 与桌面应用交互习惯一致。

### Alternatives considered
- 仅 `×` 删除：键盘效率不足。
- 全局 Backspace/Delete 删除：存在误删风险。

## Decision 6: Agent 未初始化时先缓存事件

### Decision
若 Agent Chat 未初始化，先缓存在队列中，初始化完成后按到达顺序回放。

### Rationale
- 解决竞态，避免用户操作丢失。
- 保持事件驱动架构稳定。

### Alternatives considered
- 丢弃早到事件：体验不可接受。
- 强制阻塞初始化：引入耦合与卡顿。
