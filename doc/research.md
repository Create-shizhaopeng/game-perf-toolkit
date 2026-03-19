# Technical Research: ModifyModelNameTool

**Created**: 2026-03-08

---

## Decision 1: GUI 框架

**Decision**: Python + PyQt6

**Rationale**:
- Python 运行时通过 PyInstaller 打包进 exe，终端用户无需安装 Python
- PyQt6 提供成熟的 Widget 体系，原生支持 ComboBox（带下拉历史）、右键菜单、ToolTip、对话框等规范中要求的所有 UI 组件
- QSS 样式表支持运行时主题切换（Dark/Light）
- 信号槽机制天然适合 ADB 异步操作与 UI 更新的解耦

**Alternatives considered**:
- Tkinter：Python 内置，但 ComboBox 自动补全、右键菜单、悬浮提示等需大量自定义实现，开发效率低
- PySide6：功能与 PyQt6 几乎一致，LGPL 协议更宽松，但社区资源略少；可作为备选
- Electron：重量级，对内部工具过度设计

---

## Decision 2: 数据存储方案

**Decision**: JSON 文件（`device_profiles.json`）

**Rationale**:
- 规范要求轻量级方案，JSON 零依赖
- 设备档案数据量小（预计 < 200 条），JSON 读写性能完全足够
- 用户可直接查看/手动编辑 JSON 文件
- 导入功能天然兼容（同为 JSON 格式）
- 存储位置：工具根目录下 `data/device_profiles.json`

**Alternatives considered**:
- SQLite：功能更强但对本场景过度设计，增加了依赖复杂度
- CSV：不适合嵌套数据和中文字符处理

**JSON Schema**:
```json
[
  {
    "brand": "vivo",
    "manufacturer": "vivo",
    "model": "V2505A",
    "notes": "支持120帧原神"
  }
]
```

---

## Decision 3: ADB 集成方式

**Decision**: subprocess 调用 + 异步线程

**Rationale**:
- ADB 命令通过 `subprocess.run()` 执行，简单直接
- ADB 操作（root、remount、push、reboot、wait-for-device）为阻塞式，需在后台线程执行以避免 UI 卡死
- PyQt6 的 `QThread` + 信号机制可将操作进度实时传递到 UI 线程

**Alternatives considered**:
- python-adb 库：第三方依赖，文档有限，维护状态不确定
- adb server socket 直连：复杂度高，无明显收益

---

## Decision 4: 设备连接监听方案

**Decision**: 后台轮询线程（2 秒间隔）

**Rationale**:
- 定时执行 `adb devices` 检测设备连接状态
- 2 秒间隔在响应速度（<3 秒 SC-7）和 CPU 开销之间取得平衡
- 通过比对前后两次结果判断设备插入/拔出事件
- 用 QThread + 信号通知 UI 更新

**Alternatives considered**:
- USB 热插拔事件监听（pyudev/WMI）：Windows 平台实现复杂，需额外依赖
- `adb track-devices`：ADB 内置的持续监听命令，可作为优化方案，但需管理长连接进程

---

## Decision 5: 项目结构

**Decision**: 单应用分层结构

```
ModifyModelNameTool/
├── source/                      # 源代码与依赖（实现代码）
│   ├── main.py                  # 应用入口
│   ├── requirements.txt         # Python 依赖
│   ├── build.spec               # PyInstaller 打包配置
│   ├── build.py                 # 构建脚本
│   ├── core/
│   │   ├── __init__.py
│   │   ├── profile_manager.py   # 设备档案 CRUD 与导入
│   │   ├── config_manager.py    # 用户配置管理
│   │   ├── adb_manager.py       # ADB 命令封装与设备监听
│   │   └── device_service.py    # 伪装/重置业务逻辑
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py       # 主窗口
│   │   ├── save_dialog.py       # 保存/编辑对话框
│   │   ├── device_popup.py      # 设备选取弹窗
│   │   ├── settings_menu.py     # 设置菜单（齿轮按钮）
│   │   └── styles.py            # 主题样式定义（Dark/Light）
│   ├── data/
│   │   ├── device_profiles.json # 设备档案数据库（自动生成）
│   │   ├── config.json          # 用户配置（自动生成）
│   │   └── import_sample.json   # 导入模板示例文件
│   └── adb/                     # 内置 ADB（打包时包含）
│       ├── adb.exe
│       ├── AdbWinApi.dll
│       └── AdbWinUsbApi.dll
├── design/                      # UI 设计文档
│   ├── ui-design.md
│   └── assets/                  # 设计图（SVG）
├── checklists/                  # 规范检查清单
├── spec.md                      # 功能规范
├── impl-plan.md                 # 实现计划
├── data-model.md                # 数据模型
├── research.md                  # 技术决策
├── quickstart.md                # 快速上手
└── tasks.md                     # 任务列表
```

**Rationale**:
- 代码实现（source/）与设计文档分离，职责清晰
- UI 层（ui/）与业务逻辑层（core/）分离，便于维护和测试
- data/ 目录集中管理持久化数据、用户配置和导入模板
- adb/ 目录内置最小 ADB 集合，打包时一并包含
- 单入口 main.py 简化启动方式

---

## Decision 6: 打包与分发

**Decision**: PyInstaller --onedir + zip 压缩

**Rationale**:
- --onedir 模式启动速度快（<1 秒），避免 --onefile 的解压延迟
- 最终产物压缩为 zip，用户解压即用，无需安装 Python 或 ADB
- 内置 adb/ 目录打包进 zip，若系统 PATH 已有 adb 则优先使用系统版本
- 构建脚本可通过 `pyinstaller build.spec` 一键完成

---

## Decision 7: 主题系统

**Decision**: QSS（Qt Style Sheets）双主题 + 配置持久化

**Rationale**:
- 在 `ui/styles.py` 中定义 Dark 和 Light 两套 QSS 样式表
- 主题切换通过 `QApplication.setStyleSheet()` 实现，运行时即时生效无需重启
- 用户主题偏好存储在 `data/config.json` 中，启动时加载
- 首次启动默认暗色主题
- 配色方案参照 VSCode Dark+/Light+ 风格（详见 design/ui-design.md）
