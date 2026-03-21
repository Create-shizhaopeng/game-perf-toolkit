from PyQt6.QtWidgets import QApplication


DARK_THEME = """
QMainWindow, QDialog {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: 'Segoe UI', 'Microsoft YaHei';
}

QWidget {
    font-family: 'Segoe UI', 'Microsoft YaHei';
    color: #d4d4d4;
}

/* Title Bar */
#titleBar {
    background-color: #323233;
    border-bottom: 1px solid #3c3c3c;
}

#titleLabel {
    color: #d4d4d4;
    font-size: 13px;
    font-weight: 600;
}

#gearButton {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
    color: #cccccc;
    font-size: 14px;
    padding: 2px 6px;
}
#gearButton:hover {
    background-color: #505050;
}

/* Tab Widget */
#mainTabWidget::pane {
    border: none;
    background-color: #1e1e1e;
}
#mainTabWidget > QTabBar::tab {
    background-color: #2d2d2d;
    color: #858585;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    min-width: 120px;
}
#mainTabWidget > QTabBar::tab:selected {
    background-color: #1e1e1e;
    color: #d4d4d4;
    border-bottom: 2px solid #0e7ad3;
}
#mainTabWidget > QTabBar::tab:hover:!selected {
    background-color: #383838;
    color: #cccccc;
}
#mainTabWidget #tabBarCorner {
    background-color: #2d2d2d;
    border: none;
    border-bottom: 2px solid transparent;
}

/* Section Cards */
.sectionCard {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
}

/* 游戏性能：整体/模式策略区块 — 黑底 */
QFrame[class="strategyPolicySection"] {
    background-color: #0a0a0a;
    border: 1px solid #333333;
    border-radius: 6px;
}
QFrame[class="strategyPolicySection"] .sectionTitleBlue {
    color: #6cb2f0;
}
QFrame[class="strategyPolicySection"] .fieldLabel {
    color: #b0b0b0;
}
QScrollArea[class="strategyPolicyScroll"] {
    background-color: #0a0a0a;
    border: none;
}
QScrollArea[class="strategyPolicyScroll"] QAbstractScrollArea::viewport {
    background-color: #0a0a0a;
}
QWidget[class="strategyPolicyInner"] {
    background-color: #0a0a0a;
}
QFrame[class="strategyNodeBlock"] {
    background-color: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
}
QFrame[class="strategyNodeBlock"] .fieldLabel {
    color: #b0b0b0;
}
QFrame[class="strategyNodeBlock"] .sectionTitleBlue {
    color: #6cb2f0;
}
QFrame[class="strategyNodeBlock"] QPushButton#bindcoreDeleteXBtn {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    color: #f44747;
    font-size: 18px;
    font-weight: bold;
    padding: 0;
}
QFrame[class="strategyNodeBlock"] QPushButton#bindcoreDeleteXBtn:hover {
    background-color: #3c2a2a;
    color: #ff6b6b;
}

/* Section Titles */
.sectionTitleBlue {
    color: #569cd6;
    font-size: 12px;
    font-weight: 600;
}
.sectionTitleOrange {
    color: #ce9178;
    font-size: 12px;
    font-weight: 600;
}

/* Labels */
.fieldLabel {
    color: #858585;
    font-size: 12px;
}

/* Read-only display boxes */
.readonlyField {
    background-color: #1e1e1e;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
    color: #d4d4d4;
    font-size: 13px;
    padding: 0 12px;
}

/* Editable ComboBox */
QComboBox {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
    color: #d4d4d4;
    font-size: 13px;
    padding: 0 12px;
    min-height: 28px;
    max-height: 28px;
}
QComboBox:focus {
    border: 1px solid #007acc;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #858585;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    color: #d4d4d4;
    selection-background-color: #094771;
    selection-color: #ffffff;
}

/* Buttons */
#startButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0e7ad3, stop:1 #0062a3);
    border: none;
    border-radius: 4px;
    color: #ffffff;
    font-size: 14px;
    font-weight: 600;
    min-width: 140px;
    max-width: 140px;
    min-height: 36px;
    max-height: 36px;
}
#startButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a8ae3, stop:1 #0072b3);
}
#startButton:disabled {
    background-color: #3c3c3c;
    color: #858585;
    opacity: 0.5;
}

#clearButton {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    color: #d4d4d4;
    font-size: 14px;
    font-weight: 600;
    min-width: 140px;
    max-width: 140px;
    min-height: 36px;
    max-height: 36px;
}
#clearButton:hover {
    background-color: #505050;
    border-color: #666666;
}
#clearButton:disabled {
    background-color: #3c3c3c;
    color: #858585;
    opacity: 0.5;
}

#resetButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #c94a4a, stop:1 #a63d3d);
    border: none;
    border-radius: 4px;
    color: #ffffff;
    font-size: 14px;
    font-weight: 600;
    min-width: 140px;
    max-width: 140px;
    min-height: 36px;
    max-height: 36px;
}
#resetButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #d95a5a, stop:1 #b64d4d);
}
#resetButton:disabled {
    background-color: #3c3c3c;
    color: #858585;
    opacity: 0.5;
}

/* Quick-select star button */
#starButton {
    background-color: #0e639c;
    border: none;
    border-radius: 3px;
    color: #ffffff;
    font-size: 12px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    padding: 0;
}
#starButton:hover {
    background-color: #1177bb;
}

/* Badge */
.badgeGreen {
    background-color: #2d4f2d;
    color: #4ec94e;
    border-radius: 11px;
    font-size: 11px;
    padding: 2px 10px;
}
.badgeYellow {
    background-color: #fff3cd;
    color: #856404;
    border-radius: 11px;
    font-size: 11px;
    padding: 2px 10px;
}

/* Connection indicator */
.connectionDot {
    color: #4ec94e;
    font-size: 11px;
}

/* Log area */
#logArea {
    background-color: #1e1e1e;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
    color: #d4d4d4;
    font-family: 'Consolas', 'Microsoft YaHei';
    font-size: 12px;
    padding: 8px;
}

/* Progress bar */
QProgressBar {
    background-color: #3c3c3c;
    border: none;
    border-radius: 3px;
    text-align: center;
    color: #d4d4d4;
    font-size: 10px;
    min-height: 8px;
    max-height: 8px;
}
QProgressBar::chunk {
    background-color: #0e7ad3;
    border-radius: 3px;
}

/* Separator */
.separator {
    background-color: #3c3c3c;
    max-height: 1px;
    min-height: 1px;
}

/* ScrollBar */
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 8px;
}
QScrollBar::handle:vertical {
    background-color: #424242;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #555555;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* Device Popup */
#devicePopup {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    color: #d4d4d4;
}
#devicePopup QListWidget {
    background-color: #1e1e1e;
    border: 1px solid #3c3c3c;
    color: #d4d4d4;
}
#devicePopup QListWidget::item {
    color: #d4d4d4;
    padding: 4px 8px;
}
#devicePopup QListWidget::item:hover {
    background-color: #2a2d2e;
}
#devicePopup QListWidget::item:selected {
    background-color: #094771;
    color: #ffffff;
}
#devicePopup QLabel {
    color: #d4d4d4;
}

/* Menu */
QMenu {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    color: #d4d4d4;
    padding: 4px 0;
}
QMenu::item {
    padding: 6px 30px 6px 20px;
    color: #d4d4d4;
}
QMenu::item:selected {
    background-color: #094771;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background-color: #3c3c3c;
    margin: 4px 10px;
}

/* Dialog title bar */
#dialogTitleBar {
    background-color: #323233;
    border-bottom: 1px solid #3c3c3c;
}

/* Dialog input fields */
#dialogInput {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
    color: #d4d4d4;
    font-size: 13px;
    padding: 0 12px;
    min-height: 28px;
}
#dialogInput:focus {
    border: 1px solid #007acc;
}

/* Notes text area */
#notesInput {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
    color: #d4d4d4;
    font-size: 13px;
    padding: 8px 12px;
}
#notesInput:focus {
    border: 1px solid #007acc;
}

/* File input */
#fileInput {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
    color: #d4d4d4;
    font-size: 13px;
    padding: 0 12px;
}
#fileInput:focus {
    border: 1px solid #007acc;
}

/* Browse button */
#browseButton {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 3px;
    color: #d4d4d4;
    font-size: 12px;
}
#browseButton:hover {
    background-color: #505050;
    border-color: #666666;
}

/* Tooltip */
QToolTip {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    color: #d4d4d4;
    padding: 4px 8px;
    font-size: 12px;
}

/* MessageBox */
QMessageBox {
    background-color: #252526;
    color: #d4d4d4;
}
QMessageBox QLabel {
    color: #d4d4d4;
    font-size: 13px;
}
QMessageBox QPushButton {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    color: #d4d4d4;
    font-size: 13px;
    min-width: 80px;
    min-height: 28px;
    padding: 4px 16px;
}
QMessageBox QPushButton:hover {
    background-color: #505050;
}
QMessageBox QPushButton:default {
    background-color: #0e639c;
    border: none;
    color: #ffffff;
}
QMessageBox QPushButton:default:hover {
    background-color: #1177bb;
}

/* Game perf tab: config table (dark) */
#configTable {
    background-color: #1e1e1e;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
    color: #d4d4d4;
    gridline-color: #3c3c3c;
    font-size: 12px;
}
#configTable::item {
    background-color: #1e1e1e;
    color: #d4d4d4;
    padding: 4px 8px;
}
#configTable QHeaderView::section {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: none;
    border-bottom: 1px solid #3c3c3c;
    border-right: 1px solid #3c3c3c;
    padding: 6px 8px;
    font-weight: 600;
}
#configTable QTableCornerButton::section {
    background-color: #2d2d2d;
    border: none;
    border-bottom: 1px solid #3c3c3c;
    border-right: 1px solid #3c3c3c;
}
#configTable QLineEdit {
    color: #000000;
    background-color: #ffffff;
}
"""


LIGHT_THEME = """
QMainWindow, QDialog {
    background-color: #f3f3f3;
    color: #333333;
    font-family: 'Segoe UI', 'Microsoft YaHei';
}

QWidget {
    font-family: 'Segoe UI', 'Microsoft YaHei';
    color: #333333;
}

/* Title Bar */
#titleBar {
    background-color: #dddddd;
    border-bottom: 1px solid #e0e0e0;
}

#titleLabel {
    color: #333333;
    font-size: 13px;
    font-weight: 600;
}

#gearButton {
    background-color: #e8e8e8;
    border: 1px solid #cccccc;
    border-radius: 3px;
    color: #555555;
    font-size: 14px;
    padding: 2px 6px;
}
#gearButton:hover {
    background-color: #d0d0d0;
}

/* Tab Widget */
#mainTabWidget::pane {
    border: none;
    background-color: #f3f3f3;
}
#mainTabWidget > QTabBar::tab {
    background-color: #e8e8e8;
    color: #888888;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    min-width: 120px;
}
#mainTabWidget > QTabBar::tab:selected {
    background-color: #f3f3f3;
    color: #333333;
    border-bottom: 2px solid #0078d4;
}
#mainTabWidget > QTabBar::tab:hover:!selected {
    background-color: #d8d8d8;
    color: #555555;
}
#mainTabWidget #tabBarCorner {
    background-color: #e8e8e8;
    border: none;
    border-bottom: 2px solid transparent;
}

/* Section Cards */
.sectionCard {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
}

/* 游戏性能：整体/模式策略区块 — 黑底（浅色主题下仍用黑底） */
QFrame[class="strategyPolicySection"] {
    background-color: #0a0a0a;
    border: 1px solid #333333;
    border-radius: 6px;
}
QFrame[class="strategyPolicySection"] .sectionTitleBlue {
    color: #6cb2f0;
}
QFrame[class="strategyPolicySection"] .fieldLabel {
    color: #b0b0b0;
}
QScrollArea[class="strategyPolicyScroll"] {
    background-color: #0a0a0a;
    border: none;
}
QScrollArea[class="strategyPolicyScroll"] QAbstractScrollArea::viewport {
    background-color: #0a0a0a;
}
QWidget[class="strategyPolicyInner"] {
    background-color: #0a0a0a;
}
QFrame[class="strategyNodeBlock"] {
    background-color: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
}
QFrame[class="strategyNodeBlock"] .fieldLabel {
    color: #b0b0b0;
}
QFrame[class="strategyNodeBlock"] .sectionTitleBlue {
    color: #6cb2f0;
}
QFrame[class="strategyNodeBlock"] QPushButton#bindcoreDeleteXBtn {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    color: #d32f2f;
    font-size: 18px;
    font-weight: bold;
    padding: 0;
}
QFrame[class="strategyNodeBlock"] QPushButton#bindcoreDeleteXBtn:hover {
    background-color: #3a2222;
    color: #e53935;
}

/* Section Titles */
.sectionTitleBlue {
    color: #0066b8;
    font-size: 12px;
    font-weight: 600;
}
.sectionTitleOrange {
    color: #c05020;
    font-size: 12px;
    font-weight: 600;
}

/* Labels */
.fieldLabel {
    color: #888888;
    font-size: 12px;
}

/* Read-only display boxes */
.readonlyField {
    background-color: #f8f8f8;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    color: #333333;
    font-size: 13px;
    padding: 0 12px;
}

/* Editable ComboBox */
QComboBox {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 3px;
    color: #333333;
    font-size: 13px;
    padding: 0 12px;
    min-height: 28px;
    max-height: 28px;
}
QComboBox:focus {
    border: 1px solid #0078d4;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #888888;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    color: #333333;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}

/* Buttons */
#startButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0e7ad3, stop:1 #0062a3);
    border: none;
    border-radius: 4px;
    color: #ffffff;
    font-size: 14px;
    font-weight: 600;
    min-width: 140px;
    max-width: 140px;
    min-height: 36px;
    max-height: 36px;
}
#startButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a8ae3, stop:1 #0072b3);
}
#startButton:disabled {
    background-color: #cccccc;
    color: #888888;
}

#clearButton {
    background-color: #e8e8e8;
    border: 1px solid #cccccc;
    border-radius: 4px;
    color: #333333;
    font-size: 14px;
    font-weight: 600;
    min-width: 140px;
    max-width: 140px;
    min-height: 36px;
    max-height: 36px;
}
#clearButton:hover {
    background-color: #d0d0d0;
    border-color: #aaaaaa;
}
#clearButton:disabled {
    background-color: #e8e8e8;
    color: #aaaaaa;
}

#resetButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #c94a4a, stop:1 #a63d3d);
    border: none;
    border-radius: 4px;
    color: #ffffff;
    font-size: 14px;
    font-weight: 600;
    min-width: 140px;
    max-width: 140px;
    min-height: 36px;
    max-height: 36px;
}
#resetButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #d95a5a, stop:1 #b64d4d);
}
#resetButton:disabled {
    background-color: #cccccc;
    color: #888888;
}

/* Quick-select star button */
#starButton {
    background-color: #0e639c;
    border: none;
    border-radius: 3px;
    color: #ffffff;
    font-size: 12px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    padding: 0;
}
#starButton:hover {
    background-color: #1177bb;
}

/* Badge */
.badgeGreen {
    background-color: #d4edda;
    color: #28a745;
    border-radius: 11px;
    font-size: 11px;
    padding: 2px 10px;
}
.badgeYellow {
    background-color: #fff3cd;
    color: #856404;
    border-radius: 11px;
    font-size: 11px;
    padding: 2px 10px;
}

/* Connection indicator */
.connectionDot {
    color: #28a745;
    font-size: 11px;
}

/* Log area */
#logArea {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    color: #333333;
    font-family: 'Consolas', 'Microsoft YaHei';
    font-size: 12px;
    padding: 8px;
}

/* Game perf tab: config table */
#configTable {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    color: #333333;
    gridline-color: #e0e0e0;
    font-size: 12px;
}
#configTable::item {
    background-color: #ffffff;
    color: #333333;
    padding: 4px 8px;
}
#configTable QHeaderView::section {
    background-color: #f3f3f3;
    color: #333333;
    border: none;
    border-bottom: 1px solid #e0e0e0;
    border-right: 1px solid #e0e0e0;
    padding: 6px 8px;
    font-weight: 600;
}
#configTable QTableCornerButton::section {
    background-color: #f3f3f3;
    border: none;
    border-bottom: 1px solid #e0e0e0;
    border-right: 1px solid #e0e0e0;
}
#configTable QLineEdit {
    color: #333333;
    background-color: #ffffff;
}

/* Progress bar */
QProgressBar {
    background-color: #e0e0e0;
    border: none;
    border-radius: 3px;
    text-align: center;
    color: #333333;
    font-size: 10px;
    min-height: 8px;
    max-height: 8px;
}
QProgressBar::chunk {
    background-color: #0e7ad3;
    border-radius: 3px;
}

/* Separator */
.separator {
    background-color: #e0e0e0;
    max-height: 1px;
    min-height: 1px;
}

/* ScrollBar */
QScrollBar:vertical {
    background-color: #f3f3f3;
    width: 8px;
}
QScrollBar::handle:vertical {
    background-color: #c1c1c1;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #a8a8a8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* Device Popup */
#devicePopup {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    color: #333333;
}
#devicePopup QListWidget {
    background-color: #f8f8f8;
    border: 1px solid #e0e0e0;
    color: #333333;
}
#devicePopup QListWidget::item {
    color: #333333;
    padding: 4px 8px;
}
#devicePopup QListWidget::item:hover {
    background-color: #e8e8e8;
}
#devicePopup QListWidget::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}
#devicePopup QLabel {
    color: #333333;
}

/* Menu */
QMenu {
    background-color: #f3f3f3;
    border: 1px solid #e0e0e0;
    color: #333333;
    padding: 4px 0;
}
QMenu::item {
    padding: 6px 30px 6px 20px;
    color: #333333;
}
QMenu::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background-color: #e0e0e0;
    margin: 4px 10px;
}

/* Dialog title bar */
#dialogTitleBar {
    background-color: #dddddd;
    border-bottom: 1px solid #e0e0e0;
}

/* Dialog input fields */
#dialogInput {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 3px;
    color: #333333;
    font-size: 13px;
    padding: 0 12px;
    min-height: 28px;
}
#dialogInput:focus {
    border: 1px solid #0078d4;
}

/* Notes text area */
#notesInput {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 3px;
    color: #333333;
    font-size: 13px;
    padding: 8px 12px;
}
#notesInput:focus {
    border: 1px solid #0078d4;
}

/* File input */
#fileInput {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 3px;
    color: #333333;
    font-size: 13px;
    padding: 0 12px;
}
#fileInput:focus {
    border: 1px solid #0078d4;
}

/* Browse button */
#browseButton {
    background-color: #e8e8e8;
    border: 1px solid #cccccc;
    border-radius: 3px;
    color: #333333;
    font-size: 12px;
}
#browseButton:hover {
    background-color: #d0d0d0;
    border-color: #aaaaaa;
}

/* Tooltip */
QToolTip {
    background-color: #f3f3f3;
    border: 1px solid #e0e0e0;
    color: #333333;
    padding: 4px 8px;
    font-size: 12px;
}

/* MessageBox */
QMessageBox {
    background-color: #ffffff;
    color: #333333;
}
QMessageBox QLabel {
    color: #333333;
    font-size: 13px;
}
QMessageBox QPushButton {
    background-color: #e8e8e8;
    border: 1px solid #cccccc;
    border-radius: 4px;
    color: #333333;
    font-size: 13px;
    min-width: 80px;
    min-height: 28px;
    padding: 4px 16px;
}
QMessageBox QPushButton:hover {
    background-color: #d0d0d0;
}
QMessageBox QPushButton:default {
    background-color: #0e639c;
    border: none;
    color: #ffffff;
}
QMessageBox QPushButton:default:hover {
    background-color: #1177bb;
}
"""


def get_dark_theme() -> str:
    return DARK_THEME


def get_light_theme() -> str:
    return LIGHT_THEME


def apply_theme(app: QApplication, name: str):
    if name == "light":
        app.setStyleSheet(LIGHT_THEME)
    else:
        app.setStyleSheet(DARK_THEME)
