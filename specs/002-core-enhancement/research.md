# Research: 核心框架增强（迁移支撑）

**Branch**: `002-core-enhancement` | **Date**: 2026-03-21

## 目录

- [调研背景](#调研背景)
- [技术决策确认](#技术决策确认)
- [结论](#结论)

## 调研背景

本次增强是为旧项目迁移提供底层 API 支撑。旧项目 `_archived_source/core/adb_manager.py` 中已有成熟实现，新框架 `toolkit/core/adb_manager.py` 已包含基础能力（设备发现、属性读取），需要补充高级操作。

## 技术决策确认

### 1. ADB 命令执行方式

- **Decision**: 沿用现有的 `subprocess.run()` + `CREATE_NO_WINDOW`（Windows）方式
- **Rationale**: 已验证可靠，无需引入第三方 ADB 库
- **Reference**: 旧 `_archived_source/core/adb_manager.py` 使用相同方式

### 2. Serial 参数设计

- **Decision**: 所有新增方法 MUST 接收 `serial: str` 作为第一个参数，内部通过 `-s serial` 传递给 adb
- **Rationale**: 新架构支持多设备，不应假设单设备；旧代码部分方法缺少 serial 支持
- **Note**: 现有 `get_prop()` 和 `get_device_props()` 已支持 `serial` 参数

### 3. DeviceState 模型

- **Decision**: 从旧 `dataclass` 迁移为 Pydantic `BaseModel`，放在 `toolkit/sdk/models.py`
- **Rationale**: 与框架统一使用 Pydantic，支持 JSON Schema 生成和序列化
- **Reference**: 旧 `_archived_source/core/device_service.py` 中的 `DeviceState` dataclass

### 4. wait_for_device 实现

- **Decision**: 使用轮询 `adb -s <serial> get-state` 检测设备状态，配合超时机制
- **Rationale**: `adb wait-for-device` 本身不支持精确超时控制，轮询方式更可控
- **Alternative**: 直接使用 `adb wait-for-device`（缺点：可能无限等待）

### 5. 测试策略

- **Decision**: 所有新增方法使用 `unittest.mock` 模拟 `subprocess.run`，不依赖真实 ADB 设备
- **Rationale**: 与 001-framework-completion 中 `test_adb_manager.py` 的测试策略保持一致

## 结论

技术方案明确，沿用现有框架设计模式。核心变更集中在 `toolkit/core/adb_manager.py`（新增 7 个方法）和 `toolkit/sdk/models.py`（新增 DeviceState 模型）。
