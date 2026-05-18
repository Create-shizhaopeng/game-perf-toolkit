# Data Model: 历史文件选中联动 Agent 对话上下文

## 目录

- [实体概览](#实体概览)
- [FileContext](#filecontext)
- [ConversationContextState](#conversationcontextstate)
- [HistorySendEvent](#historysendevent)
- [状态转换](#状态转换)

## 实体概览

```text
History Item (trace / analysis)
  └─(right click "发送到 Agent 对话")→ HistorySendEvent
                                      └→ ConversationContextState[conversation_id]
                                           └→ [FileContext...]
```

## FileContext

表示一条活跃文件上下文项。

| 字段 | 类型 | 说明 |
|---|---|---|
| `context_id` | `str` | 唯一标识，可用 `uuid4()` |
| `file_path` | `str` | 绝对路径，作为去重键 |
| `file_name` | `str` | 展示名称 |
| `context_type` | `"trace" \| "analysis"` | 上下文来源 |
| `missing` | `bool` | 文件不存在标记（可选，默认 `false`） |
| `created_at` | `datetime` | 注入时间 |

约束：
- 同一会话内 `file_path` 必须唯一。
- 删除操作按 `context_id` 或 `file_path` 定位。

## ConversationContextState

按会话维护的上下文集合。

| 字段 | 类型 | 说明 |
|---|---|---|
| `conversation_id` | `str` | 会话 ID |
| `contexts` | `list[FileContext]` | 活跃上下文列表 |
| `updated_at` | `datetime` | 最近更新时间 |

约束：
- 新建会话时初始化 `contexts=[]`。
- 会话切换时加载目标会话的 `contexts`。

## HistorySendEvent

`history.send_to_agent` 事件 payload。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_path` | `str` | 是 | 绝对路径 |
| `file_name` | `str` | 是 | 展示名 |
| `context_type` | `"trace" \| "analysis"` | 是 | 来源类型 |
| `missing` | `bool` | 否 | 文件不存在标记 |

## 状态转换

```text
空上下文
  └─(收到 history.send_to_agent)→ [A]
[A]
  └─(收到 history.send_to_agent B)→ [A, B]
[A, B]
  ├─(重复发送 A)→ [A, B]        # 去重
  ├─(点击 A 的 ×)→ [B]
  ├─(选中 B + Backspace/Delete)→ [A]
  └─(切换到新会话 C)→ []        # 会话隔离
```
