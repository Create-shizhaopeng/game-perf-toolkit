# 旧版文档归档说明

## 目录

- [归档说明](#归档说明)
- [文档状态一览](#文档状态一览)
- [各文档详细说明](#各文档详细说明)

## 归档说明

本目录保存的是 **架构重构前（单体应用阶段）** 的文档。这些文档在新架构
（`specs/`、`modules/*/specs/`、`.specify/`）中已被部分或全部替代。

**保留目的**：
1. 迁移尚未完成的模块时需要参考旧版需求和设计
2. 新架构的 spec 文档与旧文档进行对照审计
3. UI 设计 SVG 素材仍有视觉参考价值

**何时可以删除**：当所有旧模块迁移完成、新 spec 文档已覆盖对应内容后，
经团队确认即可删除本目录。

## 文档状态一览

| 文档 | 状态 | 新架构对应 |
|------|------|-----------|
| `spec.md` | ⚠ 部分吸收 | `modules/device_disguise/specs/001-migration/spec.md` |
| `spec-push-policy.md` | ⚠ 部分吸收 | `modules/game_perf/specs/001-migration/spec.md` |
| `data-model.md` | ✅ 已吸收 | `modules/*/src/models.py` + Pydantic/dataclass |
| `impl-plan.md` | ✅ 已吸收 | `modules/*/specs/001-migration/plan.md` |
| `tasks.md` | ✅ 已吸收 | `modules/*/specs/001-migration/tasks.md` |
| `research.md` | ✅ 已吸收 | `doc/architecture/technical-decisions.md` (ADR) |
| `quickstart.md` | ⏳ 待更新 | 需要根据新架构重写用户快速上手指南 |
| `get_game_policy.md` | ⚠ 独有 | 脚本仅存在于 `_archived_source/`，待迁移 |
| `packaging-windows.md` | ❌ 过时 | 路径和构建方式已变更，需全面重写 |
| `design/` | ⚠ 独有 | SVG 设计稿仍有 UI 参考价值 |

### 状态说明

- ✅ **已吸收**：内容已完全迁移到新架构文档，保留仅作历史参考
- ⚠ **部分吸收 / 独有**：部分内容尚未迁移，或包含新架构中不存在的信息
- ⏳ **待更新**：概念仍有价值但需要根据新架构重写
- ❌ **过时**：内容已不适用于当前架构

## 各文档详细说明

### spec.md — 设备伪装功能规格（部分吸收）

旧版 `ModifyModelNameTool` 功能规格，包含详细的场景描述和验收标准。
新架构中 `modules/device_disguise/specs/` 已覆盖核心功能，但旧 spec 中
部分边缘场景描述可能更细致，迁移时建议对照。

### spec-push-policy.md — 性能配置推送规格（部分吸收）

旧版 Push Policy 选项卡的完整规格，包含 XML 校验、版本管理、推送流程。
新架构 `modules/game_perf/specs/001-migration/` 已覆盖主要功能。
**注意**：旧 spec 中 `get_game_policy.py` 的解析逻辑标记为延后处理，
该脚本目前仅存在于 `_archived_source/core/GamepolicyParse/` 中。

### data-model.md — 数据模型（已吸收）

`DeviceProfile`、`DeviceState` 等实体定义。已迁移为 Pydantic model
(`modules/device_disguise/src/models.py`) 和 dataclass
(`modules/game_perf/src/models.py`)。

### get_game_policy.md — 策略提取脚本说明（独有）

该文档描述了从 `gameperfconfig.xml` 按游戏提取策略的脚本用法。
**重要**：对应脚本 `get_game_policy.py` 在新架构 `scripts/` 中不存在，
完整实现仅在 `_archived_source/core/GamepolicyParse/` 中。
game_perf 模块后续需要决定是否将此功能迁入。

### design/ — UI 设计稿（独有）

包含 4 个 SVG 设计稿文件，展示旧版 UI 的暗色/亮色主题和弹窗设计。
新架构 GUI 已重新设计（VS Code 风格），但这些 SVG 仍可作为视觉参考。

### packaging-windows.md — Windows 打包说明（过时）

引用的路径（`lv-game-toolkit/source/`、`build_windows.bat`）已不存在。
新架构使用 `scripts/build.py` + PyInstaller，需要全面重写。
