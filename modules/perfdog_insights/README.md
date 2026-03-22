# PerfDog 分析（`perfdog_insights`）

Toolkit 插件：离线导入 PerfDog **`.xlsx/.xlsm`**，生成摘要、洞察与建议；侧栏 **「PerfDog分析」**。结构与 **`game_perf`** 对齐（`specs/`、`tests/`、`fixtures/`、`assets/`、`.specify/`、`.cursor/`）。

## 目录布局（与 `modules/game_perf` 同型）

```text
modules/perfdog_insights/
├── AGENTS.md                 # AI / Agent 规则（目录与 game_perf 一致）
├── README.md                 # 本文件
├── manifest.json
├── assets/                   # 模块静态资源（占位 .gitkeep）
├── fixtures/                 # 模块测试数据（占位；大夹具可与根 tests 共用）
├── specs/
│   └── 004-perfdog-import-insights/   # 入口索引 → 根目录 specs/004-... 正文
├── tests/                    # 模块 pytest（Service 等）
├── .cursor/commands/         # 模块级 speckit slash 命令
├── .specify/                 # 模块级 speckit（constitution、脚本、模板）
└── src/
    ├── __init__.py
    ├── plugin.py
    ├── service.py            # PerfdogInsightsService
    ├── models.py             # 跨端类型再导出
    ├── cli_commands.py
    ├── gui_tab.py
    ├── analysis_worker.py
    ├── joint_worker.py
    └── migrations/           # manifest 占位（当前无 DB 表）
```

## 规格与实现记录（权威源）

| 说明 | 路径 |
|------|------|
| **正文**（spec / plan / tasks；数据模型与实现记录在 **plan** 内） | 仓库根 [`specs/004-perfdog-import-insights/`](../../specs/004-perfdog-import-insights/) |
| **模块内索引** | [`specs/004-perfdog-import-insights/spec.md`](specs/004-perfdog-import-insights/spec.md)（链接到根目录，避免双份维护） |

联合分析依赖 **游戏性能** Tab 写入的 **`gp_joint_policy_snapshot`**。环境变量 **`SPECIFY_FEATURE=004-perfdog-import-insights`** 用于根目录 Speckit。

## 测试

```powershell
# 仅本模块
python -m pytest modules/perfdog_insights/tests/ -q

# 全量分组（已登记于 scripts/run_all_tests.py）
.venv\Scripts\python.exe scripts\run_all_tests.py
```

核心解析烟测另见根目录 **`tests/test_perfdog_workbook.py`**。
