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
QPushButton#themeBtn {
    background-color: transparent;
    border: none;
    border-radius: 0;
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
QPushButton#themeBtn {
    background-color: transparent;
    border: none;
    border-radius: 0;
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
"""


def get_theme_stylesheet(theme: str = "dark") -> str:
    """获取主题样式表。"""
    return DARK_THEME if theme == "dark" else LIGHT_THEME
