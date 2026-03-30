# 002-device-info-json: 设备档案 device_info.json 与 GUI 导入配置

## 目录

- [背景与目标](#背景与目标)
- [用户故事](#用户故事)
- [功能需求](#功能需求)
- [数据与路径](#数据与路径)
- [JSON 格式](#json-格式)
- [验收标准](#验收标准)
- [Clarifications](#clarifications)
- [关联规格](#关联规格)
- [实现核对（analysis）](analysis.md)

## 背景与目标

将设备伪装模块的档案持久化从 `device_profiles.json` 统一为 **`device_info.json`**，并明确开发与打包后的路径；支持通过 JSON 文件**导入**设备信息；所有档案的增删改与导入成功后均**同步写回**配置文件。回退此前「将默认档案打入 PyInstaller 产物」的做法，改为用户/仓库维护 `device_info.json`（开发目录内提交默认值即可）。

## 用户故事

1. **作为用户**，我希望档案保存到固定的 JSON 配置文件中，开发时在模块目录下、安装后在 exe 旁 data 目录下，便于备份与版本管理。
2. **作为用户**，我希望点击「导入配置」选择 JSON 文件，将其中设备记录合并进档案库（已存在的组合跳过），并自动保存到配置文件。
3. **作为用户**，我在 GUI 或 CLI 中新增、编辑、删除档案后，配置文件应立即反映最新内容。

## 功能需求

- **FR-001**：`ProfileManager` 默认持久化路径为 `device_info.json`；路径规则见下文「数据与路径」。
- **FR-002**：任何 `add` / `update` / `delete` / `import_from` 成功后，`device_info.json` 与内存列表一致（已有原子写入逻辑保持不变）。
- **FR-003**：GUI 提供「导入配置」按钮；选择 JSON 文件后调用与 CLI 一致的导入逻辑，弹窗展示导入/跳过条数，并刷新联想数据。
- **FR-004**：若仅存在旧版 `device_profiles.json`（同级 `data` 或 `data/device_disguise/`），首次启动时**迁移**为 `device_info.json`（复制内容），避免老用户丢数据。
- **FR-005**：CLI `device profile import` 等行为不变，与同一 `device_info.json` 数据源一致。

## 数据与路径

| 运行方式 | 配置文件路径 |
|----------|----------------|
| 开发（非 frozen） | `modules/device_disguise/data/device_info.json` |
| PyInstaller 打包（frozen） | `<exe 同级目录>/data/device_info.json` |

仓库中在 `modules/device_disguise/data/device_info.json` 保留默认档案列表（与原有三条一致），不再使用 `device_profiles.json` 作为正式文件名。

## JSON 格式

与现有档案一致：**UTF-8 JSON 数组**，元素为对象，字段：

- `brand`（string，必填）
- `manufacturer`（string，必填）
- `model`（string，必填）
- `notes`（string，可选，默认 `""`）

示例：

```json
[
  { "brand": "vivo", "manufacturer": "vivo", "model": "V2505A", "notes": "备注" }
]
```

## 验收标准

| ID | 条件 |
|----|------|
| AC-01 | 无参 `ProfileManager()` 在开发环境下读写 `modules/device_disguise/data/device_info.json` |
| AC-02 | frozen 模式下读写 `<exe_dir>/data/device_info.json`（目录不存在时自动创建） |
| AC-03 | GUI「导入配置」成功合并记录并刷新联想；非法 JSON 有错误提示 |
| AC-04 | 仅存在旧 `device_profiles.json` 时能迁移出 `device_info.json` 并正确加载 |
| AC-05 | 单元测试覆盖路径解析、迁移及既有 CRUD/import |

## Clarifications

### Session 2026-03-30

- Q: 是否保留 PyInstaller 内嵌默认档案？ → A: 否，回退该方案；默认内容由仓库内 `device_info.json` 提供，打包后写入由用户在 `data` 目录维护或通过导入补充。
- Q: 导入与已有记录冲突时？ → A: `import_from` 沿用现有语义：重复 `brand+manufacturer+model` 跳过计 `skipped`。
- Q: 旧文件迁移范围？ → A: 检测 `data/device_profiles.json` 与 `data/device_disguise/device_profiles.json`（兼容曾将档案放在 exe/data 子目录的布局）。

## 关联规格

- [001-migration/spec.md](../001-migration/spec.md)：初版迁移；002 取代其中关于 `device_profiles.json` 路径的陈述，以本 spec 为准。
