# Tasks: ModifyModelNameTool (设备型号伪装与重置工具)

**Input**: `ModifyModelNameTool/` design documents (spec.md, impl-plan.md, data-model.md, research.md, quickstart.md, design/)
**Prerequisites**: impl-plan.md (required), spec.md (required)

**Tests**: Not explicitly requested in spec. Test tasks are omitted.

**Organization**: Tasks grouped by user story (mapped from spec.md 10 scenarios). Priorities inferred from functionality criticality.

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create project skeleton and dependency configuration

- [x] T001 Create project directory structure per impl-plan.md (`core/`, `ui/`, `data/`, `adb/`) and create `__init__.py` in each Python package directory (`core/`, `ui/`)
- [x] T002 Create `requirements.txt` with PyQt6>=6.5.0 and pyinstaller>=6.0.0
- [x] T003 [P] Create `data/import_sample.json` with sample device profiles

**Checkpoint**: Project skeleton ready, dependencies installable via `pip install -r requirements.txt`

---

## Phase 2: Foundational (Core Modules)

**Purpose**: Implement core business logic modules that ALL user stories depend on

**CRITICAL**: No UI work can begin until this phase is complete

- [x] T004 [P] Implement ProfileManager in `core/profile_manager.py` -- DeviceProfile CRUD, JSON persistence (`data/device_profiles.json`), unique key (brand+manufacturer+model, 使用 `.lower()` 大小写不敏感比较), `load()`, `save()`, `add()`, `update()`, `delete()`, `find()`, `exists()`, `import_from()`, `get_all()`; atomic file write
- [x] T005 [P] Implement ConfigManager in `core/config_manager.py` -- AppConfig (theme, adb_path), JSON persistence (`data/config.json`), `load()`, `save()`, `get_theme()`, `set_theme()`; default `{"theme":"dark","adb_path":""}`
- [x] T006 [P] Implement AdbManager + DeviceMonitor in `core/adb_manager.py` -- ADB subprocess wrapper: `check_adb_available()`, `get_connected_devices()`, `get_prop(key)`, `run_cmd(cmd)`; ADB path priority: system PATH -> config -> bundled `adb/adb.exe`; DeviceMonitor (QThread): 2-second polling `adb devices`, signals `device_connected(dict)` / `device_disconnected()`
- [x] T007 Implement DeviceService in `core/device_service.py` -- Disguise flow: root -> remount -> setenforce 0 -> pull build.prop -> modify -> push -> reboot -> wait boot_completed -> verify getprop; Reset flow: read vendor props -> same ADB flow to restore; signals `progress(str)`, `error(str)`, `finished(DeviceState)`; runs in QThread (depends on T004, T006)
- [x] T008 [P] Implement theme styles in `ui/styles.py` -- `get_dark_theme()`, `get_light_theme()`, `apply_theme(app, name)` returning QSS strings; colors per design/ui-design.md

**Checkpoint**: All core modules independently functional, can be tested via Python REPL

---

## Phase 3: US1 - 连接设备并查看当前信息 (Priority: P1) MVP

**Goal**: 插入 USB 设备后 3 秒内自动显示 brand/manufacturer/model，拔出后清空并置灰按钮

**Independent Test**: 启动工具 -> 插入设备 -> 第一行显示设备属性 + 绿色连接状态 + 伪装状态徽章 -> 拔出设备 -> 第一行清空 + 按钮置灰

### Implementation

- [x] T009 [US1] Create MainWindow scaffold in `ui/main_window.py` -- 四区域布局: Section 1 (当前设备信息), Section 2 (伪装设备信息), Section 3 (执行日志), Section 4 (操作按钮); window title, gear button placeholder, minimum size 640x520
- [x] T010 [US1] Implement Section 1 (当前设备信息) in `ui/main_window.py` -- 三个只读显示框 (brand/manufacturer/model, h=26px); 状态徽章 (未伪装绿色/已伪装黄色); 连接指示器 (绿色圆点 + 文字); labels 12px, values 13px, dominant-baseline centering
- [x] T011 [US1] Wire DeviceMonitor signals in `ui/main_window.py` -- `device_connected` -> read odm props via AdbManager -> populate Section 1 -> compare odm vs vendor -> set badge; `device_disconnected` -> clear Section 1 -> hide badge -> disable buttons
- [x] T012 [US1] Implement button state management in `ui/main_window.py` -- Start/Clear/Reset buttons (140x36); Start (蓝色渐变 `#0e7ad3`->`#0062a3`), Clear (灰色), Reset (红色渐变 `#c94a4a`->`#a63d3d`); 悬停亮度 +10%; 禁用 opacity 0.5; 按钮文字 14px bold; disabled when device not connected; enabled when connected

**Checkpoint**: US1 complete -- 设备插入自动显示信息，拔出自动清空，按钮状态正确

---

## Phase 4: US2 - 手动输入伪装信息并执行 (Priority: P1) MVP

**Goal**: 手动输入 brand/manufacturer/model 后点击 Start 执行伪装，进度实时显示，完成后 getprop 验证

**Independent Test**: 连接设备 -> 输入伪装信息 -> 点击 Start -> 日志区逐行显示 adb root/remount/push/reboot 进度 -> 设备重启后自动验证 -> Section 1 更新为伪装值 + 徽章变为「已伪装」

### Implementation

- [x] T013 [US2] Implement Section 2 (伪装设备信息) in `ui/main_window.py` -- 标题 + ☆ 快捷选取按钮 (20x20, 与标题同行同高); 三个 QComboBox (brand/manufacturer/model, h=28px, editable); 下拉箭头; 焦点边框变蓝
- [x] T014 [US2] Implement Section 3 (执行日志) in `ui/main_window.py` -- 标题「执行日志」; 滚动文本区域显示日志; 底部固定区域: 分隔线 + 进度条 + 百分比文字 (等距 8px, 贴底部); 日志颜色: 绿(成功)/黄(进行中)/红(错误)
- [x] T015 [US2] Wire Start button to DeviceService.disguise() in `ui/main_window.py` -- 点击 Start -> 校验三字段非空 (空字段弹提示) -> 直接调用 DeviceService.disguise() (FR-7 保存检查在 Phase 6 T023 补全，MVP 阶段跳过); 连接 progress/error/finished 信号更新 Section 3; 执行期间 Start 按钮禁用
- [x] T016 [US2] Implement error handling for disguise in `ui/main_window.py` -- FR-8: adb root 失败提示 root 权限; adb 不可用提示环境配置; 其他错误显示具体信息; 错误信息红色显示在日志区

**Checkpoint**: US2 complete -- 可手动伪装设备，进度实时反馈，错误有明确提示

---

## Phase 5: US3 - 重置设备 + 清除输入 (Priority: P1) MVP

**Goal**: 点击 Reset 还原设备为原始型号，点击 Clear 清空输入框

**Independent Test**: 设备已伪装 -> 点击 Reset -> 日志显示还原进度 -> 重启后验证 -> 徽章变为「未伪装」; 输入框有内容 -> 点击 Clear -> 三个输入框清空

### Implementation

- [x] T017 [US3] Wire Reset button to DeviceService.reset() in `ui/main_window.py` -- 点击 Reset -> DeviceService.reset() (从 vendor 属性读取原始值) -> 复用 Section 3 进度显示 -> 完成后 Section 1 更新 + 徽章变绿
- [x] T018 [US3] Implement Clear button logic in `ui/main_window.py` -- 清空三个 ComboBox 输入框; 不影响已连接设备; 不清除日志区
- [x] T019 [US3] Implement Section 4 (操作按钮行) polish in `ui/main_window.py` -- 验证按钮样式在主题切换后保持一致; 按钮间距与对齐微调; 确保 Tab 键序正确 (Start -> Clear -> Reset)

**Checkpoint**: US1+US2+US3 = 完整 MVP -- 连接、伪装、重置、清除全部可用

---

## Phase 6: US4 - 设备档案管理 (Priority: P2)

**Goal**: 用户可保存、选取、编辑、删除设备档案，弹窗选取后自动填充输入框

**Independent Test**: 点击 ☆ -> 弹窗显示已保存设备列表 -> 选中一项自动填充输入框; 伪装新组合时弹出保存对话框 -> Save 持久化; 右键编辑/删除功能正常

### Implementation

- [x] T020 [P] [US4] Implement SaveDialog in `ui/save_dialog.py` -- 模态对话框 380x340, 最小 400x320; 标题栏 + 关闭按钮; brand/manufacturer/model 输入框 (h=28px, label 左 input 右, dominant-baseline centering); 备注多行输入框 (h=68px, placeholder 灰色斜体); Save + Cancel 按钮 (140x36, 居中, 间距 16px); 新增模式 (预填输入值) / 编辑模式 (预填 DB 值); Save 时唯一键校验
- [x] T021 [P] [US4] Implement DevicePopup in `ui/device_popup.py` -- 固定大小 480x340, 最小 400x280; 锚定 ☆ 按钮右下角; 左栏 200px QListWidget (model 列表, 每项 36px, 双行: model + brand·manufacturer); 右栏备注面板 (悬停 1 秒显示备注 + 游戏标签); 右键菜单: 编辑 / 删除; 选中信号发射 DeviceProfile
- [x] T022 [US4] Wire ☆ button to DevicePopup in `ui/main_window.py` -- 点击 ☆ -> DevicePopup.show() -> 选中 profile -> 自动填充三个 ComboBox
- [x] T023 [US4] Implement save-before-disguise check (FR-7) in `ui/main_window.py` -- Start 点击时: 检查 (brand, manufacturer, model) 组合是否已在 DB -> 不存在则弹出 SaveDialog (预填当前输入) -> Save 后继续执行 / Cancel 后取消伪装
- [x] T024 [US4] Implement edit/delete in DevicePopup `ui/device_popup.py` -- 右键「编辑」-> 打开 SaveDialog 编辑模式 -> Save 后更新 DB 并刷新列表; 右键「删除」-> QMessageBox 确认 -> 确认后从 DB 删除并刷新列表

**Checkpoint**: US4 complete -- 设备档案完整 CRUD, 弹窗选取自动填充

---

## Phase 7: US5 - 输入框自动补全 (Priority: P2)

**Goal**: 三个 ComboBox 输入时从数据库过滤历史记录，选中某项后自动填充其余字段

**Independent Test**: brand 输入框输入 "vi" -> 下拉显示 "vivo" -> 选中后 manufacturer 和 model 自动填充为匹配的第一条记录

### Implementation

- [x] T025 [US5] Implement ComboBox auto-complete in `ui/main_window.py` -- 三个 QComboBox 设置 QCompleter (case-insensitive); 数据源来自 ProfileManager.get_all(); 输入时实时过滤
- [x] T026 [US5] Implement cross-field auto-fill in `ui/main_window.py` -- 选中 brand 下拉项 -> 查找匹配的 profiles -> 按首字母排序取第一条 -> 自动填充 manufacturer + model; 同理 manufacturer/model 选中后填充其余; 响应时间 <=500ms

**Checkpoint**: US5 complete -- 输入框自动补全与联动填充

---

## Phase 8: US6 - 设置菜单、主题切换与数据导入 (Priority: P3)

**Goal**: 齿轮按钮打开设置菜单，支持 Dark/Light 主题切换和 JSON 设备档案导入

**Independent Test**: 点击齿轮 -> 菜单显示 Import + Theme 选项; 切换 Theme 即时生效 + 重启后保持; Import JSON 文件后设备列表新增条目

### Implementation

- [x] T027 [P] [US6] Implement SettingsMenu in `ui/settings_menu.py` -- QMenu: "Import Device Data" (文件夹图标) + "Theme: Dark/Light" (太阳/月亮图标, 当前项勾选); 锚定齿轮按钮正下方弹出; 菜单样式跟随当前主题
- [x] T028 [US6] Implement theme switching in `ui/main_window.py` -- 选择 Theme -> Styles.apply_theme(app, name) 即时切换 QSS -> ConfigManager.set_theme() 持久化; 默认 Dark; 无需重启
- [x] T029 [US6] Implement JSON import in `ui/main_window.py` -- 选择 "Import Device Data" -> QFileDialog (filter *.json) -> ProfileManager.import_from(path) -> 反馈成功/跳过条数 (在日志区或 QMessageBox); 按唯一键去重
- [x] T030 [US6] Wire SettingsMenu to MainWindow title bar in `ui/main_window.py` -- 齿轮按钮 (28x20 or 20x20, 暗色 bg `#3c3c3c` icon `#cccccc` / 亮色 bg `#e8e8e8` icon `#555555`) 点击弹出 SettingsMenu

**Checkpoint**: US6 complete -- 设置菜单、主题切换、数据导入全部可用

---

## Phase 9: Entry Point & Integration

**Purpose**: 创建应用入口，组装所有组件

- [x] T031 Create `main.py` entry point -- QApplication 初始化; 加载 ConfigManager -> 应用主题; 初始化 ProfileManager, AdbManager, DeviceService; 创建 MainWindow 并注入依赖; 启动 DeviceMonitor; `app.exec()`
- [x] T032 Integration testing -- 手动验证所有 10 个场景端到端; 验证成功标准 SC-1 ~ SC-8

**Checkpoint**: 应用完整可运行，所有功能集成

---

## Phase 10: Packaging & Deployment (Priority: P3)

**Purpose**: PyInstaller 打包为 Windows exe，zip 分发

- [x] T033 [P] Create `build.spec` for PyInstaller -- `--onedir` mode; 包含 `data/import_sample.json`, `adb/` directory; `--exclude-module` 排除不需要的 Qt 模块减小体积; 输出 `dist/ModifyModelNameTool/`
- [x] T034 Create `build.py` packaging script -- 执行 PyInstaller build.spec; 产物压缩为 `ModifyModelNameTool-vX.X.X.zip`
- [x] T035 Bundle ADB binaries in `adb/` directory -- 放入 `adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll`; AdbManager 优先系统 PATH, 其次 config adb_path, 最后 bundled adb

**Checkpoint**: 可生成 exe 分发包，解压即用

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: 全局优化和收尾

- [x] T036 Error handling refinement (FR-8) -- 审查所有 ADB 操作的错误路径; 确保每种错误有明确中文提示
- [x] T037 Performance validation -- 设备连接检测 <=3 秒 (SC-1, SC-7); 自动补全响应 <=500ms (SC-6); 端到端伪装/重置 <2 分钟 (SC-2, SC-3)
- [x] T038 [P] UI polish -- 验证所有页面文字垂直居中; 验证暗色/亮色主题颜色一致性; 验证缩放不变形 (preserveAspectRatio)
- [x] T039 Run quickstart.md validation -- 按 quickstart.md 步骤从零搭建验证

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies -- can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 -- BLOCKS all user stories
- **Phase 3-8 (User Stories)**: All depend on Phase 2 completion
  - US1 (Phase 3): No story dependencies -> **MVP start**
  - US2 (Phase 4): Depends on US1 (needs MainWindow scaffold)
  - US3 (Phase 5): Depends on US2 (reuses progress display)
  - US4 (Phase 6): Depends on US1 (needs MainWindow); SaveDialog/DevicePopup can parallel
  - US5 (Phase 7): Depends on US4 (needs ProfileManager data in ComboBox)
  - US6 (Phase 8): Depends on US1 (needs MainWindow gear button)
- **Phase 9 (Integration)**: Depends on all user stories
- **Phase 10 (Packaging)**: Depends on Phase 9
- **Phase 11 (Polish)**: Depends on Phase 9

### Module Dependency Graph

```
T004 ProfileManager ─┐
                     ├─> T007 DeviceService ─┐
T006 AdbManager ─────┘                       │
                                              ├─> T009 MainWindow ─> T031 main.py
T005 ConfigManager ──────────────────────────┤
T008 Styles ─────────────────────────────────┘
                     ┌─> T020 SaveDialog ────┤
T004 ProfileManager ─┤                       ├─> T031 main.py
                     └─> T021 DevicePopup ───┤
T005 ConfigManager ──┐                       │
T008 Styles ─────────┼─> T027 SettingsMenu ──┘
T004 ProfileManager ─┘
```

### Within Each User Story

- Core modules before UI components
- Models/Services before Views
- Signals/slots wiring after both sides implemented

### Parallel Opportunities

```
Phase 2 - All [P] tasks can run in parallel:
  T004 ProfileManager | T005 ConfigManager | T006 AdbManager | T008 Styles

Phase 6 - Dialog components in parallel:
  T020 SaveDialog | T021 DevicePopup

Phase 8 - Settings menu parallel with other US6 tasks:
  T027 SettingsMenu (while US5 completes)
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US1 -- 设备连接与显示
4. Complete Phase 4: US2 -- 伪装执行
5. Complete Phase 5: US3 -- 重置与清除
6. **STOP and VALIDATE**: 连接、伪装、重置核心流程可用
7. 此时可交付内部测试使用

### Incremental Delivery

1. Setup + Foundational -> Core ready
2. US1 + US2 + US3 -> **MVP** (核心伪装/重置功能)
3. US4 -> 设备档案管理 (提升效率)
4. US5 -> 自动补全 (改善体验)
5. US6 -> 设置与主题 (功能完善)
6. Integration + Packaging -> **Release v1.0**

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 39 |
| Phase 1 (Setup) | 3 tasks |
| Phase 2 (Foundational) | 5 tasks |
| US1 (连接显示) | 4 tasks |
| US2 (伪装执行) | 4 tasks |
| US3 (重置清除) | 3 tasks |
| US4 (档案管理) | 5 tasks |
| US5 (自动补全) | 2 tasks |
| US6 (设置主题) | 4 tasks |
| Integration | 2 tasks |
| Packaging | 3 tasks |
| Polish | 4 tasks |
| Parallel opportunities | 8 tasks (T004-T008, T020-T021, T027, T033) |
| MVP scope | Phase 1-5 (US1+US2+US3, 19 tasks) |

---

## Post-Implementation Changes

实现完成后的需求变更、Bug 修复与结构调整：

| 编号 | 类型 | 说明 | 影响文件 |
|------|------|------|---------|
| PC-1 | 需求变更 | 伪装前校验输入值与当前设备信息是否一致，一致则提示不执行 | `ui/main_window.py` |
| PC-2 | 需求变更 | 设备选取弹窗备注由「悬停1秒延迟」改为「实时显示」 | `ui/device_popup.py` |
| PC-3 | 需求遗漏 | ComboBox 下拉列表未填充数据库历史值，补充加载与刷新逻辑 | `ui/main_window.py` |
| PC-4 | Bug 修复 | `device_popup.py` 未导入 `QDialog`，编辑保存时 NameError 崩溃 | `ui/device_popup.py` |
| PC-5 | Bug 修复 | SaveDialog 以 Popup 为 parent，Popup 失焦关闭导致卡死闪退 | `ui/device_popup.py` |
| PC-6 | Bug 修复 | DevicePopup 未继承暗色主题背景，文字不可读 | `ui/device_popup.py`, `ui/styles.py` |
| PC-7 | Bug 修复 | QMessageBox 暗色主题下文字颜色不可读 | `ui/styles.py` |
| PC-8 | 结构调整 | 源代码迁移至 `source/` 子目录，设计文档保留根目录 | 全部源文件 |
| PC-9 | 增强 | SettingsMenu 导入成功后发射 `data_imported` 信号刷新 ComboBox | `ui/settings_menu.py`, `ui/main_window.py` |
