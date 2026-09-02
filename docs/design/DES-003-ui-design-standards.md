<!--
  id: DES-003
  title: UI 设计规范与 VSCode 差距补齐
  type: design
  status: draft
  created: 2026-08-12
  updated: 2026-08-12
  tags: [ui, design-token, vscode, style, refactor]
  depends_on: []
-->

# UI 设计规范与 VSCode 差距补齐
<!-- TOC START -->

## 目录

- [1. 概述与目标](#1-概述与目标)
  - [1.1 背景](#11-背景)
  - [1.2 目标](#12-目标)
  - [1.3 与现有文档的关系](#13-与现有文档的关系)
  - [1.4 现状快照](#14-现状快照)
- [2. 设计原则](#2-设计原则)
- [3. Design Token 体系](#3-design-token-体系)
  - [3.1 颜色 token](#31-颜色-token)
  - [3.2 间距与密度 token](#32-间距与密度-token)
  - [3.3 字号 token](#33-字号-token)
  - [3.4 圆角 token](#34-圆角-token)
  - [3.5 阴影 token](#35-阴影-token)
  - [3.6 Token 落盘位置](#36-token-落盘位置)
- [4. 组件状态规范](#4-组件状态规范)
  - [4.1 六态模型](#41-六态模型)
  - [4.2 组件清单](#42-组件清单)
- [5. 布局与密度规范](#5-布局与密度规范)
  - [5.1 面板结构](#51-面板结构)
  - [5.2 密度要求](#52-密度要求)
  - [5.3 模块内容组织规范](#53-模块内容组织规范)
- [6. 交互规范（借鉴 VSCode）](#6-交互规范借鉴-vscode)
  - [6.1 命令面板（Ctrl+Shift+P）](#61-命令面板ctrlshiftp)
  - [6.2 布局持久化](#62-布局持久化)
  - [6.3 Badge 徽标](#63-badge-徽标)
  - [6.4 动效](#64-动效)
  - [6.5 键盘焦点环](#65-键盘焦点环)
- [7. 现状差距清单](#7-现状差距清单)
  - [7.1 P0 — 命名不一致（破坏性，样式丢失或死代码）](#71-p0-命名不一致破坏性样式丢失或死代码)
  - [7.2 P1 — 规范违反（硬编码颜色 / 内联样式）](#72-p1-规范违反硬编码颜色-内联样式)
  - [7.3 P2 — 美观度差距（Token 缺失 / 交互缺失）](#73-p2-美观度差距token-缺失-交互缺失)
  - [7.4 P3 — 性能与虚拟滚动](#74-p3-性能与虚拟滚动)
- [8. 实施路线](#8-实施路线)
  - [8.1 Phase 1 — Token 落地 + 规范违规清零（低风险，先行）](#81-phase-1-token-落地-规范违规清零低风险先行)
  - [8.2 Phase 2 — 交互补强（中等风险）](#82-phase-2-交互补强中等风险)
  - [8.3 Phase 3 — 动效与性能（可选）](#83-phase-3-动效与性能可选)
- [9. 风险与未决问题](#9-风险与未决问题)
- [变更记录](#变更记录)

<!-- TOC END -->

## 1. 概述与目标

### 1.1 背景

项目的 GUI 采用 PyQt6，三面板布局（左侧导航 + 中央内容 + 底部日志 + 右侧扩展面板）在结构上已对齐 VSCode，颜色使用 Catppuccin（Mocha 暗色 / Latte 亮色），图标使用 Codicons。但经过代码审计，界面的**商用感 / 美观度**与 VSCode 存在系统性差距，原因有三类：

1. **Token 缺失**：颜色、间距、字号、圆角等基础设计变量散落在 2500 行 QSS 中随手填写，没有统一的设计 token 体系，控件之间密度不一致。
2. **规范违规**：4 个子组件绕过全局 QSS 使用内联 `setStyleSheet` 和硬编码颜色；2 个模块存在无效的 objectName / class 属性（"死代码"）。
3. **交互缺失**：缺少焦点环、徽标、布局记忆、命令面板、动效等 VSCode 级交互细节。

### 1.2 目标

| 目标 | 说明 |
|------|------|
| **建立 Design Token 体系** | 颜色 / 间距 / 字号 / 圆角 / 阴影五类 token 集中定义，作为所有 UI 的唯一取值来源 |
| **补齐组件状态规范** | 每个交互控件定义 normal / hover / pressed / focus / disabled / active 六态 |
| **清空规范违规** | 消除模块内联样式与硬编码颜色，消除无效 objectName / class 属性 |
| **对标 VSCode 交互** | 焦点环、徽标、布局记忆、命令面板等关键交互项落地 |
| **给出实施路线** | 分期推进，Phase 1 低风险先落地，Phase 3 性能项可选 |

### 1.3 与现有文档的关系

| 文档 | 定位 | 关系 |
|------|------|------|
| [ui-style-architecture.md](../architecture/ui-style-architecture.md) | 样式**怎么管**（分层 / QSS / objectName 规范） | 本文是它的设计层补充，不冲突 |
| [ui-style-guide.md](../../.claude/rules/ui-style-guide.md) | 开发**硬约束**（禁止硬编码、objectName 绑定） | 本文为其提供 token 取值来源 |
| [theme_colors.py](../../toolkit/gui/theme_colors.py) | 颜色**常量实现** | 本文第 3 章给出扩展后的 token 命名与取值 |

### 1.4 现状快照

模块 GUI 审计结论（2026-08-12）：5 个模块有 GUI Tab（`device_disguise` / `perfdog_insights` / `agent_chat`（右侧面板）/ `perfetto_capture` / `game_perf`）。跨模块共性问题 5 条，详见第 7 章。

## 2. 设计原则

以下原则指导所有 UI 改动，优先级从高到低：

1. **单一取值来源**：任何颜色 / 间距 / 字号 / 圆角 MUST 来自 token 或全局 QSS，MUST NOT 在模块代码中字面量书写。
2. **状态完备**：每个交互控件 MUST 有完整六态反馈，且 hover / focus / active 三级视觉层级分明。
3. **密度一致**：所有控件遵循统一的 8px 基准间距体系，不允许模块自定义 padding / margin 打散密度。
4. **全局优先**：样式定义 MUST 走 `styles.py` 全局 QSS + objectName，MUST NOT 内联 `setStyleSheet` 覆盖主题（例外：运行时动态状态切换）。
5. **键盘可达**：所有可交互元素 MUST 有清晰的键盘焦点指示（focus ring），不设 `outline: none` 后不补 focus 样式。
6. **对标 VSCode**：交互范式（命令面板 / 徽标 / 布局记忆 / 动效）以 VSCode 为参考目标，但以 PyQt6 可实现为限。

## 3. Design Token 体系

### 3.1 颜色 token

现有 [theme_colors.py](../../toolkit/gui/theme_colors.py) 已覆盖基础背景 / 前景 / 强调 / 语义色。**补充**以下 VSCode 对齐的语义 token（以 [VS Code Theme Color 官方参考](https://code.visualstudio.com/api/references/theme-color) 为命名参照）：

| 新 token | 对标 VSCode | 用途 | 推荐值（dark） | 推荐值（light） |
|----------|------------|------|---------------|----------------|
| `focus_border` | `focusBorder` | 键盘焦点环 | `#89b4fa`（blue） | `#1e66f5` |
| `shadow` | `widget.shadow` | 弹出层 / 对话框阴影 | `rgba(0,0,0,0.35)` | `rgba(0,0,0,0.20)` |
| `selection_bg` / `selection_fg` | `list.activeSelectionBackground/Foreground` | 列表 / 树选中项（活动窗口） | `#585b70` / `#cdd6f4` | `#bcc0cc` / `#4c4f69` |
| `selection_bg_inactive` | `list.inactiveSelectionBackground` | 列表 / 树选中项（窗口失活） | `#45475a` | `#ccd0da` |
| `badge_bg` / `badge_fg` | `badge.background/foreground` | 导航徽标计数 | `#cba6f7` / `#1e1e2e` | `#8839ef` / `#ffffff` |
| `overlay_bg` | `widget.shadow` | 遮罩层 | `rgba(24,24,37,0.6)` | `rgba(230,233,239,0.6)` |
| `tooltip_bg` / `tooltip_fg` | `editorHoverWidget.background/foreground` | 悬停提示 | `#313244` / `#cdd6f4` | `#e6e9ef` / `#4c4f69` |
| `scrollbar_bg` / `scrollbar_hover` | `scrollbarSlider.background/hoverBackground` | 滚动条（替换现硬编码 rgba） | `rgba(121,121,121,80)` / `rgba(121,121,121,160)` | `rgba(100,100,100,60)` / `rgba(100,100,100,130)` |
| `input_focus_bg` | `inputOption.activeBackground` | 输入框聚焦时背景 | `#313244`（不变） | `#f9f9fb` |

**命名规范**：新 token 一律小写下划线，按语义分组；与现有键（`bg` / `fg` / `border` / `accent` 等）保持同风格。

### 3.2 间距与密度 token

以 **8px 为基准**（对齐 VSCode 紧凑密度），控件尺寸统一：

| Token | 值 | 用途 |
|-------|-----|------|
| `space-1` | 4px | 紧凑内边距（图标按钮、CheckBox 间距） |
| `space-2` | 8px | 控件默认 padding（按钮 / 输入框 / 列表行垂直） |
| `space-3` | 12px | 面板内容 padding、GroupBox 内部 |
| `space-4` | 16px | 区块间距、模块内容区 padding |
| `space-5` | 24px | 大区块间距、对话框 padding |
| `control-h` | 28px | 标准控件最小高度（按钮 / 输入 / 下拉） |
| `list-row-h` | 22px | 列表 / 树行高 |
| `nav-item-h` | 32px | 左侧导航项高度 |
| `panel-header-h` | 32px | 面板标题栏高度 |

**约束**：模块代码 MUST 使用上述基准值，MUST NOT 自定义 `padding: 5px` / `6px` 等偏离基准的散值。当前 QSS 中 `6px 16px`、`6px 20px`、`4px 8px` 等组合应收敛为 token 对应组合。

### 3.3 字号 token

| Token | 值 | 用途 |
|-------|-----|------|
| `font-2` | 10px | 辅助提示（fieldHint） |
| `font-3` | 11px | 状态栏、日志、小标签 |
| `font-4` | 12px | 正文默认 |
| `font-5` | 13px | Tab 标题、导航项、强调文本 |
| `font-6` | 14px | 窗口标题、section 标题 |
| `font-7` | 20px | 欢迎页大标题 |

**约束**：正文默认 12px，关键标题 13px，禁止在模块内随意写 `font-size: 15px` / `16px` 等。

### 3.4 圆角 token

| Token | 值 | 用途 |
|-------|-----|------|
| `radius-sm` | 2px | CheckBox / Radio |
| `radius-md` | 4px | 输入框 / 下拉 / 按钮 / SpinBox |
| `radius-lg` | 6px | 面板 / 卡片 / 树项 hover |
| `radius-xl` | 8px | 对话框 / 消息气泡 / 聊天输入框 |

**约束**：当前 QSS 中的 `border-radius: 7px`（滑杆把手）等特殊值保留，其余统一到四档。

### 3.5 阴影 token

Qt 无原生 CSS 阴影，使用 `QGraphicsDropShadowEffect`。适用范围：

| 场景 | 阴影配置 |
|------|---------|
| 对话框 / 弹出菜单 | `shadow` token，blur 24px，offset y 8px |
| 卡片 hover | `shadow` token，blur 12px，offset y 4px |
| 右侧面板浮层 | 轻微阴影，blur 16px |

**约束**：MUST 在 `toolkit/gui/` 提供统一封装函数（如 `apply_panel_shadow(widget, theme)`），模块 MUST NOT 各自实现阴影。

### 3.6 Token 落盘位置

- 颜色 token → [theme_colors.py](../../toolkit/gui/theme_colors.py)
- 间距 / 字号 / 圆角 token → 新增 `toolkit/gui/design_tokens.py`（纯常量，供 QSS 生成与模块引用）
- QSS 中的魔法值（padding / font-size / radius）逐步替换为 token 注释标注

## 4. 组件状态规范

### 4.1 六态模型

每个交互控件 MUST 定义以下状态（缺失的补齐）：

| 状态 | 说明 | 视觉要求 |
|------|------|---------|
| `normal` | 默认 | 无特殊反馈 |
| `hover` | 鼠标悬停 | 背景提亮一级（`hover` token） |
| `pressed` | 按下 | 背景压暗一级 |
| `focus` | 键盘聚焦 | **统一 focus ring**：`focus_border` 1px + 外发光（可用 `border: 1px solid focus_border` + 轻微 outline） |
| `disabled` | 禁用 | 前景降为 `fg_muted`，背景降级 |
| `active` | 选中 / 激活 | 背景 `selection_bg` 或 accent 强调 |

**关键补齐点**：
- 当前 QSS 大量控件只有 hover/pressed，缺 focus（如 [styles.py:433-447](../../toolkit/gui/styles.py#L433-L447) 的通用按钮无 focus 态）。
- 树 / 表选中态需区分窗口活动（`selection_bg` / `selection_bg_inactive`），目前仅 `gameperfDiffTree` 做了。
- **禁止** `outline: none` 后不补 focus 样式（当前 [styles.py:683](../../toolkit/gui/styles.py#L683) 等列表控件 `outline: none` 但无 focus ring）。

### 4.2 组件清单

| 组件 | 现状态 | 需补齐 |
|------|--------|--------|
| 按钮（primary/secondary/danger/ghost/stop/icon） | hover/pressed/disabled 有 | focus、active、icon 按钮 hover 圆角 |
| 输入框（QLineEdit/QTextEdit） | focus 改边框色 | focus ring 统一、hover 态 |
| 下拉（QComboBox） | hover/focus 有 | 弹出列表 item focus |
| CheckBox / Radio | hover 有 | focus ring、radio 样式缺失 |
| 列表 / 树 | selected/hover 有 | 窗口失活两级、focus ring |
| Tab | selected/hover 有 | focus ring、关闭按钮 hover |
| 滑杆 / 进度条 | 有 | focus |
| Tooltip | 无 | 统一 tooltip token |
| Badge（新增） | 无 | badge_bg/badge_fg |

## 5. 布局与密度规范

### 5.1 面板结构

维持现有三面板 + 底部面板结构（[main_window.py:143-159](../../toolkit/gui/main_window.py#L143-L159)）：

```
┌─────────┬────────────────────────────┐
│ NavPanel │ ContentStack                │
│ (180px)  ├────────────────────────────┤
│         │ BottomPanel（可折叠，默认最小化）│
├─────────┴────────────────────────────┤
│ StatusBar                             │
└──────────────────────────────────────┘
（RightPanel 为 overlay 浮层，可开关）
```

### 5.2 密度要求

- 模块内容区统一 `padding: 16px`（`space-4`）。
- GroupBox 内部间距 8-12px（`space-2`/`space-3`）。
- 表单行高统一 28px（`control-h`）。
- Sash（Splitter 手柄）宽度 4px，hover 变 accent 色（已有，保持统一）。

### 5.3 模块内容组织规范

参考 VSCode 的分组范式，模块 Tab 建议分层：

1. **工具条（可选）**：顶部横向操作条，高 36px。
2. **配置区**：GroupBox 分组，卡片化。
3. **主内容区**：表 / 树 / 图表，占主要空间。
4. **底部操作行**：主操作（primaryBtn）在右，次要操作在左。

## 6. 交互规范（借鉴 VSCode）

### 6.1 命令面板（Ctrl+Shift+P）

VSCode 灵魂交互，适配工具集的建议：

- 全局搜索：跳转模块、执行模块动作（如 `perfetto_capture: 开始抓取`）。
- 落地：新增 `toolkit/gui/command_palette.py`，基于 `QLineEdit + QListWidget` 模糊匹配，通过 `EventBus` 或服务注册表派发。
- 工作量：中等（约 300 行），建议 Phase 2。

### 6.2 布局持久化

- 保存：Splitter sizes、面板开关状态、当前激活 Tab、右侧面板宽度。
- 落盘：`data/config.json`（`ConfigManager`）新增 `gui.layout` 键。
- 时机：窗口关闭时保存，启动时恢复。

### 6.3 Badge 徽标

- 左侧导航项可携带计数徽标（如 Trace 模块"有 N 个新报告"）。
- 实现：`NavPanel` 支持 badge 文本，样式用 `badge_bg/badge_fg` token。
- 工作量：低，Phase 2。

### 6.4 动效

QSS 不支持 CSS transition/animation，用 `QPropertyAnimation` / `QGraphicsOpacityEffect` 对**关键路径**补动画：

| 场景 | 动画 | 时长 |
|------|------|------|
| 面板展开 / 收起 | 高度 / 宽度插值 | 150ms ease |
| 右侧面板淡入 | 透明度 | 120ms |
| 模块 Tab 切换 | 透明度 + 轻微位移 | 100ms |
| 按钮 hover | QSS 无过渡，跳过（成本高） | — |

**约束**：动画 MUST 封装到 `toolkit/gui/` 公共工具，模块 MUST NOT 各自实现；避免大量 QSS 动画导致性能问题。

### 6.5 键盘焦点环

- 全应用统一 focus ring（`focus_border` token）。
- 键盘用户可用 Tab 遍历所有交互元素，聚焦元素有清晰指示。
- 覆盖：按钮 / 输入 / 下拉 / 列表 / 树 / Tab / 滑杆。

## 7. 现状差距清单

依据 2026-08-12 模块 GUI 审计（5 个 GUI 模块），按严重度分级。

### 7.1 P0 — 命名不一致（破坏性，样式丢失或死代码）

| 问题 | 位置 | 影响 |
|------|------|------|
| `setObjectName("primaryButton")` 与全局 QSS 的 `primaryBtn` 不一致 | [perfdog_insights/gui_tab.py:88](../../modules/perfdog_insights/src/gui_tab.py#L88) | 主操作按钮样式丢失，降级为通用按钮 |
| `setProperty("class", "sectionCard")` / `sectionTitleBlue` 无对应 QSS 规则 | [perfdog_insights/gui_tab.py:60,68](../../modules/perfdog_insights/src/gui_tab.py#L60)、[game_perf/gui_tab.py:188,241,721,739](../../modules/game_perf/src/gui_tab.py#L188) | 10+ 处"死代码"，样式无效 |

**处理**：Phase 1 将 `primaryButton` 改为 `primaryBtn`；`sectionCard`/`sectionTitleBlue` 若需要则补全局 QSS 规则，否则移除。

### 7.2 P1 — 规范违反（硬编码颜色 / 内联样式）

| 问题 | 位置 | 影响 |
|------|------|------|
| 模块级硬编码颜色常量 `_BG="#1e1e2e"` 等 + 内联绘制样式 | [perfetto_capture/fps_chart.py:28-36](../../modules/perfetto_capture/src/fps_chart.py#L28) | 复制主题色，换主题后图表不跟随 |
| 拖入区完整内联样式 + 硬编码 `rgba(203,166,247,0.1)` | [perfetto_capture/drag_drop_area.py:33-66](../../modules/perfetto_capture/src/drag_drop_area.py#L33) | 绕过全局 QSS |
| 统计标签内联 `font-size` + 硬编码 `#FABF42`/`#F85149` | [perfetto_capture/jank_stats.py:29-39](../../modules/perfetto_capture/src/jank_stats.py#L29) | 同上 |
| 日志颜色硬编码 `#dcdcaa`/`#f44747`/`#608b4e` 等 5 种 + 颜色→level 字符串推断 | [game_perf/gui_tab.py:1248-1353](../../modules/game_perf/src/gui_tab.py#L1248) | 与 theme_colors 语义色脱节 |
| 档案编辑/删除按钮内联 padding | [device_disguise/gui_tab.py:538-539](../../modules/device_disguise/src/gui_tab.py#L538) | 轻微违规 |

**处理**：Phase 1 全部迁移到全局 QSS + objectName，颜色从 `get_colors()` 获取；`game_perf` 的日志颜色映射提升为显式 level 参数。

### 7.3 P2 — 美观度差距（Token 缺失 / 交互缺失）

| 差距 | 现状 | 目标 |
|------|------|------|
| 间距 / 字号 / 圆角取值散乱 | `6px 16px`/`6px 20px`/`4px 8px` 混用 | 收敛到第 3 章 token |
| 缺少 focus ring | 大量控件 `outline: none` 无 focus 态 | 全应用统一 focus_border |
| 树 / 表选中态无窗口失活两级 | 仅 gameperfDiffTree 做了 | selection_bg / selection_bg_inactive |
| 无徽标 | 导航纯文字 | NavPanel badge |
| 布局不记忆 | 每次启动还原默认 | 布局持久化 |
| 无命令面板 | 无 | Phase 2 命令面板 |
| 无关键动效 | 面板切换生硬 | Phase 3 关键动画 |
| 高 DPI 图标发虚 | codicon 字体渲染 QPixmap | Phase 3 SVG 渲染 |

### 7.4 P3 — 性能与虚拟滚动

| 问题 | 位置 | 影响 |
|------|------|------|
| QTableWidget 11 列 + 每行 6 个 QComboBox cellWidget，刷新全量重建 | [game_perf/gui_tab.py](../../modules/game_perf/src/gui_tab.py) | 数百行时 UI 卡顿 |
| QTreeWidget 历史树无虚拟滚动 | [perfetto_capture/session_tree.py](../../modules/perfetto_capture/src/session_tree.py) | 大量节点时性能下降 |

**处理**：Phase 3 可选——game_perf 换 QTableView + delegate，历史树评估虚拟化。非本次美观度改造重点，但记录在案。

## 8. 实施路线

### 8.1 Phase 1 — Token 落地 + 规范违规清零（低风险，先行）

1. 扩展 `theme_colors.py` 补齐 3.1 节 token；新增 `toolkit/gui/design_tokens.py`。
2. 修正 P0：`primaryButton` → `primaryBtn`；清理或补全 `sectionCard`/`sectionTitleBlue`。
3. 清理 P1：fps_chart / drag_drop_area / jank_stats 迁移全局 QSS；game_perf 日志颜色映射提升；device_disguise 内联 padding 移除。
4. 统一间距 / 字号 / 圆角：`styles.py` 全量按 token 收敛。
5. 运行 `scripts/check_hardcoded_strings.py` 及既有测试回归。

### 8.2 Phase 2 — 交互补强（中等风险）

1. 统一 focus ring（全应用）。
2. 树 / 表选中态窗口失活两级。
3. NavPanel badge 徽标。
4. 布局持久化（ConfigManager `gui.layout`）。
5. 命令面板（Ctrl+Shift+P）。

### 8.3 Phase 3 — 动效与性能（可选）

1. 面板展开 / 收起关键动画（QPropertyAnimation 封装）。
2. Codicons SVG 渲染提升高 DPI 清晰度。
3. game_perf QTableWidget → QTableView + delegate 虚拟化。

## 9. 风险与未决问题

| 风险 | 说明 | 缓解 |
|------|------|------|
| QSS 大规模重构回归 | 2500 行 QSS 改动可能影响各模块观感 | 每步跑启动验证 + 截图对比 |
| 动画性能 | 过度动画导致卡顿 | 仅关键路径，封装公共工具 |
| QTableView 迁移工作量大 | game_perf 表格重构耗时 | 归入 Phase 3 可选，不阻塞 |
| 主题 token 扩展影响既有模块 | 新增 token 不影响既有键，向后兼容 | 只增不改 |

**未决问题**：
- `sectionCard`/`sectionTitleBlue` 的语义是否需要保留（若保留则补 QSS，否则移除）— Phase 1 确认。
- 命令面板优先级：若工具集用户以鼠标为主，是否值得投入 — Phase 2 前确认。
- 布局持久化粒度：仅主窗口 vs 包含各模块面板状态 — Phase 2 细化。

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-12 | 初版建立：基于模块 GUI 审计，产出 Design Token 体系 + 差距清单 + 三期实施路线 |