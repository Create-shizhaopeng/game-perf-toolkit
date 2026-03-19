# Data Model: ModifyModelNameTool

**Created**: 2026-03-08

---

## Entities

### 1. DeviceProfile（设备档案）

持久化实体，存储在 `data/device_profiles.json` 中。

| 字段         | 类型   | 约束               | 说明                                |
| ------------ | ------ | ------------------ | ----------------------------------- |
| brand        | string | 必填，非空         | 设备品牌                            |
| manufacturer | string | 必填，非空         | 设备制造商                          |
| model        | string | 必填，非空         | 设备型号                            |
| notes        | string | 可选，默认空字符串 | 备注（如适用的高帧游戏）            |

**唯一约束**: `(brand, manufacturer, model)` 组合唯一，不区分大小写。

**验证规则**:
- brand、manufacturer、model 不得为空或仅含空白字符
- 新增/编辑时若 `(brand, manufacturer, model)` 组合与已有记录冲突，拒绝操作并提示用户

**存储格式**:

```json
[
  {
    "brand": "vivo",
    "manufacturer": "vivo",
    "model": "V2505A",
    "notes": "支持120帧原神、王者荣耀"
  },
  {
    "brand": "OPPO",
    "manufacturer": "OPPO",
    "model": "PGJM10",
    "notes": "Find X7 Ultra，支持120帧和平精英"
  }
]
```

### 2. DeviceState（设备运行状态）

运行时实体，不持久化，存在于应用内存中。

| 字段                  | 类型    | 来源                                                       | 说明                   |
| --------------------- | ------- | ---------------------------------------------------------- | ---------------------- |
| is_connected          | boolean | `adb devices` 轮询结果                                    | 设备是否已连接         |
| current_brand         | string  | `adb shell getprop ro.product.odm.brand`                   | 当前 odm brand         |
| current_manufacturer  | string  | `adb shell getprop ro.product.odm.manufacturer`            | 当前 odm manufacturer  |
| current_model         | string  | `adb shell getprop ro.product.odm.model`                   | 当前 odm model         |
| original_brand        | string  | `adb shell getprop ro.product.vendor.brand`                | 原始 vendor brand      |
| original_manufacturer | string  | `adb shell getprop ro.product.vendor.manufacturer`         | 原始 vendor manufacturer |
| original_model        | string  | `adb shell getprop ro.product.vendor.model`                | 原始 vendor model      |
| is_disguised          | boolean | `current_* != original_*` 比较结果                         | 是否处于伪装状态       |

**状态转换**:

```
[未连接] --设备插入--> [已连接/未伪装]
[已连接/未伪装] --执行伪装--> [已连接/已伪装]
[已连接/已伪装] --执行重置--> [已连接/未伪装]
[已连接/*] --设备拔出--> [未连接]
```

### 3. AppConfig（应用配置）

持久化实体，存储在 `data/config.json` 中。

| 字段     | 类型   | 约束                  | 说明                 |
| -------- | ------ | --------------------- | -------------------- |
| theme    | string | "dark" 或 "light"     | 当前主题偏好         |
| adb_path | string | 可选，默认空字符串    | 用户自定义 adb 路径  |

**默认值**: `{"theme": "dark", "adb_path": ""}`

**存储格式**:

```json
{
  "theme": "dark",
  "adb_path": ""
}
```

**加载策略**:
- 启动时读取 `data/config.json`
- 文件不存在或字段缺失时使用默认值
- 每次配置变更后立即写回文件

**ADB 路径解析优先级**:
1. 系统 PATH 中的 adb（`shutil.which("adb")`）
2. 用户自定义路径（`adb_path` 字段，若非空）
3. 工具内置 `adb/adb.exe`

---

## CRUD 操作矩阵

| 操作 | 触发场景                           | 规则                                         |
| ---- | ---------------------------------- | -------------------------------------------- |
| 创建 | Scenario 4 保存对话框 Save         | 唯一键检查 -> 写入 JSON -> 刷新内存缓存      |
| 查询 | 自动补全、选取弹窗、Start 前检查   | 从内存缓存查询，支持按字段模糊匹配           |
| 更新 | Scenario 8 编辑对话框 Save         | 唯一键冲突检查 -> 更新 JSON -> 刷新缓存      |
| 删除 | Scenario 9 右键删除确认            | 确认对话框 -> 从 JSON 移除 -> 刷新缓存       |
| 导入 | Scenario 10 选择 JSON 文件导入     | 解析 JSON -> 按唯一键去重 -> 合并写入 -> 刷新缓存 |

---

## 文件 I/O 策略

### device_profiles.json

- **启动时**: 读取 `data/device_profiles.json` 加载到内存列表
- **每次写操作后**: 将完整列表序列化回 JSON 文件（原子覆盖写）
- **文件不存在时**: 自动创建空数组 `[]`
- **编码**: UTF-8（支持中文备注）
- **格式化**: `json.dump` 使用 `indent=2, ensure_ascii=False` 保持可读性

### config.json

- **启动时**: 读取 `data/config.json`，缺失字段用默认值填充
- **配置变更时**: 立即写回文件（如主题切换）
- **文件不存在时**: 自动创建默认配置 `{"theme": "dark", "adb_path": ""}`
- **编码**: UTF-8
- **格式化**: `json.dump` 使用 `indent=2`
