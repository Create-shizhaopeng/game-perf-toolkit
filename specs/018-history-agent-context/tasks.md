# Tasks: 历史文件选中联动 Agent 对话上下文

**Input**: Design documents from `specs/018-history-agent-context/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/history-send-to-agent.event.json`

## 目录

- [Phase 1: Foundational](#phase-1-foundational-blocking-prerequisites)
- [Phase 2: US1 — 右键发送文件到 Agent 对话](#phase-2-user-story-1--右键发送文件到-agent-对话-priority-p1--mvp)
- [Phase 3: US2 — Agent 利用上下文进行分析对话](#phase-3-user-story-2--agent-利用上下文进行分析对话-priority-p2)
- [Phase 4: US3 — 管理已注入的上下文](#phase-4-user-story-3--管理已注入的上下文-priority-p2)
- [Phase 5: Polish & 验证](#phase-5-polish--验证)
- [Dependencies & Execution Order](#dependencies--execution-order)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无依赖冲突）
- **[Story]**: 对应用户故事（US1/US2/US3）
- 任务描述必须包含明确文件路径

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: 打通事件契约与会话上下文基础能力，作为所有故事前置。

- [ ] T001 定义并常量化事件名 `history.send_to_agent` 及 payload 解析入口，统一引用 in `modules/agent_chat/src/gui_tab.py` and `modules/perfetto_capture/src/history_panel.py`
- [ ] T002 建立会话级上下文状态容器（`conversation_id -> list[FileContext]`）与去重逻辑（按 `file_path`）in `modules/agent_chat/src/gui_tab.py`
- [ ] T003 增加 Agent 未初始化时的事件缓存队列与初始化回放机制 in `modules/agent_chat/src/gui_tab.py`
- [ ] T004 梳理右侧面板自动打开调用链，确保 `show_right_panel` 可被 Agent Tab 安全调用 in `toolkit/gui/main_window.py`

**Checkpoint**: 事件与会话上下文基础设施可用，可进入 US1。

---

## Phase 2: User Story 1 — 右键发送文件到 Agent 对话 (Priority: P1) 🎯 MVP

**Goal**: 历史条目右键可发送上下文，右侧面板自动打开并展示上下文区域。

**Independent Test**: 右键抓取历史/分析历史条目发送后，1 秒内右侧打开并显示文件项。

### Implementation for User Story 1

- [ ] T005 [US1] 在抓取历史条目右键菜单增加“发送到 Agent 对话”动作 in `modules/perfetto_capture/src/history_panel.py`
- [ ] T006 [US1] 在分析历史条目右键菜单增加“发送到 Agent 对话”动作 in `modules/perfetto_capture/src/history_panel.py`
- [ ] T007 [US1] 实现发送事件 payload 构建：`file_path`、`file_name`、`context_type`、`missing` in `modules/perfetto_capture/src/history_panel.py`
- [ ] T008 [US1] 发布 `history.send_to_agent` 事件并补充异常保护日志 in `modules/perfetto_capture/src/history_panel.py`
- [ ] T009 [US1] Agent Chat 监听 `history.send_to_agent` 事件并触发右侧面板自动打开 in `modules/agent_chat/src/gui_tab.py`
- [ ] T010 [US1] 渲染上下文区域基础 UI（文件名 + 路径 + 不存在标记）in `modules/agent_chat/src/gui_tab.py`
- [ ] T011 [US1] 输入框聚焦联动：接收发送事件后将焦点移到输入框 in `modules/agent_chat/src/gui_tab.py`

**Checkpoint**: US1 独立可验收（右键发送 + 自动打开 + 显示上下文）。

---

## Phase 3: User Story 2 — Agent 利用上下文进行分析对话 (Priority: P2)

**Goal**: 发送消息时把活跃文件路径拼接到用户本轮消息尾部。

**Independent Test**: 有上下文时发送消息，LLM 请求包含路径；无上下文时不包含。

### Implementation for User Story 2

- [ ] T012 [US2] 在消息发送路径中注入“上下文拼接器”，将活跃路径拼接到用户本轮消息尾部 in `modules/agent_chat/src/gui_tab.py`
- [ ] T013 [US2] 统一多文件路径拼接格式（顺序稳定、换行分隔、无重复）in `modules/agent_chat/src/gui_tab.py`
- [ ] T014 [US2] 无活跃上下文时保持原始消息不变（不追加任何上下文文本）in `modules/agent_chat/src/gui_tab.py`
- [ ] T015 [US2] 会话切换时恢复该会话上下文列表并驱动 UI 重绘 in `modules/agent_chat/src/gui_tab.py`
- [ ] T016 [US2] 新建会话初始化为空上下文，不继承其他会话 in `modules/agent_chat/src/gui_tab.py`

**Checkpoint**: US2 独立可验收（注入正确 + 会话隔离生效）。

---

## Phase 4: User Story 3 — 管理已注入的上下文 (Priority: P2)

**Goal**: 支持单项删除（点击 `×` 或选中后 Backspace/Delete）。

**Independent Test**: 删除指定上下文后，仅该项消失，后续消息不含该路径。

### Implementation for User Story 3

- [ ] T017 [US3] 为每个上下文文件项增加 `×` 删除按钮并实现单项删除回调 in `modules/agent_chat/src/gui_tab.py`
- [ ] T018 [US3] 实现上下文文件项“选中态”与键盘事件处理（仅在列表焦点内响应）in `modules/agent_chat/src/gui_tab.py`
- [ ] T019 [US3] 实现 Backspace/Delete 快捷删除选中项 in `modules/agent_chat/src/gui_tab.py`
- [ ] T020 [US3] 删除后同步会话上下文状态并立即刷新 UI in `modules/agent_chat/src/gui_tab.py`
- [ ] T021 [US3] 删除最后一个上下文项时隐藏/降级上下文区域展示 in `modules/agent_chat/src/gui_tab.py`

**Checkpoint**: US3 独立可验收（两种删除交互 + 状态同步正确）。

---

## Phase 5: Polish & 验证

**Purpose**: 测试覆盖、回归验证、文档收口。

- [ ] T022 [P] 编写事件链路测试：右键发送后事件 payload 字段完整性校验 in `modules/perfetto_capture/tests/test_history_panel_send_to_agent.py`
- [ ] T023 [P] 编写 Agent 上下文状态测试：多文件去重、会话隔离、新会话空上下文 in `modules/agent_chat/tests/test_context_injection.py`
- [ ] T024 [P] 编写消息注入测试：有/无上下文两条路径 in `modules/agent_chat/tests/test_context_injection.py`
- [ ] T025 [P] 编写删除交互测试：`×` 删除、Backspace/Delete 删除、删除后注入内容更新 in `modules/agent_chat/tests/test_context_injection.py`
- [ ] T026 端到端手测执行 `quickstart.md` 全流程并记录结果（含 SC-001 耗时量化：记录“右键发送”到“上下文区域可见”的耗时，需 <=1s）in `specs/018-history-agent-context/quickstart.md`
- [ ] T027 编写跨消息保持测试：同一会话连续 3 条消息均注入活跃路径，删除后下一条消息不再注入 in `modules/agent_chat/tests/test_context_injection.py`
- [ ] T028 统一文档术语（“上下文区域”）并做最终一致性自检 in `specs/018-history-agent-context/spec.md` and `specs/018-history-agent-context/plan.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: 无依赖，先做
- **Phase 2 (US1)**: 依赖 Phase 1（事件和状态基础完成）
- **Phase 3 (US2)**: 依赖 Phase 2（先有上下文注入入口）
- **Phase 4 (US3)**: 依赖 Phase 2（有上下文项可管理）
- **Phase 5**: 依赖 Phase 2-4 完成

### User Story Dependencies

- **US1** 是 MVP，最先交付
- **US2** 与 **US3** 都依赖 US1，但二者可并行推进

### Parallel Opportunities

- T005/T006 可并行（同文件不同菜单分支）
- T015/T016 可并行（会话切换与新建路径）
- T022-T025 可并行（不同测试场景）

---

## Implementation Strategy

### MVP First (US1 Only)

1. 完成 Phase 1
2. 完成 US1（T005-T011）
3. 立即验证 SC-001/SC-002
4. 通过后再推进 US2/US3

### Incremental Delivery

1. 事件链路（US1）
2. 注入语义（US2）
3. 删除交互（US3）
4. 测试回归（Phase 5）
