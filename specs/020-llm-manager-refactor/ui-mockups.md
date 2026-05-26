# UI Mockups: LLM Manager 模块重构

**Created**: 2026-05-25
**Updated**: 2026-05-26（实现中简化：ProviderManageDialog → 直接打开 JSON 文件编辑）
**Feature**: [spec.md](spec.md)

所有颜色来自 `toolkit/gui/theme_colors.py` 暗色主题（Catppuccin Mocha）。
所有图标使用 `toolkit/gui/codicons.py` codicon 字体，禁止 Unicode Emoji。
所有新控件 `objectName` 遵循项目命名规范，新增样式写入 `toolkit/gui/styles.py`。

---

## 1. LLM 设置对话框（精简后 — 最终版）

```
┌──────────────────────────────────────────────────────────────┐
│  #llmSettingsDialog  bg=#1e1e2e  border=1px #45475a        │
│  border-radius=8px  width=440  height≈320                   │
│                                                              │
│  ┌─ Title Bar (36px) ────────────────────────────────────┐  │
│  │  "LLM 模型设置"                [chrome-close]          │  │
│  │  color=#cdd6f4  font=13px bold  codicon 14px          │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ Body  padding=20  spacing=12 ────────────────────────┐ │
│  │                                                        │ │
│  │   Label(72px right-align)     Input(stretch)           │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  Provider:   [GLM (智谱)                   ▾]    │  │ │
│  │  │              #llmProviderCombo  fixed-height=28  │  │ │
│  │  │              QComboBox  color=#cdd6f4            │  │ │
│  │  │                                                  │  │ │
│  │  │  Model:      [glm-4-plus                   ▾]    │  │ │
│  │  │              #llmModelCombo  fixed-height=28     │  │ │
│  │  │              QComboBox  [1M]/[200K]/[128K] 标签  │  │ │
│  │  │                                                  │  │ │
│  │  │  Base URL:   [____________________________]     │  │ │
│  │  │              #llmUrlEdit  fixed-height=28        │  │ │
│  │  │              placeholder="留空使用默认地址"       │  │ │
│  │  │                                                  │  │ │
│  │  │  API Key:    [****************************]     │  │ │
│  │  │              #llmApiKeyEdit  fixed-height=28     │  │ │
│  │  │              EchoMode=Password                   │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │                                                        │ │
│  │  [✓] 启用扩展思考  #thinkingCheck                      │ │
│  │  (仅 provider.thinking=true 时显示)                     │ │
│  │                                                        │ │
│  │  [管理 Provider...]          [取消]  [保存]            │ │
│  │  #manageProviderBtn          #secondaryBtn #primaryBtn │ │
│  │  color=#a6adc8  hover下划线  font-size=12px            │ │
│  │  → 打开 llm_providers.json 系统编辑器                   │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

> **简化说明**: 「管理 Provider」按钮从打开复杂 GUI 对话框改为 `os.startfile()` 直接打开 `data/config/llm_providers.json` 用系统默认编辑器编辑。保存后点击设置面板「保存」按钮自动重载。

### 最终 QSS 参数

所有输入控件统一高度：`padding: 2px 8px; min-height: 22px; max-height: 28px`

---

## 2. Provider 管理 — 已简化 (superseded)

> 原设计为此处复杂的 ProviderManageDialog。实际实现中简化为直接编辑 JSON 配置文件。
> 见第 1 节「管理 Provider」按钮说明。

```
┌─────────────────────────────────────────────────────────────────┐
│  #providerManageDialog  bg=#1e1e2e  border=1px #45475a        │
│  border-radius=8px  width=520  min-height=400                  │
│                                                                 │
│  ┌─ Title Bar (36px) ─────────────────────────────────────────┐ │
│  │  "管理 LLM Provider"                [chrome-close]          │ │
│  │  color=#cdd6f4  font=13px bold       codicon 14px          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─ Body  padding=(20,16,20,16)  spacing=12  ─────────────────┐ │
│  │                                                             │ │
│  │  ┌─ Provider List (QListWidget) ──────────────────────────┐ │ │
│  │  │  #providerListWidget                                   │ │ │
│  │  │  bg=#181825  border=1px #45475a  border-radius=6px    │ │ │
│  │  │  padding=4px  min-height=160                           │ │ │
│  │  │                                                         │ │ │
│  │  │  ┌──────────────────────────────────────────────────┐  │ │ │
│  │  │  │  check  GLM (智谱)                     edit  ▸  │  │ │ │
│  │  │  │  codicon  color=#a6e3a1                codicon  │  │ │ │
│  │  │  │  #a6e3a1  font-size=12px               #a6adc8  │  │ │ │
│  │  │  │  (启用)                                  hover   │  │ │ │
│  │  │  │  bg=#313244  border-radius=4px          #cdd6f4  │  │ │ │
│  │  │  │  margin=2px                                       │  │ │ │
│  │  │  ├──────────────────────────────────────────────────┤  │ │ │
│  │  │  │  check  Claude (Anthropic)              edit  ▸  │  │ │ │
│  │  │  │  #a6e3a1                                         │  │ │ │
│  │  │  ├──────────────────────────────────────────────────┤  │ │ │
│  │  │  │  circle-slash  DeepSeek                 edit  ▸  │  │ │ │
│  │  │  │  #6c7086       (已禁用)                          │  │ │ │
│  │  │  └──────────────────────────────────────────────────┘  │ │ │
│  │  └─────────────────────────────────────────────────────────┘  │ │
│  │                                                             │ │
│  │  [+ 添加 Provider  (add codicon)]                           │ │
│  │   #ghostBtn  color=#a6adc8  font-size=12px                 │ │
│  │                                                             │ │
│  │  ┌─ Separator  border-top=1px #313244 ───────────────────┐ │ │
│  │  └───────────────────────────────────────────────────────┘  │ │
│  │                                                             │ │
│  │  ┌─ Edit Panel (选中 Provider 后显示) ────────────────────┐ │ │
│  │  │  #providerEditPanel  bg=#181825                        │ │ │
│  │  │  border=1px #313244  border-radius=6px                  │ │ │
│  │  │  padding=12px  spacing=10                               │ │ │
│  │  │                                                         │ │ │
│  │  │  "ID:"     [____________]  "名称:"  [____________]     │ │ │
│  │  │  QLabel     #providerIdEdit    QLabel   #providerNameEdit│ │ │
│  │  │  color=      QLineEdit         color=    QLineEdit      │ │ │
│  │  │  #a6adc8     min-width=120     #a6adc8   min-width=160 │ │ │
│  │  │  font=12px   font-size=12px    font=12px  font-size=12px│ │ │
│  │  │                                                         │ │ │
│  │  │  "Base URL:"  [________________________________]       │ │ │
│  │  │  QLabel        #providerUrlEdit                        │ │ │
│  │  │  color=#a6adc8  QLineEdit  font-size=12px              │ │ │
│  │  │  font=12px      placeholder="留空使用默认地址"           │ │ │
│  │  │                                                         │ │ │
│  │  │  "Prefix:"  [____]   "API Key:"  [****]  [eye-closed]  │ │ │
│  │  │  QLabel     #prefixEdit  QLabel     #apiKeyEdit         │ │ │
│  │  │  color=     QLineEdit    color=     QLineEdit           │ │ │
│  │  │  #a6adc8    font=12px    #a6adc8    EchoMode=Password   │ │ │
│  │  │  font=12px  width=80     font=12px  切换按钮 codicon    │ │ │
│  │  │                                                         │ │ │
│  │  │  [✓] 启用扩展思考  thinking_budget: [4000]             │ │ │
│  │  │  QCheckBox         QSpinBox                            │ │ │
│  │  │  #thinkingEdit      min=1024  max=64000  step=1000     │ │ │
│  │  │  color=#cdd6f4      width=80                          │ │ │
│  │  │  font-size=12px     font-size=12px                     │ │ │
│  │  │                                                         │ │ │
│  │  │  ┌─ Models Section ──────────────────────────────────┐ │ │ │
│  │  │  │  "Models:"                                         │ │ │ │
│  │  │  │  QLabel  color=#a6adc8  font-size=12px bold       │ │ │ │
│  │  │  │                                                    │ │ │ │
│  │  │  │  ┌──────────────────────────────────────────────┐ │ │ │ │
│  │  │  │  │  model-name     context_window    trash  ▸   │ │ │ │ │
│  │  │  │  │  #modelNameEdit  #contextEdit      codicon   │ │ │ │ │
│  │  │  │  │  QLineEdit       QSpinBox          #6c7086   │ │ │ │ │
│  │  │  │  │  font-size=12px  min=1024          hover     │ │ │ │ │
│  │  │  │  │  width=160       max=2000000       #f38ba8   │ │ │ │ │
│  │  │  │  │                 step=32000                   │ │ │ │ │
│  │  │  │  ├──────────────────────────────────────────────┤ │ │ │ │
│  │  │  │  │  claude-opus-4-7  1000000            trash   │ │ │ │ │
│  │  │  │  │  ...                                       │ │ │ │ │
│  │  │  │  └──────────────────────────────────────────────┘ │ │ │ │
│  │  │  │                                                    │ │ │ │
│  │  │  │  [+ 添加模型  (add codicon)]                      │ │ │ │
│  │  │  │   #ghostBtn  color=#a6adc8  font-size=11px       │ │ │ │
│  │  │  └────────────────────────────────────────────────────┘ │ │ │
│  │  │                                                         │ │ │
│  │  │  "默认模型:"  [glm-4-plus           ▾]                 │ │ │
│  │  │  QLabel       #defaultModelCombo                       │ │ │
│  │  │  color=#a6adc8 从 models 列表动态生成                   │ │ │
│  │  │  font=12px    font-size=12px                            │ │ │
│  │  │                                                         │ │ │
│  │  │  [保存修改]              [删除此 Provider]              │ │ │
│  │  │  #primaryBtn              #dangerBtn                   │ │ │
│  │  │  color=#cdd6f4           color=#f38ba8                │ │ │
│  │  │  bg=#cba6f7              bg=transparent               │ │ │
│  │  │  min-width=80            border=1px #f38ba8           │ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  │                                                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 涉及字符串常量（新增到 `modules/llm_manager/src/strings_gui.py`）

```python
DLG_TITLE_MANAGE_PROVIDER: Final = "管理 LLM Provider"
BTN_ADD_PROVIDER: Final = "添加 Provider"
BTN_SAVE_CHANGES: Final = "保存修改"
BTN_DELETE_PROVIDER: Final = "删除此 Provider"
LABEL_ID: Final = "ID:"
LABEL_NAME: Final = "名称:"
LABEL_BASE_URL: Final = "Base URL:"
LABEL_PREFIX: Final = "Prefix:"
LABEL_API_KEY: Final = "API Key:"
LABEL_MODELS: Final = "Models:"
LABEL_DEFAULT_MODEL: Final = "默认模型:"
LABEL_CONTEXT_WINDOW: Final = "context_window"
LABEL_THINKING_BUDGET: Final = "thinking_budget:"
PLACEHOLDER_BASE_URL: Final = "留空使用默认地址"
BTN_ADD_MODEL: Final = "添加模型"
DLG_DELETE_PROVIDER_TITLE: Final = "删除 Provider"
DLG_DELETE_PROVIDER_MSG_FMT: Final = "确定要删除 Provider \"{name}\" 吗？此操作不可撤销。"
DLG_DELETE_PROVIDER_CONFIRM: Final = "删除"
DLG_NO_MODEL_WARN: Final = "未配置模型"
```

### 涉及 QSS（`toolkit/gui/styles.py` 新增）

```css
/* Provider 管理对话框 */
QDialog#providerManageDialog {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 8px;
}

/* Provider 列表 */
QListWidget#providerListWidget {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}
QListWidget#providerListWidget::item {
    background-color: #313244;
    border-radius: 4px;
    margin: 2px;
    padding: 6px 10px;
    color: #cdd6f4;
}
QListWidget#providerListWidget::item:hover {
    background-color: #45475a;
}

/* 编辑面板 */
QWidget#providerEditPanel {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
}

/* 编辑区域子控件 */
QLineEdit#providerIdEdit,
QLineEdit#providerNameEdit,
QLineEdit#providerUrlEdit,
QLineEdit#prefixEdit,
QLineEdit#apiKeyEdit,
QLineEdit#modelNameEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    color: #cdd6f4;
    font-size: 12px;
    padding: 4px 8px;
}

QSpinBox#contextEdit,
QSpinBox#thinkingBudgetEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    color: #cdd6f4;
    font-size: 12px;
    padding: 4px 8px;
}
```

---

## 3. 底部状态栏 — LLM 上下文显示（精简后）

```
┌─ Status Bar (24px)  #statusBar ──────────────────────────────────────────┐
│  bg=#181825  border-top=1px #313244                                     │
│  padding=(12,0,12,0)  spacing=12                                        │
│                                                                          │
│  ┌─ Left ────────────────────────┐  ┌─ Center Stretch ─┐  ┌─ Right ───┐ │
│  │                               │  │                    │  │           │ │
│  │ "就绪"                        │  │                    │  │ v0.1.0    │ │
│  │ #statusBarText                │  │                    │  │           │ │
│  │ color=#a6adc8  font=11px     │  │                    │  │           │ │
│  │                               │  │                    │  │           │ │
│  └───────────────────────────────┘  └────────────────────┘  │           │ │
│                                                              │           │ │
│                                 ┌─ LLM Status Widget ────────┤           │ │
│                                 │  spacing=6                │           │ │
│                                 │                           │           │ │
│                                 │   ◉  (圆环 18x18)         │           │ │
│                                 │  #contextRingWidget       │           │ │
│                                 │  QPainter 自绘            │           │ │
│                                 │  bg=#45475a (底环)       │           │ │
│                                 │  fg=#89b4fa (填充弧)     │           │ │
│                                 │  线宽=2px                 │           │ │
│                                 │  tooltip:                  │           │ │
│                                 │  "5,120 / 128,000         │           │ │
│                                 │   tokens (4.0%)"          │           │ │
│                                 │                           │           │ │
│                                 │  [glm-4-plus]             │           │ │
│                                 │  #llmModelLabel           │           │ │
│                                 │  color=#cba6f7  font=11px  │           │ │
│                                 │  hover: underline          │           │ │
│                                 │  click: 弹出模型切换菜单    │           │ │
│                                 │                           │           │ │
│                                 └───────────────────────────┘           │ │
└──────────────────────────────────────────────────────────────────────────┘
```

### 圆环绘制逻辑（已有的 `ContextRingWidget` 简化）

```
像素坐标 (18x18):

         ┌─────────────────┐
         │   ╭──────╮     │  ← 底环: QPen(#45475a, 2px)  360° full arc
         │  ╱        ╲    │
         │  │  · 9,9 │    │  ← 中心点
         │  │         │    │
         │  ╲        ╱    │  ← 填充弧: QPen(#89b4fa, 2px) N° from 12 o'clock
         │   ╰──────╯     │     N = ratio * 360 (顺时针)
         └─────────────────┘

  ratio=0.04 (4%):    ratio=0.50 (50%):   ratio=0.95 (95%):
      ╭╮                  ╭──╮                ╭──╮
     ╱  ╲               ╱    ╲             ╱████╲
    │    │              │██████│            │██████│
     ╲  ╱               ╲    ╱             ╲████╱
      ╰╯                  ╰──╯               ╰──╯

  颜色统一为 #89b4fa (blue)，不做绿/黄/红区分
```

### 移除的控件

```
旧版 LLMStatusWidget:              新版（精简后）:
┌───────────────────────────┐      ┌───────────────────┐
│ ◉  1.2k / 100k  [model]  │  →   │ ◉  [model]         │
│     ↑ 文字标签（删除）    │      │ 无文字标签          │
│     颜色变化（删除）      │      │ 统一蓝色填充        │
│                          │      │ hover 显示 tooltip   │
└───────────────────────────┘      └───────────────────┘
```

### 涉及字符串常量

```python
# toolkit/gui/strings.py
LLM_CONTEXT_TOOLTIP_FMT: Final = "{used:,} / {total:,} tokens ({pct:.1f}%)"  # 新增
LLM_STATUS_NOT_CONFIGURED: Final = "未配置"  # 已存在
```

---

## 4. 设置菜单（已有改动 + 新增项）

```
  SettingsButton (齿轮 36x28)
  #settingsBtn
  codicon settings-gear 10px
  color=#a6adc8
  hover bg=#313244
  │
  └─ click →
       ┌──────────────────────┐
       │ #settingsMenu        │  bg=#313244  border=1px #45475a
       │ border-radius=6px    │  padding=4px  min-width=160
       │                      │
       │  主题切换             │  color=#cdd6f4  font-size=12px
       │                      │  padding=(6,24,6,24)  border-radius=4px
       │  LLM 模型设置         │  hover bg=#45475a
       │                      │
       │  Agent 设置           │
       │                      │
       │  ────────────────    │  ← separator  color=#45475a
       │                      │
       │  日志  ▸             │  ← chevron-right codicon 10px #a6adc8
       │                      │     hover 展开二级菜单:
       │                      │     ┌──────────────────────┐
       │                      │     │ #logSubMenu          │
       │                      │     │ bg=#313244           │
       │                      │     │                       │
       │                      │     │  导出日志             │  ← export codicon?
       │                      │     │  历史日志             │  ← folder codicon?
       │                      │     │  清空历史             │  ← trash codicon?
       │                      │     └──────────────────────┘
       └──────────────────────┘
```

> **注意**: 这个设置菜单布局是上一轮 `refactor-log-panel-header` 已实现的内容，本次 llm_manager 不需要再改动。

---

## 设计要点总结

| 原则 | 实现 |
|------|------|
| 图标 | 全部 codicon 字体，禁用 Unicode Emoji |
| 颜色 | 全部来自 `theme_colors.get_colors()`，不在模块代码中硬编码 |
| 样式 | 通过 `objectName` + `styles.py` 全局 QSS，不内联 `setStyleSheet()` |
| 对话框 | 继承 `ToolkitDialog`，使用 `DialogCloseButton` |
| 字符串 | 用户可见中文 MUST 提取到 `strings_gui.py` 的 `Final` 常量 |
| 布局 | 标准 QVBoxLayout / QHBoxLayout / QFormLayout，间距统一 10-14px |
