# Perfetto 抓取模块迁移 — 实现计划

## 目录

- [技术上下文](#技术上下文)
- [Constitution 检查](#constitution-检查)
- [实现阶段](#实现阶段)
- [风险与缓解](#风险与缓解)
- [依赖关系](#依赖关系)

## 技术上下文

### 源项目技术栈
- Python 3.10+，纯标准库
- 自定义 Adb 类（subprocess 封装）
- JSON 配置文件 + 手写校验
- argparse CLI + stdin 交互模式

### 目标技术栈
- Python 3.12+
- AdbManager（toolkit 核心，需扩展 input_text + shell_raw）
- Pydantic 配置模型
- Typer CLI
- PyQt6 GUI（QThread + pyqtSignal）
- pluggy 插件注册

### Constitution 检查

| Constitution 原则 | 对齐措施 |
|---|---|
| 插件 context 键名 MUST 使用 `pe_` 前缀 | `pe_service`, `pe_adb` |
| ADB stdout/stderr 访问 MUST 使用 `or ""` 保护 | 所有 shell_raw 结果访问加保护 |
| GUI 后台线程 MUST 通过 pyqtSignal 与主线程通信 | CaptureWorker(QThread) + signals |
| service 层 MUST NOT 包含 PyQt6 代码 | service.py 纯同步逻辑 |

## 实现阶段

### Phase 0: ADB 核心扩展（主模块）

**范围**: `toolkit/core/adb_manager.py`

1. `_run_cmd_raw()` 新增 `input_text` 参数
2. 新增 `shell_raw()` 方法
3. 补充对应单元测试

### Phase 1: 数据模型与配置

**范围**: `modules/perfetto_capture/src/`

1. `models.py` — CaptureConfig(Pydantic)、TraceItem、CaptureSession、RunningTrace 等
2. `config_manager.py` — 配置加载/保存/验证/默认值
3. `assets/config.json` — 默认配置模板

### Phase 2: 抓取引擎（Service 层）

**范围**: `modules/perfetto_capture/src/service.py`

1. 迁移 `build_pbtxt_config()` — pbtxt 生成
2. 迁移 `start_tracing()` / `stop_tracing()` — 适配 AdbManager.shell_raw()
3. 迁移 `ensure_device_trace_dir()` / `probe_perfetto_capabilities()`
4. 实现 `PerfettoCaptureService` 完整 API
5. 会话管理（开始/保存/停止/导出）
6. 断线检测与重连逻辑

### Phase 3: CLI 命令

**范围**: `modules/perfetto_capture/src/cli_commands.py`

1. `perfetto info` — 显示模块信息
2. `perfetto start` — 启动抓取（-t/-b/-o）
3. `perfetto config show/reset` — 配置管理

### Phase 4: GUI 页面

**范围**: `modules/perfetto_capture/src/gui_tab.py`

1. 配置面板（左侧上方）
2. 会话状态面板（左侧中间）
3. 控制按钮（左侧下方）
4. 日志面板（右侧）
5. CaptureWorker(QThread) 后台抓取
6. 按钮状态联动

### Phase 5: 插件集成

**范围**: `modules/perfetto_capture/src/plugin.py`

1. hookimpl 注册完善
2. on_startup context 键注册
3. EventBus 事件发布

### Phase 6: 测试与验证

**范围**: `modules/perfetto_capture/tests/`

1. 迁移 5 个原有测试（适配新接口）
2. 新增 service 层测试
3. 新增配置模型测试
4. spec analysis 一致性检查

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| AdbManager.shell_raw 改动影响现有模块 | 新增方法，不修改已有签名，回归测试覆盖 |
| perfetto 设备兼容性 | 保留原有的 trace_dir 回退机制 |
| GUI 线程安全 | 严格使用 QThread + pyqtSignal，参照 P08 踩坑记录 |
| PyInstaller 打包路径 | 使用 ROOT_DIR 解析，参照 P14 踩坑记录 |

## 依赖关系

```
Phase 0 (ADB 扩展)
    ↓
Phase 1 (数据模型) ←── Phase 2 (Service)
                            ↓
               Phase 3 (CLI) + Phase 4 (GUI) ←── 可并行
                            ↓
                    Phase 5 (插件集成)
                            ↓
                    Phase 6 (测试验证)
```
