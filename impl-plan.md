# Implementation Plan: ModifyModelNameTool

**Created**: 2026-03-08
**Tech Stack**: Python 3.x + PyQt6

---

## Module Breakdown

### Module 1: core/profile_manager.py -- 设备档案管理

**职责**: DeviceProfile 的 CRUD 操作和 JSON 文件持久化

**关键类**: `ProfileManager`

| 方法              | 说明                                          |
| ----------------- | --------------------------------------------- |
| `load()`          | 从 JSON 文件加载档案列表到内存                |
| `save()`          | 将内存列表写回 JSON 文件                      |
| `add(profile)`    | 新增档案，唯一键冲突时抛出异常                |
| `update(old, new)`| 更新档案，冲突检查                            |
| `delete(profile)` | 删除档案                                      |
| `find(field, val)`| 按字段模糊匹配查询                            |
| `exists(b, m, mo)`| 检查 brand+manufacturer+model 组合是否存在    |
| `import_from(path)`| 从外部 JSON 导入，去重合并，返回导入统计      |
| `get_all()`       | 返回全部档案列表                              |

**依赖**: 无外部依赖，仅标准库 `json`, `os`

---

### Module 2: core/adb_manager.py -- ADB 命令封装与设备监听

**职责**: 封装所有 ADB 操作，提供设备状态监听

**关键类**: `AdbManager`

| 方法/信号                    | 说明                                         |
| ---------------------------- | -------------------------------------------- |
| `check_adb_available()`      | 检测 adb 命令是否可用                        |
| `get_connected_devices()`    | 获取已连接设备列表                           |
| `get_prop(key)`              | 读取设备属性                                 |
| `run_cmd(cmd)`               | 执行 adb 命令，返回结果或抛出异常            |
| `signal: device_connected`   | 设备插入信号，携带设备序列号                  |
| `signal: device_disconnected`| 设备拔出信号                                |

**关键类**: `DeviceMonitor(QThread)`

| 功能                      | 说明                                           |
| ------------------------- | ---------------------------------------------- |
| 后台轮询                  | 每 2 秒执行 `adb devices`                      |
| 状态变化检测              | 比对前后两次设备列表，发射连接/断开信号         |

---

### Module 3: core/device_service.py -- 业务逻辑层

**职责**: 伪装/重置的完整业务流程编排

**关键类**: `DeviceService(QThread)`

| 方法/信号               | 说明                                                        |
| ----------------------- | ----------------------------------------------------------- |
| `disguise(profile)`     | 执行伪装流程（root->remount->修改->push->reboot->验证）    |
| `reset()`               | 执行重置流程（读取原始值->修改->push->reboot->验证）        |
| `get_device_state()`    | 读取当前设备状态（odm + vendor 属性）                       |
| `signal: progress(msg)` | 进度信号，传递当前步骤文字                                  |
| `signal: error(msg)`    | 错误信号，传递错误提示文字                                  |
| `signal: finished(state)`| 完成信号，携带最终设备状态                                 |

**流程细节（disguise）**:
1. 发射 progress("设备信息修改中......")
2. adb root -> 失败则发射 error("设备无 root 权限...")
3. adb remount
4. adb shell setenforce 0
5. adb pull /odm/etc/build.prop
6. 修改 build.prop 中的三个属性
7. adb push build.prop /odm/etc/build.prop
8. 发射 progress("正在重启设备请稍后......")
9. adb reboot
10. 等待 sys.boot_completed=1
11. getprop 验证三个属性
12. 发射 finished(new_state) 或 error

---

### Module 4: ui/main_window.py -- 主窗口

**职责**: 主界面布局与事件绑定

**布局结构**:
```
+---------------------------------------------------+
| 当前设备信息  brand: [---]  manufacturer: [---]    |
|              model: [---]        [已伪装/未伪装]   |
+---------------------------------------------------+
| 伪装设备信息: [*] brand:[v] manufacturer:[v]       |
|                   model:[v]                        |
+---------------------------------------------------+
| +-----------------------------------------------+ |
| | 进度信息区                                     | |
| | 设备信息修改中......                           | |
| | 正在重启设备请稍后......                       | |
| +-----------------------------------------------+ |
+---------------------------------------------------+
|     [Start]        [Clear]        [Reset]          |
+---------------------------------------------------+
```

**关键交互**:
- Start 点击 -> 校验输入非空 -> 校验与当前设备信息不一致 -> 检查数据库 -> 可能弹出保存对话框 -> 启动 DeviceService.disguise
- Clear 点击 -> 清空三个 ComboBox
- Reset 点击 -> 启动 DeviceService.reset
- DeviceMonitor 信号 -> 更新第一行 + 按钮状态
- DeviceService.progress 信号 -> 追加进度文字
- DeviceService.error 信号 -> 显示错误文字
- ComboBox 选择变化 -> 自动补全其余字段
- 保存/导入档案后 -> 刷新 ComboBox 下拉列表

---

### Module 5: ui/save_dialog.py -- 保存/编辑对话框

**职责**: 新增/编辑设备档案的模态对话框

**字段**: brand（输入框）、manufacturer（输入框）、model（输入框）、notes（多行文本框，placeholder 提示）

**按钮**: Save / Cancel

**模式区分**: 通过构造参数区分新增（预填用户输入值）和编辑（预填数据库现有值）

---

### Module 6: ui/device_popup.py -- 设备选取弹窗

**职责**: 从数据库快捷选取设备档案

**特性**:
- 固定大小弹窗，锚定在触发按钮右下角
- 左侧 QListWidget 显示 model 列表
- 右侧 QLabel 显示备注（鼠标悬停时实时显示，无延迟）
- 右键菜单：编辑、删除
- 点击选中后发射信号携带 DeviceProfile，关闭弹窗

---

### Module 7: core/config_manager.py -- 用户配置管理

**职责**: 管理用户偏好设置（主题等），持久化到 config.json

**关键类**: `ConfigManager`

| 方法                | 说明                                    |
| ------------------- | --------------------------------------- |
| `load()`            | 从 config.json 加载配置，不存在则用默认值 |
| `save()`            | 保存配置到 config.json                  |
| `get_theme()`       | 获取当前主题（dark/light），默认 dark   |
| `set_theme(theme)`  | 设置主题并持久化                        |

**依赖**: 无外部依赖，仅标准库 `json`, `os`

---

### Module 8: ui/settings_menu.py -- 设置菜单

**职责**: 标题栏齿轮按钮的二级菜单

**特性**:
- QMenu 弹出菜单，锚定在齿轮按钮下方
- 菜单项：
  - "Import Device Data" -> 触发文件选择对话框，调用 ProfileManager.import_from()
  - "Theme: Dark / Light" -> 切换主题，调用 ConfigManager.set_theme()
- 主题切换后通过 `theme_changed` 信号通知 MainWindow 刷新样式
- 导入成功后通过 `data_imported` 信号通知 MainWindow 刷新 ComboBox 下拉列表

---

### Module 9: ui/styles.py -- 主题样式定义

**职责**: 定义 Dark 和 Light 两套 QSS 样式表

**关键函数**:

| 函数                    | 说明                                  |
| ----------------------- | ------------------------------------- |
| `get_dark_theme()`      | 返回暗色主题 QSS 字符串              |
| `get_light_theme()`     | 返回亮色主题 QSS 字符串              |
| `apply_theme(app, name)`| 根据主题名称应用 QSS 到 QApplication |

---

### Module 10: build -- 打包构建

**职责**: PyInstaller 打包配置与构建脚本

**文件**:
- `build.spec`: PyInstaller 配置文件，--onedir 模式
- `build.py`: 构建脚本，执行打包并压缩为 zip

**打包内容**:
- Python 运行时 + 依赖（PyQt6）
- adb/ 目录（adb.exe + DLL）
- data/import_sample.json
- 其他资源文件

---

## Implementation Order

| 阶段 | 模块                        | 依赖         | 说明                         |
| ---- | --------------------------- | ------------ | ---------------------------- |
| 1    | core/profile_manager.py     | 无           | 数据层，可独立开发和测试     |
| 2    | core/config_manager.py      | 无           | 配置管理，可独立开发         |
| 3    | core/adb_manager.py         | 无           | ADB 封装，可独立开发         |
| 4    | core/device_service.py      | 1, 3         | 业务逻辑编排                 |
| 5    | ui/styles.py                | 无           | 主题样式定义                 |
| 6    | ui/main_window.py           | 1, 2, 3, 4, 5 | 主界面                     |
| 7    | ui/save_dialog.py           | 1            | 保存/编辑对话框              |
| 8    | ui/device_popup.py          | 1            | 设备选取弹窗                 |
| 9    | ui/settings_menu.py         | 1, 2, 5      | 设置菜单                     |
| 10   | main.py                     | 6-9          | 应用入口，组装各模块         |
| 11   | data/import_sample.json     | 无           | 导入模板示例文件             |
| 12   | build.spec + build.py       | 10           | 打包构建                     |

---

## Risk Mitigation

| 风险                     | 影响 | 缓解策略                                            |
| ------------------------ | ---- | --------------------------------------------------- |
| 设备重启期间 USB 断开    | 高   | 重启后等待 adb wait-for-device，超时 120 秒后报错   |
| build.prop 格式不一致    | 中   | 使用正则匹配属性行，兼容不同格式                    |
| JSON 文件写入中途异常    | 中   | 先写临时文件再原子替换                              |
| PyInstaller 打包体积过大 | 中   | 使用 --exclude-module 排除不需要的 Qt 模块          |
| 内置 ADB 版本与设备不兼容| 低   | 优先使用系统 PATH 中的 adb，内置版本作为兜底        |
