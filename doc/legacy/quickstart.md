# Quick Start: Toolkit

Toolkit 为多功能桌面工具，包含两个选项卡：**ModifyModelNameTool**（设备型号伪装）与 **push policy**（策略配置推送）。

## 用户使用（exe 分发版）

### 系统要求

- Windows 10/11（x64）
- Android 设备已开启 USB 调试，已 root

### 安装

1. 下载 `Toolkit-vX.X.X.zip`
2. 解压到任意目录
3. 双击 `Toolkit.exe` 启动

无需安装 Python 或 ADB，工具已内置所有依赖。

### 使用流程（ModifyModelNameTool 选项卡）

1. 通过 USB 连接 Android 设备（已 root、已开启 USB 调试）
2. 启动工具，选择「ModifyModelNameTool」选项卡，第一行自动显示当前设备信息
3. 在第二行输入伪装目标的 brand/manufacturer/model（或点击快捷选取按钮从数据库选取）
4. 点击 **Start** 执行伪装
5. 等待设备重启完成，验证成功
6. 测试完成后点击 **Reset** 还原设备原始信息

### 使用流程（push policy 选项卡）

1. 切换到「push policy」选项卡
2. **配置文件** 区域：标题「配置文件」与提醒「支持拖拽「文件名包含 gameperfconfig」的 .xml 到此区域」同一行显示；该区域与「伪装设备信息」块高度一致
3. 选择配置文件：输入路径、点击「浏览」或拖拽 **文件名包含 gameperfconfig** 的 .xml 文件（如 `gameperfconfig（11）.xml`）；推送到设备后统一为 `gameperfconfig.xml`
4. 点击 **Start**：先做 XML 格式校验，通过后按「设备 version + 1」推送并重启设备
5. 点击 **Reset**：将设备策略恢复为上次 push 前备份的版本（version 为重置前设备 version + 1）
6. 点击 **Clear**：仅清除已选配置文件路径

### 设置

点击标题栏右侧的齿轮按钮：

- **Import Device Data**: 从 JSON 文件导入设备档案（格式参见下方）
- **Theme**: 切换暗色/亮色主题（偏好自动保存）

### 导入设备档案

准备 JSON 文件（格式参考 `data/import_sample.json`）：

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

通过 设置 > Import Device Data 选择该文件导入。

---

## 开发者指南

### 环境要求

- Python 3.9+
- Windows 10/11

### 安装开发依赖

```bash
cd source
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

### 依赖清单（source/requirements.txt）

```
PyQt6>=6.5.0
pyinstaller>=6.0.0
```

### 开发模式启动

```bash
cd source
python main.py
```

### 构建 exe

```bash
cd source
python build.py
```

构建产物在 `source/dist/Toolkit/` 目录下，自动压缩为 zip 即可分发。

### 项目结构

```
Toolkit/
├── source/                      # 源代码与依赖
│   ├── main.py                  # 应用入口（ApplicationName: Toolkit）
│   ├── requirements.txt         # Python 依赖
│   ├── build.spec               # PyInstaller 打包配置（产物名 Toolkit）
│   ├── build.py                 # 构建脚本
│   ├── core/
│   │   ├── __init__.py
│   │   ├── profile_manager.py   # 设备档案 CRUD 与导入
│   │   ├── config_manager.py    # 用户配置管理
│   │   ├── adb_manager.py       # ADB 命令封装与设备监听
│   │   ├── device_service.py   # 伪装/重置业务逻辑
│   │   └── push_policy_service.py # 策略推送/重置与 XML 校验
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py       # 主窗口（Tab: ModifyModelNameTool + push policy）
│   │   ├── push_policy_tab.py   # push policy 选项卡
│   │   ├── save_dialog.py       # 保存/编辑对话框
│   │   ├── device_popup.py      # 设备选取弹窗
│   │   ├── settings_menu.py    # 设置菜单（齿轮按钮）
│   │   └── styles.py           # 主题样式定义（Dark/Light）
│   ├── data/
│   │   ├── device_profiles.json # 设备档案数据库（自动生成）
│   │   ├── config.json          # 用户配置（自动生成）
│   │   ├── import_sample.json   # 导入模板示例
│   │   └── backups/             # push policy 备份（按设备 serial 分子目录）
│   └── adb/                     # 内置 ADB
│       ├── adb.exe
│       ├── AdbWinApi.dll
│       └── AdbWinUsbApi.dll
├── design/                      # UI 设计文档
│   ├── ui-design.md
│   └── assets/                  # 设计图（SVG）
├── checklists/                  # 规范检查清单
├── spec.md                      # 设备伪装功能规范
├── spec-push-policy.md          # push policy 功能规范与澄清
├── impl-plan.md                 # 实现计划
├── data-model.md                # 数据模型
├── research.md                  # 技术决策
├── quickstart.md                # 快速上手
└── tasks.md                     # 任务列表

（根目录 `UI示意图/`、`UI.jpg` / `ui*.png` / `model名修改重置工具.md` 为本地示意图与说明，已列入 `.gitignore`，不入库；设备伪装需求见 `spec.md`、`design/ui-design.md`。）
```
