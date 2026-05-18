# Feature Specification: UI 样式统一管理

**Feature Branch**: `017-ui-style-unification`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "UI样式统一管理：将模块级内联样式迁移到框架层全局QSS统一管理，消除硬编码颜色和重复的主题字典"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 主题切换全局一致 (Priority: P1)

作为工具使用者，我切换暗色/亮色主题时，所有模块的所有控件（包括下拉框、列表、树、进度条、滑块、菜单等）都应立即且完整地切换到对应主题样式，不出现颜色残留或不一致。

**Why this priority**: 主题切换一致性直接影响用户体验，不一致的颜色会让工具显得不专业。当前多个模块的内联样式未随主题切换更新，导致亮色模式下部分控件仍显示暗色样式。

**Independent Test**: 启动工具 → 切换到亮色主题 → 逐一检查所有模块 Tab 的控件外观是否正确 → 切换回暗色主题 → 再次检查。

**Acceptance Scenarios**:

1. **Given** 工具在暗色模式运行, **When** 用户切换到亮色主题, **Then** 所有模块的所有 QComboBox、QListWidget、QTreeWidget、QProgressBar、QSlider、QMenu、QTextBrowser 均显示亮色风格。
2. **Given** 工具在亮色模式运行, **When** 用户切换到暗色主题, **Then** 上述所有控件均显示暗色风格，无残留亮色元素。
3. **Given** 工具启动, **When** 直接使用默认暗色主题, **Then** 所有控件外观一致，无可见性差的控件。

---

### User Story 2 - 颜色体系集中管理 (Priority: P1)

作为开发者，我修改某个主题颜色（如强调色）时，只需在一处修改即可全局生效，而不是在多个模块的颜色字典中重复修改。

**Why this priority**: 当前 Catppuccin 调色板在 5 个文件中重复定义，任何颜色调整都需要同步多处，容易遗漏导致不一致。

**Independent Test**: 修改集中颜色定义中的 `accent` 值 → 重启工具 → 检查所有使用强调色的位置是否统一生效。

**Acceptance Scenarios**:

1. **Given** 颜色常量集中定义在一个文件中, **When** 开发者修改暗色主题的 `accent` 颜色值, **Then** 所有模块中引用该颜色的位置都使用新值。
2. **Given** 各模块之前有独立的颜色字典, **When** 迁移完成后, **Then** 各模块不再有自己的 `_THEME_COLORS` / `_THEMES` 字典定义，统一引用共享模块。

---

### User Story 3 - 通用控件样式框架管理 (Priority: P2)

作为开发者，我在任何模块中使用 QComboBox、QListWidget、QTreeWidget 等通用控件时，无需手动设置样式即可获得与整体主题一致的外观。

**Why this priority**: 当前框架层全局 QSS 未覆盖这些常用控件，模块开发者必须自行添加内联样式才能让控件在暗色模式下可用，增加了开发负担和不一致风险。

**Independent Test**: 在任意模块中新建一个 QComboBox → 不设置任何样式 → 启动工具 → 检查该 QComboBox 在暗色/亮色模式下是否有合理的默认外观。

**Acceptance Scenarios**:

1. **Given** 全局 QSS 已覆盖 QComboBox, **When** 模块新建一个 QComboBox 不设置任何样式, **Then** 该 QComboBox 在暗色模式下背景为深色、文字为浅色、边框可见。
2. **Given** 全局 QSS 已覆盖 QListWidget, **When** 模块新建一个 QListWidget, **Then** 选中项和悬停项有明确的视觉反馈。

---

### User Story 4 - 消除模块内联样式冗余 (Priority: P2)

作为开发者，模块代码中的 `setStyleSheet` 调用应尽量减少，特别是静态样式应由框架层全局 QSS 统一管理，模块只保留真正需要动态切换的内联样式。

**Why this priority**: agent_chat 有 63 处 setStyleSheet 调用，其中大量是初始化时的静态样式与 set_theme() 中的重复。消除冗余可降低维护成本。

**Independent Test**: 对比迁移前后模块中的 setStyleSheet 调用数量 → 静态样式调用数应大幅减少。

**Acceptance Scenarios**:

1. **Given** agent_chat 模块迁移完成, **When** 统计 setStyleSheet 调用, **Then** 调用数从 63 减少至仅保留动态必要的（约 20 处以内）。
2. **Given** 初始化时设置的静态样式已迁移到全局 QSS, **When** set_theme() 被调用, **Then** 不再需要重复设置已由全局 QSS 管理的样式。

---

### User Story 5 - 统一主题切换机制 (Priority: P3)

作为开发者，所有 Tab 模块应有统一的 `set_theme()` 接口，框架层自动调用；模块仅在有动态样式（如 QPainter 绘制）时才需重写此方法。

**Why this priority**: 当前仅 agent_chat 和 device_disguise 实现了 set_theme()，其他模块的内联样式不随主题切换，导致亮色模式下部分模块外观异常。

**Independent Test**: 所有 Tab 均可接收 set_theme() 调用 → 无 AttributeError → 样式正确切换。

**Acceptance Scenarios**:

1. **Given** BaseTab 提供默认 set_theme() 方法, **When** MainWindow 切换主题, **Then** 所有 Tab 都收到主题变更通知，不抛出异常。
2. **Given** 某模块未重写 set_theme(), **When** 主题切换, **Then** 该模块的外观仍然正确（因为全局 QSS 已生效）。

---

### User Story 6 - 消除重复组件 (Priority: P3)

作为开发者，重复的 UI 组件（如 DialogCloseButton 在两处定义、日志着色逻辑在多个模块重复）应合并为共享组件。

**Why this priority**: 减少代码重复，降低维护负担，确保行为一致。

**Independent Test**: 搜索重复的组件定义 → 确认只剩一个权威实现 → 所有引用点使用该实现。

**Acceptance Scenarios**:

1. **Given** DialogCloseButton 在 toolkit_dialog.py 中定义, **When** 检查 llm_settings_dialog.py, **Then** 不再有独立的 _DialogCloseButton 实现，统一使用 toolkit_dialog.DialogCloseButton。
2. **Given** 日志着色逻辑提取为共享组件, **When** 多个模块需要日志着色, **Then** 统一引用共享组件而非各自实现。

---

### Edge Cases

- 全局 QSS 与模块内联样式冲突时，内联样式优先级更高（Qt QSS 特性），需确保不意外覆盖。
- 动态创建的消息 widget（如 agent_chat 的聊天气泡）在主题切换后是否需要更新样式。
- 模块特有的语义色（如 perfetto_capture 的绿色"开始抓取"按钮）不应被全局 QSS 覆盖。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 框架层 `styles.py` MUST 为 QComboBox、QListWidget/QListView、QTreeWidget/QTreeView、QProgressBar、QSlider、QMenu、QFrame、QTextBrowser 提供暗色和亮色两套全局默认样式。
- **FR-002**: MUST 新建共享颜色常量模块（`theme_colors.py`），集中定义 Catppuccin Mocha（暗色）和 Latte（亮色）调色板。
- **FR-003**: 各模块 MUST 删除自有的 `_THEME_COLORS` / `_THEMES` / `_DARK` 字典定义，统一从共享颜色常量导入。
- **FR-004**: 模块中的静态内联 `setStyleSheet` 调用 MUST 尽可能迁移到全局 QSS（通过 `objectName` 选择器）。
- **FR-005**: 模块中仅保留动态必要的 `setStyleSheet` 调用（状态切换、逐条创建的列表项等）。
- **FR-006**: `BaseTab` MUST 提供默认的 `set_theme(theme: str)` 方法，存储 `self._theme` 属性。
- **FR-007**: `MainWindow._propagate_theme()` MUST 确保所有已注册 Tab 都能接收主题变更。
- **FR-008**: `llm_settings_dialog.py` 中的 `_DialogCloseButton` MUST 删除，统一使用 `toolkit_dialog.DialogCloseButton`。
- **FR-009**: 日志着色逻辑 SHOULD 提取为共享组件 `toolkit/gui/log_widget.py`。
- **FR-010**: 所有变更 MUST NOT 改变现有 UI 的视觉外观（仅是实现方式的重构）。

### Key Entities

- **theme_colors.py**: 集中定义的主题颜色常量字典，包含暗色/亮色两套完整调色板。
- **styles.py (DARK_THEME / LIGHT_THEME)**: 框架层全局 QSS 字符串，覆盖所有通用控件和命名选择器。
- **BaseTab.set_theme()**: 统一的主题切换接口。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 切换亮色/暗色主题后，所有模块的所有通用控件（QComboBox、QListWidget、QTreeWidget、QProgressBar、QSlider、QMenu、QTextBrowser）外观完整切换，无可见性问题。
- **SC-002**: Catppuccin 调色板颜色定义仅存在于一处（`theme_colors.py`），各模块无自有颜色字典。
- **SC-003**: agent_chat 模块的 `setStyleSheet` 调用数从 63 减少到 25 以内。
- **SC-004**: 所有 Tab 模块均可响应 `set_theme()` 调用而不抛出异常。
- **SC-005**: 视觉外观与重构前保持一致，无回归变化。

## Assumptions

- 现有的 Qt QSS 机制（全局样式通过 `QApplication.setStyleSheet` 应用）能满足所有样式需求，不需要引入第三方主题库。
- 模块特有的语义色（如 perfetto_capture 的绿色按钮）通过 objectName 选择器在全局 QSS 中定义，不与通用按钮样式冲突。
- 动态创建的消息 widget 保留最少的内联样式是合理的，不要求 100% 消除内联样式。

## Clarifications

*(待 clarify 阶段填写)*
