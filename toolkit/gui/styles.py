"""GUI 样式表定义 — 暗色/亮色主题"""

DARK_THEME = """
/* 全局 — VS Code 风格字体 */
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 12px;
}

/* 标题栏 */
QWidget#titleBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
}

QLabel#titleLabel {
    color: #cba6f7;
    font-size: 14px;
    font-weight: bold;
    padding-left: 4px;
}

/* 窗口控制按钮 — VS Code 风格（paintEvent 绘制图标） */
QWidget#titleBar QPushButton#minBtn,
QWidget#titleBar QPushButton#maxBtn,
QWidget#titleBar QPushButton#closeBtn,
QPushButton#themeBtn,
QPushButton#settingsBtn {
    background-color: transparent;
    border: none;
    border-radius: 0;
}

QMenu#settingsMenu {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px;
}
QMenu#settingsMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
    color: #cdd6f4;
}
QMenu#settingsMenu::item:selected {
    background-color: #45475a;
}

/* LLM 设置对话框 — 无边框风格 */
QDialog#llmSettingsDialog {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 8px;
}
QWidget#llmDialogTitleBar {
    background-color: #181825;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QLabel#llmDialogTitle {
    color: #cdd6f4;
    font-weight: bold;
    font-size: 13px;
    background: transparent;
}
QPushButton#llmDialogCloseBtn {
    background: transparent;
    border: none;
    color: #a6adc8;
    font-size: 14px;
    border-radius: 4px;
}
QPushButton#llmDialogCloseBtn:hover {
    background: #f38ba8;
    color: #1e1e2e;
}
QWidget#llmDialogSeparator {
    background-color: #45475a;
}
QDialog#llmSettingsDialog QLabel {
    color: #cdd6f4;
}
QDialog#llmSettingsDialog QPushButton#providerBtn {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 16px;
    color: #cdd6f4;
    min-width: 72px;
}
QDialog#llmSettingsDialog QPushButton#providerBtn:checked {
    background-color: #cba6f7;
    color: #1e1e2e;
    border-color: #cba6f7;
}
QDialog#llmSettingsDialog QLineEdit#apiKeyEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cdd6f4;
}
QDialog#llmSettingsDialog QPushButton#apiKeyToggle {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    color: #cdd6f4;
    padding: 4px;
}
QDialog#llmSettingsDialog QComboBox#modelCombo {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cdd6f4;
}
QDialog#llmSettingsDialog QSlider::groove:horizontal {
    background: #313244;
    height: 4px;
    border-radius: 2px;
}
QDialog#llmSettingsDialog QSlider::handle:horizontal {
    background: #cba6f7;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QDialog#llmSettingsDialog QSpinBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 2px 4px;
    color: #cdd6f4;
}
QDialog#llmSettingsDialog QPushButton#llmSaveBtn {
    background-color: #cba6f7;
    color: #1e1e2e;
    border: none;
    border-radius: 4px;
    padding: 6px 20px;
    font-weight: bold;
}
QDialog#llmSettingsDialog QPushButton#llmSaveBtn:hover {
    background-color: #b490e0;
}
QDialog#llmSettingsDialog QPushButton#llmCancelBtn {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px 20px;
    color: #cdd6f4;
}

QComboBox#deviceCombo {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 2px 4px 2px 18px;
    color: #a6adc8;
    font-size: 11px;
}

QComboBox#deviceCombo QLineEdit {
    background-color: transparent;
    border: none;
    color: #a6adc8;
    font-size: 11px;
    padding-left: 4px;
}

QComboBox#deviceCombo::drop-down {
    border: none;
    width: 16px;
}

QComboBox#deviceCombo QAbstractItemView {
    background-color: #313244;
    border: 1px solid #45475a;
    color: #cdd6f4;
    font-size: 11px;
    selection-background-color: #585b70;
}

/* 左侧导航 */
QWidget#navPanel {
    background-color: #181825;
    border-right: 1px solid #313244;
}

QPushButton#navButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #bac2de;
    text-align: left;
    padding: 8px 12px;
    margin: 1px 4px;
    font-size: 13px;
}

QPushButton#navButton:hover {
    background-color: #313244;
    color: #cdd6f4;
}

QPushButton#navButton:checked {
    background-color: #45475a;
    color: #cba6f7;
    font-weight: bold;
}

/* 内容区 */
QStackedWidget {
    background-color: #1e1e2e;
}

/* 底部状态栏 */
QWidget#statusBar {
    background-color: #181825;
    border-top: 1px solid #313244;
}

QLabel#statusBarText {
    color: #a6adc8;
    font-size: 11px;
    background: transparent;
}

QLabel#llmTokenLabel {
    color: #a6adc8;
    font-size: 11px;
    background: transparent;
}
QLabel#llmModelLabel {
    color: #cba6f7;
    font-size: 11px;
    background: transparent;
    padding: 0 4px;
}
QLabel#llmModelLabel:hover {
    text-decoration: underline;
}
QMenu#modelSwitchMenu {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px;
}
QMenu#modelSwitchMenu::item {
    padding: 4px 20px;
    border-radius: 4px;
    color: #cdd6f4;
}
QMenu#modelSwitchMenu::item:selected {
    background-color: #45475a;
}

/* Splitter 拖拽手柄 */
QSplitter#bodySplitter::handle {
    background-color: #313244;
    width: 2px;
}

QSplitter#bodySplitter::handle:hover {
    background-color: #cba6f7;
}

/* 滚动条 — VS Code 风格 */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: rgba(121, 121, 121, 80);
    border-radius: 5px;
    min-height: 20px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: rgba(121, 121, 121, 160);
}

QScrollBar::handle:vertical:pressed {
    background-color: rgba(121, 121, 121, 200);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: rgba(121, 121, 121, 80);
    border-radius: 5px;
    min-width: 20px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: rgba(121, 121, 121, 160);
}

QScrollBar::handle:horizontal:pressed {
    background-color: rgba(121, 121, 121, 200);
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* Tab 控件 */
QTabWidget::pane {
    border: 1px solid #45475a;
    border-radius: 4px;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #313244;
    color: #a6adc8;
    border: 1px solid #45475a;
    border-bottom: none;
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border-bottom: 2px solid #89b4fa;
}
QTabBar::tab:hover:!selected {
    background-color: #45475a;
    color: #cdd6f4;
}

/* 通用按钮 */
QPushButton {
    background-color: #45475a;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    color: #cdd6f4;
}

QPushButton:hover {
    background-color: #585b70;
}

QPushButton:pressed {
    background-color: #313244;
}

/* 输入框 */
QLineEdit, QTextEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cdd6f4;
}

QLineEdit:focus, QTextEdit:focus {
    border-color: #cba6f7;
}

/* 表格 */
QTableWidget, QTableView {
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    border: 1px solid #313244;
    gridline-color: #313244;
    color: #cdd6f4;
}

QHeaderView::section {
    background-color: #181825;
    color: #a6adc8;
    border: none;
    border-bottom: 1px solid #313244;
    padding: 6px 8px;
    font-weight: bold;
}

/* 标签 */
QLabel {
    color: #cdd6f4;
}

/* 分组框 */
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
    color: #a6adc8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    padding: 0 8px;
}

/* 主要按钮 — 强调操作（保存/确认/发送） */
QPushButton#primaryBtn {
    background-color: #cba6f7;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 6px 20px;
    font-weight: bold;
}
QPushButton#primaryBtn:hover { background-color: #b490e0; }
QPushButton#primaryBtn:pressed { background-color: #a37dd0; }

/* 次要按钮 — 辅助操作（取消/关闭） */
QPushButton#secondaryBtn {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 20px;
    color: #cdd6f4;
}
QPushButton#secondaryBtn:hover { background-color: #45475a; }

/* 危险按钮 — 破坏性操作（删除） */
QPushButton#dangerBtn {
    background-color: transparent;
    border: 1px solid #f38ba8;
    border-radius: 6px;
    padding: 6px 20px;
    color: #f38ba8;
}
QPushButton#dangerBtn:hover { background-color: #f38ba8; color: #1e1e2e; }

/* 幽灵按钮 — 无背景无边框（列表内操作图标等） */
QPushButton#ghostBtn {
    background: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}

/* 停止按钮 */
QPushButton#stopBtn {
    background-color: #f38ba8;
    color: #1e1e2e;
    font-weight: bold;
}

QPushButton#stopBtn:hover {
    background-color: #eba0b3;
}

QPushButton#stopBtn:pressed {
    background-color: #d6738d;
}

QPushButton#stopBtn:disabled {
    background-color: #45475a;
    color: #6c7086;
}

/* 复选框 */
QCheckBox {
    spacing: 4px;
    color: #cdd6f4;
    background: transparent;
}

QCheckBox::indicator {
    width: 12px;
    height: 12px;
    border: 1px solid #585b70;
    border-radius: 2px;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #cba6f7;
    border-color: #cba6f7;
}

QCheckBox::indicator:hover {
    border-color: #cba6f7;
}

/* 数值输入框 */
QSpinBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 3px 24px 3px 6px;
    color: #cdd6f4;
    min-height: 22px;
}

QSpinBox:focus {
    border-color: #cba6f7;
}

QSpinBox:disabled {
    color: #6c7086;
    background-color: #1e1e2e;
}

QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    background-color: #45475a;
    border: none;
    border-left: 1px solid #313244;
    border-top-right-radius: 3px;
}

QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    background-color: #45475a;
    border: none;
    border-left: 1px solid #313244;
    border-bottom-right-radius: 3px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #585b70;
}

QSpinBox::up-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #cdd6f4;
}

QSpinBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #cdd6f4;
}

QSpinBox::up-arrow:disabled, QSpinBox::down-arrow:disabled {
    border-bottom-color: #6c7086;
    border-top-color: #6c7086;
}

/* 下拉框 */
QComboBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 24px 4px 8px;
    color: #cdd6f4;
    min-height: 22px;
}
QComboBox:hover { border-color: #585b70; }
QComboBox:focus { border-color: #cba6f7; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 20px;
    border: none;
}
QComboBox::down-arrow {
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #a6adc8;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    border: 1px solid #45475a;
    color: #cdd6f4;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
    outline: none;
}
QComboBox QAbstractItemView::item { padding: 4px 8px; }
QComboBox QAbstractItemView::item:hover { background-color: #45475a; }

/* 列表控件 */
QListWidget, QListView {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    color: #cdd6f4;
    outline: none;
}
QListWidget::item, QListView::item {
    padding: 4px 8px;
    border-radius: 4px;
}
QListWidget::item:selected, QListView::item:selected {
    background-color: #45475a;
    color: #cdd6f4;
}
QListWidget::item:hover:!selected, QListView::item:hover:!selected {
    background-color: #313244;
}

/* 树控件 */
QTreeWidget, QTreeView {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    color: #cdd6f4;
    outline: none;
    alternate-background-color: #181825;
}
QTreeWidget::item, QTreeView::item {
    padding: 3px 4px;
}
QTreeWidget::item:selected, QTreeView::item:selected {
    background-color: #45475a;
    color: #cdd6f4;
}
QTreeWidget::item:hover:!selected, QTreeView::item:hover:!selected {
    background-color: #313244;
}
QTreeWidget::branch:has-children:closed { border-image: none; image: none; }
QTreeWidget::branch:has-children:open { border-image: none; image: none; }

/* 进度条 */
QProgressBar {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
    min-height: 18px;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}

/* 滑块 */
QSlider::groove:horizontal {
    background: #313244;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #cba6f7;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #b490e0;
}

/* 通用菜单 */
QMenu {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
    color: #cdd6f4;
}
QMenu::item:selected {
    background-color: #45475a;
}
QMenu::separator {
    height: 1px;
    background-color: #45475a;
    margin: 4px 8px;
}

/* 分隔线 */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #45475a;
    max-height: 1px;
}

/* 文本浏览器 */
QTextBrowser {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
}

/* 滚动区域 */
QScrollArea {
    background-color: transparent;
    border: none;
}

/* ── Agent 智能助手模块 ── */
QWidget#agentLeftPanel {
    background-color: #1e1e2e;
    border-right: 1px solid #45475a;
}
QWidget#agentToolbar {
    background-color: #1e1e2e;
    border-bottom: 1px solid #45475a;
}
QLabel#agentLblTitle {
    color: #cba6f7;
    font-weight: bold;
    font-size: 13px;
    background: transparent;
}
QWidget#agentInputBar {
    border-top: 1px solid #45475a;
}
QPushButton#agentBtnNewConv {
    color: #cba6f7;
    border: 1px solid #45475a;
    border-radius: 4px;
    font-size: 11px;
}
QPushButton#agentBtnSend {
    background-color: #cba6f7;
    color: #1e1e2e;
    border-radius: 8px;
    font-weight: bold;
    border: none;
}
QListWidget#agentConvList {
    background-color: transparent;
    border: none;
}
QListWidget#agentConvList::item {
    padding: 2px 0px;
    border-radius: 4px;
}
QListWidget#agentConvList::item:selected {
    background-color: transparent;
}
QListWidget#agentConvList::item:hover {
    background-color: transparent;
}
QScrollArea#agentMsgScroll {
    border: none;
    background: transparent;
}
QLabel#agentWelcomeTitle {
    color: #cba6f7;
    font-size: 20px;
    font-weight: bold;
    background: transparent;
}
QLabel#agentWelcomeSubtitle {
    color: #a6adc8;
    font-size: 13px;
    padding: 8px;
    background: transparent;
}
QLabel#agentWelcomeHint {
    color: #a6adc8;
    font-size: 11px;
    padding: 12px;
    background: transparent;
}
QPushButton#agentShortcutBtn {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 8px;
    font-size: 12px;
}
QLabel#agentHistLabel {
    font-weight: bold;
    font-size: 12px;
    background: transparent;
}
QTextEdit#agentChatInput {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px 10px;
    color: #cdd6f4;
    font-size: 13px;
}

/* ── 对话框内容标签 ── */
QLabel#dlgMsgLabel {
    font-size: 13px;
    padding: 8px 0;
}

/* ── Home Tab 模块 ── */
QLabel#homeWelcome {
    color: #cba6f7;
    font-size: 20px;
    font-weight: bold;
    background: transparent;
}
QLabel#homeSubtitle {
    color: #a6adc8;
    font-size: 13px;
    background: transparent;
}
QLabel#homeModulesTitle {
    font-size: 15px;
    font-weight: bold;
    margin-top: 8px;
    background: transparent;
}
QLabel#noModulesHint {
    color: #6c7086;
    font-style: italic;
    padding: 12px;
    background: transparent;
}
QFrame#moduleCard {
    border: 1px solid #313244;
    border-radius: 6px;
}
QFrame#moduleCard:hover {
    border-color: #45475a;
}
QLabel#moduleNameLabel {
    font-weight: bold;
    font-size: 13px;
    background: transparent;
}
QLabel#moduleVersionLabel {
    color: #a6adc8;
    font-size: 11px;
    background: transparent;
}
QLabel#moduleDescLabel {
    color: #6c7086;
    font-size: 12px;
    background: transparent;
}

/* ── Jank Panel 字体 ── */
QLabel#jankSectionLabel {
    font-size: 11px;
    font-weight: bold;
}
QPushButton#jankSmallBtn {
    font-size: 11px;
}
QLabel#jankCaptureLabel {
    font-size: 12px;
    font-weight: bold;
    color: #a6e3a1;
}

/* ── 通用字段标签 ── */
QLabel#fieldHint {
    font-size: 10px;
    font-style: italic;
}
QLabel#fieldLabel {
    font-size: 13px;
}

/* ── 配置对比树 ── */
QTreeWidget#gameperfDiffTree::item:selected,
QTreeWidget#gameperfDiffTree::item:selected:active {
    background-color: #585b70;
    color: #f5f5f5;
}
QTreeWidget#gameperfDiffTree::item:selected:!active {
    background-color: #45475a;
    color: #e8e8e8;
}
QTreeWidget#gameperfDiffTree::item:hover {
    background-color: #313244;
}

/* ── Analysis Chat ── */
QLabel#analysisChatHeader {
    font-weight: bold;
    font-size: 13px;
    background: transparent;
}
QTextBrowser#analysisChatDisplay {
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    color: #cdd6f4;
    padding: 8px;
    font-size: 13px;
}
QLineEdit#analysisChatInput {
    font-size: 13px;
}

/* ── History Panel ── */
QWidget#historyPanel {
    background: #313244;
    border-left: 3px solid #45475a;
}

/* ── Device Disguise ── */
QPushButton#profileSelectBtn {
    text-align: left;
    padding: 8px;
    border-radius: 4px;
    background: #313244;
    color: #cdd6f4;
}
QPushButton#profileSelectBtn:hover {
    background: #45475a;
}

/* ── Perfetto Analysis ── */
QPushButton#dimensionSelector {
    text-align: left;
    padding: 2px 6px;
}
QTextEdit#analysisLog {
    font-size: 11px;
}
QPushButton#dangerIconBtn {
    color: #e74c3c;
    background: transparent;
    border: none;
}
QPushButton#dangerIconBtn:hover {
    background-color: #e74c3c;
    color: white;
}

/* ── 面板布局切换按钮 ── */
QPushButton#navToggleBtn,
QPushButton#bottomToggleBtn,
QPushButton#rightToggleBtn {
    background-color: transparent;
    border: none;
    border-radius: 0;
}

/* ── 底部面板 ── */
QWidget#bottomPanel {
    background-color: #1e1e2e;
    border-top: 1px solid #45475a;
}
QWidget#bottomPanelHeader {
    background-color: #181825;
    border-bottom: 1px solid #313244;
}
QTabBar#logChannelBar {
    background: transparent;
    border: none;
}
QTabBar#logChannelBar::tab {
    background: transparent;
    color: #a6adc8;
    padding: 2px 10px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 11px;
}
QTabBar#logChannelBar::tab:selected {
    color: #cdd6f4;
    border-bottom: 2px solid #cba6f7;
}
QTabBar#logChannelBar::tab:hover {
    color: #cdd6f4;
}
QPushButton#logFilterBtn {
    background: #313244;
    color: #a6adc8;
    border: 1px solid #45475a;
    border-radius: 3px;
    padding: 1px 6px;
    font-size: 10px;
}
QPushButton#logFilterBtn:checked {
    background: #45475a;
    color: #cdd6f4;
    border-color: #cba6f7;
}
QPushButton#logClearBtn {
    background: transparent;
    border: none;
    color: #a6adc8;
    font-size: 12px;
}
QPushButton#logClearBtn:hover {
    color: #cdd6f4;
}
QTextEdit#bottomPanelLog {
    background-color: #1e1e2e;
    border: none;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
}

/* ── 右侧面板 ── */
QWidget#rightPanel {
    background-color: #1e1e2e;
    border-left: 1px solid #45475a;
}
QLabel#rightPanelPlaceholder {
    color: #6c7086;
    font-size: 12px;
}
"""

LIGHT_THEME = """
/* 全局 — 参考 VS Code Light+ 文字色 */
QWidget {
    background-color: #eff1f5;
    color: #333333;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 12px;
}

/* 标题栏 */
QWidget#titleBar {
    background-color: #e6e9ef;
    border-bottom: 1px solid #ccd0da;
}

QLabel#titleLabel {
    color: #8839ef;
    font-size: 14px;
    font-weight: bold;
    padding-left: 4px;
}

QWidget#titleBar QPushButton#minBtn,
QWidget#titleBar QPushButton#maxBtn,
QWidget#titleBar QPushButton#closeBtn,
QPushButton#themeBtn,
QPushButton#settingsBtn {
    background-color: transparent;
    border: none;
    border-radius: 0;
}

QMenu#settingsMenu {
    background-color: #eff1f5;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 4px;
}
QMenu#settingsMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
    color: #333333;
}
QMenu#settingsMenu::item:selected {
    background-color: #ccd0da;
}

/* LLM 设置对话框 — 浅色无边框 */
QDialog#llmSettingsDialog {
    background-color: #eff1f5;
    border: 1px solid #bcc0cc;
    border-radius: 8px;
}
QWidget#llmDialogTitleBar {
    background-color: #e6e9ef;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QLabel#llmDialogTitle {
    color: #333333;
    font-weight: bold;
    font-size: 13px;
    background: transparent;
}
QPushButton#llmDialogCloseBtn {
    background: transparent;
    border: none;
    color: #616161;
    font-size: 14px;
    border-radius: 4px;
}
QPushButton#llmDialogCloseBtn:hover {
    background: #d20f39;
    color: #ffffff;
}
QWidget#llmDialogSeparator {
    background-color: #bcc0cc;
}
QDialog#llmSettingsDialog QLabel {
    color: #333333;
}
QDialog#llmSettingsDialog QPushButton#providerBtn {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    padding: 4px 16px;
    color: #333333;
    min-width: 72px;
}
QDialog#llmSettingsDialog QPushButton#providerBtn:checked {
    background-color: #8839ef;
    color: #ffffff;
    border-color: #8839ef;
}
QDialog#llmSettingsDialog QLineEdit#apiKeyEdit {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    padding: 4px 8px;
    color: #333333;
}
QDialog#llmSettingsDialog QPushButton#apiKeyToggle {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    color: #333333;
    padding: 4px;
}
QDialog#llmSettingsDialog QComboBox#modelCombo {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    padding: 4px 8px;
    color: #333333;
}
QDialog#llmSettingsDialog QSlider::groove:horizontal {
    background: #bcc0cc;
    height: 4px;
    border-radius: 2px;
}
QDialog#llmSettingsDialog QSlider::handle:horizontal {
    background: #8839ef;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QDialog#llmSettingsDialog QSpinBox {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    padding: 2px 4px;
    color: #333333;
}
QDialog#llmSettingsDialog QPushButton#llmSaveBtn {
    background-color: #8839ef;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 20px;
    font-weight: bold;
}
QDialog#llmSettingsDialog QPushButton#llmSaveBtn:hover {
    background-color: #7030d0;
}
QDialog#llmSettingsDialog QPushButton#llmCancelBtn {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    padding: 6px 20px;
    color: #333333;
}

QComboBox#deviceCombo {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    padding: 2px 4px 2px 18px;
    color: #333333;
    font-size: 11px;
}

QComboBox#deviceCombo QLineEdit {
    background-color: transparent;
    border: none;
    color: #333333;
    font-size: 11px;
    padding-left: 4px;
}

QComboBox#deviceCombo::drop-down {
    border: none;
    width: 16px;
}

QComboBox#deviceCombo QAbstractItemView {
    background-color: #e6e9ef;
    border: 1px solid #bcc0cc;
    color: #333333;
    font-size: 11px;
    selection-background-color: #ccd0da;
}

/* 左侧导航 */
QWidget#navPanel {
    background-color: #e6e9ef;
    border-right: 1px solid #ccd0da;
}

QPushButton#navButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #444444;
    text-align: left;
    padding: 8px 12px;
    margin: 1px 4px;
    font-size: 13px;
}

QPushButton#navButton:hover {
    background-color: #ccd0da;
    color: #1a1a1a;
}

QPushButton#navButton:checked {
    background-color: #bcc0cc;
    color: #8839ef;
    font-weight: bold;
}

/* 内容区 */
QStackedWidget {
    background-color: #eff1f5;
}

/* 底部状态栏 */
QWidget#statusBar {
    background-color: #e6e9ef;
    border-top: 1px solid #ccd0da;
}

QLabel#statusBarText {
    color: #616161;
    font-size: 11px;
    background: transparent;
}

QLabel#llmTokenLabel {
    color: #616161;
    font-size: 11px;
    background: transparent;
}
QLabel#llmModelLabel {
    color: #8839ef;
    font-size: 11px;
    background: transparent;
    padding: 0 4px;
}
QLabel#llmModelLabel:hover {
    text-decoration: underline;
}
QMenu#modelSwitchMenu {
    background-color: #eff1f5;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 4px;
}
QMenu#modelSwitchMenu::item {
    padding: 4px 20px;
    border-radius: 4px;
    color: #333333;
}
QMenu#modelSwitchMenu::item:selected {
    background-color: #ccd0da;
}

/* Splitter 拖拽手柄 */
QSplitter#bodySplitter::handle {
    background-color: #ccd0da;
    width: 2px;
}

QSplitter#bodySplitter::handle:hover {
    background-color: #8839ef;
}

/* 滚动条 — VS Code 风格 */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: rgba(100, 100, 100, 60);
    border-radius: 5px;
    min-height: 20px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: rgba(100, 100, 100, 130);
}

QScrollBar::handle:vertical:pressed {
    background-color: rgba(100, 100, 100, 180);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: rgba(100, 100, 100, 60);
    border-radius: 5px;
    min-width: 20px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: rgba(100, 100, 100, 130);
}

QScrollBar::handle:horizontal:pressed {
    background-color: rgba(100, 100, 100, 180);
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* Tab 控件 */
QTabWidget::pane {
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    background-color: #eff1f5;
}
QTabBar::tab {
    background-color: #dce0e8;
    color: #6c6f85;
    border: 1px solid #bcc0cc;
    border-bottom: none;
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #eff1f5;
    color: #333333;
    border-bottom: 2px solid #1e66f5;
}
QTabBar::tab:hover:!selected {
    background-color: #ccd0da;
    color: #333333;
}

/* 通用按钮 */
QPushButton {
    background-color: #ccd0da;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    color: #333333;
}

QPushButton:hover {
    background-color: #bcc0cc;
}

QPushButton:pressed {
    background-color: #acb0be;
}

/* 输入框 */
QLineEdit, QTextEdit {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    padding: 4px 8px;
    color: #333333;
}

QLineEdit:focus, QTextEdit:focus {
    border-color: #8839ef;
}

/* 表格 */
QTableWidget, QTableView {
    background-color: #eff1f5;
    alternate-background-color: #e6e9ef;
    border: 1px solid #ccd0da;
    gridline-color: #ccd0da;
    color: #333333;
}

QHeaderView::section {
    background-color: #e6e9ef;
    color: #616161;
    border: none;
    border-bottom: 1px solid #ccd0da;
    padding: 6px 8px;
    font-weight: bold;
}

/* 标签 */
QLabel {
    color: #333333;
}

/* 分组框 */
QGroupBox {
    border: 1px solid #ccd0da;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
    color: #616161;
}

QGroupBox::title {
    subcontrol-origin: margin;
    padding: 0 8px;
}

/* 主要按钮 */
QPushButton#primaryBtn {
    background-color: #8839ef;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 20px;
    font-weight: bold;
}
QPushButton#primaryBtn:hover { background-color: #7030d0; }
QPushButton#primaryBtn:pressed { background-color: #5f28b8; }

/* 次要按钮 */
QPushButton#secondaryBtn {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 6px;
    padding: 6px 20px;
    color: #333333;
}
QPushButton#secondaryBtn:hover { background-color: #ccd0da; }

/* 危险按钮 */
QPushButton#dangerBtn {
    background-color: transparent;
    border: 1px solid #d20f39;
    border-radius: 6px;
    padding: 6px 20px;
    color: #d20f39;
}
QPushButton#dangerBtn:hover { background-color: #d20f39; color: #ffffff; }

/* 幽灵按钮 */
QPushButton#ghostBtn {
    background: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}

/* 停止按钮 */
QPushButton#stopBtn {
    background-color: #d20f39;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#stopBtn:hover {
    background-color: #e34063;
}

QPushButton#stopBtn:pressed {
    background-color: #b30d30;
}

QPushButton#stopBtn:disabled {
    background-color: #ccd0da;
    color: #9ca0b0;
}

/* 复选框 */
QCheckBox {
    spacing: 4px;
    color: #333333;
    background: transparent;
}

QCheckBox::indicator {
    width: 12px;
    height: 12px;
    border: 1px solid #acb0be;
    border-radius: 2px;
    background-color: #dce0e8;
}

QCheckBox::indicator:checked {
    background-color: #8839ef;
    border-color: #8839ef;
}

QCheckBox::indicator:hover {
    border-color: #8839ef;
}

/* 数值输入框 */
QSpinBox {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    padding: 3px 24px 3px 6px;
    color: #333333;
    min-height: 22px;
}

QSpinBox:focus {
    border-color: #8839ef;
}

QSpinBox:disabled {
    color: #9ca0b0;
    background-color: #e6e9ef;
}

QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    background-color: #ccd0da;
    border: none;
    border-left: 1px solid #bcc0cc;
    border-top-right-radius: 3px;
}

QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    background-color: #ccd0da;
    border: none;
    border-left: 1px solid #bcc0cc;
    border-bottom-right-radius: 3px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #bcc0cc;
}

QSpinBox::up-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #333333;
}

QSpinBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #333333;
}

QSpinBox::up-arrow:disabled, QSpinBox::down-arrow:disabled {
    border-bottom-color: #9ca0b0;
    border-top-color: #9ca0b0;
}

/* 下拉框 */
QComboBox {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    padding: 4px 24px 4px 8px;
    color: #333333;
    min-height: 22px;
}
QComboBox:hover { border-color: #acb0be; }
QComboBox:focus { border-color: #8839ef; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 20px;
    border: none;
}
QComboBox::down-arrow {
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #616161;
}
QComboBox QAbstractItemView {
    background-color: #eff1f5;
    border: 1px solid #bcc0cc;
    color: #333333;
    selection-background-color: #ccd0da;
    selection-color: #333333;
    outline: none;
}
QComboBox QAbstractItemView::item { padding: 4px 8px; }
QComboBox QAbstractItemView::item:hover { background-color: #ccd0da; }

/* 列表控件 */
QListWidget, QListView {
    background-color: #eff1f5;
    border: 1px solid #ccd0da;
    color: #333333;
    outline: none;
}
QListWidget::item, QListView::item {
    padding: 4px 8px;
    border-radius: 4px;
}
QListWidget::item:selected, QListView::item:selected {
    background-color: #ccd0da;
    color: #333333;
}
QListWidget::item:hover:!selected, QListView::item:hover:!selected {
    background-color: #dce0e8;
}

/* 树控件 */
QTreeWidget, QTreeView {
    background-color: #eff1f5;
    border: 1px solid #ccd0da;
    color: #333333;
    outline: none;
    alternate-background-color: #e6e9ef;
}
QTreeWidget::item, QTreeView::item {
    padding: 3px 4px;
}
QTreeWidget::item:selected, QTreeView::item:selected {
    background-color: #ccd0da;
    color: #333333;
}
QTreeWidget::item:hover:!selected, QTreeView::item:hover:!selected {
    background-color: #dce0e8;
}
QTreeWidget::branch:has-children:closed { border-image: none; image: none; }
QTreeWidget::branch:has-children:open { border-image: none; image: none; }

/* 进度条 */
QProgressBar {
    background-color: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    text-align: center;
    color: #333333;
    min-height: 18px;
}
QProgressBar::chunk {
    background-color: #1e66f5;
    border-radius: 3px;
}

/* 滑块 */
QSlider::groove:horizontal {
    background: #bcc0cc;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #8839ef;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #7030d0;
}

/* 通用菜单 */
QMenu {
    background-color: #eff1f5;
    border: 1px solid #bcc0cc;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
    color: #333333;
}
QMenu::item:selected {
    background-color: #ccd0da;
}
QMenu::separator {
    height: 1px;
    background-color: #bcc0cc;
    margin: 4px 8px;
}

/* 分隔线 */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #bcc0cc;
    max-height: 1px;
}

/* 文本浏览器 */
QTextBrowser {
    background-color: #eff1f5;
    border: 1px solid #ccd0da;
    color: #333333;
    selection-background-color: #ccd0da;
}

/* 滚动区域 */
QScrollArea {
    background-color: transparent;
    border: none;
}

/* ── Agent 智能助手模块 ── */
QWidget#agentLeftPanel {
    background-color: #eff1f5;
    border-right: 1px solid #ccd0da;
}
QWidget#agentToolbar {
    background-color: #eff1f5;
    border-bottom: 1px solid #ccd0da;
}
QLabel#agentLblTitle {
    color: #8839ef;
    font-weight: bold;
    font-size: 13px;
    background: transparent;
}
QWidget#agentInputBar {
    border-top: 1px solid #ccd0da;
}
QPushButton#agentBtnNewConv {
    color: #8839ef;
    border: 1px solid #ccd0da;
    border-radius: 4px;
    font-size: 11px;
}
QPushButton#agentBtnSend {
    background-color: #8839ef;
    color: #ffffff;
    border-radius: 8px;
    font-weight: bold;
    border: none;
}
QListWidget#agentConvList {
    background-color: transparent;
    border: none;
}
QListWidget#agentConvList::item {
    padding: 2px 0px;
    border-radius: 4px;
}
QListWidget#agentConvList::item:selected {
    background-color: transparent;
}
QListWidget#agentConvList::item:hover {
    background-color: transparent;
}
QScrollArea#agentMsgScroll {
    border: none;
    background: transparent;
}
QLabel#agentWelcomeTitle {
    color: #8839ef;
    font-size: 20px;
    font-weight: bold;
    background: transparent;
}
QLabel#agentWelcomeSubtitle {
    color: #6c6f85;
    font-size: 13px;
    padding: 8px;
    background: transparent;
}
QLabel#agentWelcomeHint {
    color: #6c6f85;
    font-size: 11px;
    padding: 12px;
    background: transparent;
}
QPushButton#agentShortcutBtn {
    background-color: #e6e9ef;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 8px;
    font-size: 12px;
}
QLabel#agentHistLabel {
    font-weight: bold;
    font-size: 12px;
    background: transparent;
}
QTextEdit#agentChatInput {
    background-color: #e6e9ef;
    border: 1px solid #ccd0da;
    border-radius: 8px;
    padding: 8px 10px;
    color: #4c4f69;
    font-size: 13px;
}

/* ── 对话框内容标签 ── */
QLabel#dlgMsgLabel {
    font-size: 13px;
    padding: 8px 0;
}

/* ── Home Tab 模块 ── */
QLabel#homeWelcome {
    color: #8839ef;
    font-size: 20px;
    font-weight: bold;
    background: transparent;
}
QLabel#homeSubtitle {
    color: #616161;
    font-size: 13px;
    background: transparent;
}
QLabel#homeModulesTitle {
    font-size: 15px;
    font-weight: bold;
    margin-top: 8px;
    background: transparent;
}
QLabel#noModulesHint {
    color: #888888;
    font-style: italic;
    padding: 12px;
    background: transparent;
}
QFrame#moduleCard {
    border: 1px solid #ccd0da;
    border-radius: 6px;
}
QFrame#moduleCard:hover {
    border-color: #bcc0cc;
}
QLabel#moduleNameLabel {
    font-weight: bold;
    font-size: 13px;
    background: transparent;
}
QLabel#moduleVersionLabel {
    color: #616161;
    font-size: 11px;
    background: transparent;
}
QLabel#moduleDescLabel {
    color: #888888;
    font-size: 12px;
    background: transparent;
}

/* ── Jank Panel 字体 ── */
QLabel#jankSectionLabel {
    font-size: 11px;
    font-weight: bold;
}
QPushButton#jankSmallBtn {
    font-size: 11px;
}
QLabel#jankCaptureLabel {
    font-size: 12px;
    font-weight: bold;
    color: #40a02b;
}

/* ── 通用字段标签 ── */
QLabel#fieldHint {
    font-size: 10px;
    font-style: italic;
}
QLabel#fieldLabel {
    font-size: 13px;
}

/* ── 配置对比树 ── */
QTreeWidget#gameperfDiffTree::item:selected,
QTreeWidget#gameperfDiffTree::item:selected:active {
    background-color: #bcc0cc;
    color: #4c4f69;
}
QTreeWidget#gameperfDiffTree::item:selected:!active {
    background-color: #ccd0da;
    color: #4c4f69;
}
QTreeWidget#gameperfDiffTree::item:hover {
    background-color: #e6e9ef;
}

/* ── Analysis Chat ── */
QLabel#analysisChatHeader {
    font-weight: bold;
    font-size: 13px;
    background: transparent;
}
QTextBrowser#analysisChatDisplay {
    background: #eff1f5;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    color: #4c4f69;
    padding: 8px;
    font-size: 13px;
}
QLineEdit#analysisChatInput {
    font-size: 13px;
}

/* ── History Panel ── */
QWidget#historyPanel {
    background: #e6e9ef;
    border-left: 3px solid #ccd0da;
}

/* ── Device Disguise ── */
QPushButton#profileSelectBtn {
    text-align: left;
    padding: 8px;
    border-radius: 4px;
    background: #e6e9ef;
    color: #4c4f69;
}
QPushButton#profileSelectBtn:hover {
    background: #ccd0da;
}

/* ── Perfetto Analysis ── */
QPushButton#dimensionSelector {
    text-align: left;
    padding: 2px 6px;
}
QTextEdit#analysisLog {
    font-size: 11px;
}
QPushButton#dangerIconBtn {
    color: #e74c3c;
    background: transparent;
    border: none;
}
QPushButton#dangerIconBtn:hover {
    background-color: #e74c3c;
    color: white;
}

/* ── 面板布局切换按钮 ── */
QPushButton#navToggleBtn,
QPushButton#bottomToggleBtn,
QPushButton#rightToggleBtn {
    background-color: transparent;
    border: none;
    border-radius: 0;
}

/* ── 底部面板 ── */
QWidget#bottomPanel {
    background-color: #eff1f5;
    border-top: 1px solid #ccd0da;
}
QWidget#bottomPanelHeader {
    background-color: #e6e9ef;
    border-bottom: 1px solid #ccd0da;
}
QTabBar#logChannelBar {
    background: transparent;
    border: none;
}
QTabBar#logChannelBar::tab {
    background: transparent;
    color: #6c6f85;
    padding: 2px 10px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 11px;
}
QTabBar#logChannelBar::tab:selected {
    color: #4c4f69;
    border-bottom: 2px solid #8839ef;
}
QTabBar#logChannelBar::tab:hover {
    color: #4c4f69;
}
QPushButton#logFilterBtn {
    background: #e6e9ef;
    color: #6c6f85;
    border: 1px solid #ccd0da;
    border-radius: 3px;
    padding: 1px 6px;
    font-size: 10px;
}
QPushButton#logFilterBtn:checked {
    background: #ccd0da;
    color: #4c4f69;
    border-color: #8839ef;
}
QPushButton#logClearBtn {
    background: transparent;
    border: none;
    color: #6c6f85;
    font-size: 12px;
}
QPushButton#logClearBtn:hover {
    color: #4c4f69;
}
QTextEdit#bottomPanelLog {
    background-color: #eff1f5;
    border: none;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
}

/* ── 右侧面板 ── */
QWidget#rightPanel {
    background-color: #eff1f5;
    border-left: 1px solid #ccd0da;
}
QLabel#rightPanelPlaceholder {
    color: #9ca0b0;
    font-size: 12px;
}
"""


def get_theme_stylesheet(theme: str = "dark") -> str:
    """获取主题样式表。"""
    return DARK_THEME if theme == "dark" else LIGHT_THEME
