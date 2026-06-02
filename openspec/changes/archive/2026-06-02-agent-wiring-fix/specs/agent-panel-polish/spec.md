# Agent Panel Polish

AgentPanel 右侧面板的 UI 完整性：信号声明、拖拽调整宽度、会话选择器。

## ADDED Requirements

### Requirement: AgentPanel 声明标准信号

AgentPanel SHALL 声明 `panel_expanded`、`panel_collapsed`、`message_sent` 三个 pyqtSignal。

#### Scenario: 面板展开时发出信号

- **WHEN** 用户点击展开按钮或通过 title bar toggle 展开面板
- **THEN** `panel_expanded` 信号被 emit

#### Scenario: 面板折叠时发出信号

- **WHEN** 用户点击折叠按钮或通过 title bar toggle 关闭面板
- **THEN** `panel_collapsed` 信号被 emit

### Requirement: AgentPanel 支持拖拽调整宽度

AgentPanel SHALL 支持通过左边缘拖拽调整宽度，范围 240px 到 480px。

#### Scenario: 拖拽调整面板宽度

- **WHEN** 用户在面板左边缘按下鼠标并拖拽
- **THEN** 面板宽度跟随鼠标移动实时变化
- **AND** 宽度限制在 240px-480px 范围内

### Requirement: AgentPanel 提供会话选择器

AgentPanel SHALL 在标题栏下方提供会话历史下拉选择器和"新建会话"按钮。

#### Scenario: 选择历史会话

- **WHEN** 用户从下拉列表中选择一个已有会话
- **THEN** 消息区域加载该会话的历史消息

#### Scenario: 新建会话

- **WHEN** 用户点击"新建"按钮
- **THEN** 消息区域清空，当前会话 ID 置空
