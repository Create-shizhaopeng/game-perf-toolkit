# get_game_policy.py 使用说明

## 目录

- [功能概述](#功能概述)
- [脚本位置](#脚本位置)
- [依赖与环境](#依赖与环境)
- [命令行用法](#命令行用法)
  - [参数说明](#参数说明)
  - [输出格式说明](#输出格式说明)
- [使用示例](#使用示例)
- [匹配规则](#匹配规则)
- [返回值与错误](#返回值与错误)
- [与文档的对应关系](#与文档的对应关系)

## 功能概述

从 `gameperfconfig.xml` 中按**游戏名称**或**包名**提取指定游戏的策略配置（即该游戏对应的整段 `Game` 节点及其子节点）。解析在脚本内完成，无需将整个配置文件加载到外部上下文，便于在流水线或本地重复使用。

## 脚本位置

- 路径：`scripts/get_game_policy.py`  
- 建议在项目根目录（即 `gameperfconfig.xml` 所在目录）执行，或通过参数指定配置文件路径。

## 依赖与环境

- Python 3.6+，仅使用标准库（`xml.etree.ElementTree`、`argparse`、`pathlib`）。  
- 输出 JSON 时无需额外依赖；若需更好排版，可安装 `json`（已内置于标准库）。

## 命令行用法

```text
python scripts/get_game_policy.py [game] [-f CONFIG] [-o FORMAT] [--pkg] [-O FILE] [--preenv]
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `game` | 游戏名称或包名，支持部分匹配（如「和平精英」或 `pubgmhd`）；与 `--pkg` 同用时视为包名 | 和平精英 |
| `-f`, `--config` | 配置文件路径 | `gameperfconfig.xml`（当前目录） |
| `-o`, `--output` | 输出格式：`xml` / `json` / `summary` / `report` | `xml` |
| `--pkg` | 按包名匹配：`game` 参数仅与 pkg 属性匹配（可传完整包名或片段，如 `com.tencent.lolm` 或 `lolm`） | 关闭 |
| `-O`, `--out-file` | 将输出直接写入指定文件（UTF-8 编码），避免 PowerShell 重定向乱码；若目标路径所在目录不存在则自动创建 | 不写文件 |
| `--preenv` | 是否同时输出 PreEnv 中的 CPU/GPU 频率表（便于解释频点档位） | 不输出 |

### 输出格式说明

- **xml**：将匹配到的 `Game` 子树序列化为 XML 字符串输出，便于直接查看或二次解析。  
- **json**：将 `Game` 转为嵌套字典后以 JSON 输出（含 BindCore、Mode、SceneOpt、Policy 等），便于程序处理。  
  - **FpsAdjustLevel / FpsAdjustTime**：在 Game 下若有则出现在顶层；若某 Mode 下单独配置则出现在该 Mode 对象内（与 `gameperfconfig_report.md` 中「Game 或 Mode 下可选」一致）。  
  - **JankAdjustLevel / JankAdjustTime**：同上，Game 或 Mode 下若有则一并提取（仅 TGPA 类游戏可能配置）。  
  - **BindCore**：Game 下及**各 Mode 下**若有则均提取；每个线程的 `value` 为十六进制掩码，同时输出 **value_binary**（8 位二进制字符串，如 `01000000`）。  
  - **Policy / SceneOpt 中的 freq 项**：除原始档位 `value`（如 `0_3`）外，增加 **freq_display**，为根据 PreEnv 频率表换算后的具体频率范围（CPU 为 GHz，GPU 为 MHz，如 `0.38～0.96 GHz`、`443～734 MHz`；`-1_-1` 显示为「无限制」）。  
- **summary**：输出可读的文本摘要（游戏名、pkg、ThermalTempType、FpsAdjust、**JankAdjust**、BindCore、SceneOpt、各 Mode 的 ThermalSceneCode / FpsAdjust / **JankAdjust** / **BindCore** / PerfHint / TempLevel 频点等）。
- **report**：输出固定版式的 Markdown 分析报告，结构如下：
  - **Header**：仅游戏名、包名
  - **目录**：自动生成各章节跳转链接
  - **一、基本信息**：精简表格（ThermalTempType、游戏级 BindCore/SceneOpt/FpsAdjust 有无）
  - **二、绑核（BindCore）**：线程名 / mask(hex) / 二进制表格，无则写「无」
  - **三、场景策略（SceneOpt）**：有则列 Scene id/time/频点，无则「无」
  - **四、各模式温控与频点**：帧率调节已合并到此章节。每模式含 ThermalSceneCode、PerfHint、帧率调节说明、TempLevel 温控表格。表格基准列从 PreEnv 动态获取（Gold / Prime / Gpu 等）；有 FpsAdjust 时自动追加 N 列 boost（如 `Gold boost | Prime boost | Gpu boost`），值为 FpsAdjustLevel 按 cluster 顺序偏移后解析的实际频率（CPU 簇索引 +N，GPU 索引 −N）
  - **五、分析与建议**：占位段落，由 agent 调用模型能力根据前四节做全面分析，给出修改建议及需用户提供的信息以便进一步分析

使用 `--preenv` 时，会在主输出前增加 PreEnv 频率表信息（json 下为结构化 PreEnv，其余为简要档位数量说明）。  
**说明**：json / summary 下的绑核二进制与频率解析依赖配置文件中的 PreEnv 节点；若 PreEnv 缺失或无对应 cluster，则仅输出原始 value，不生成 value_binary / freq_display。

## 使用示例

1. **提取「和平精英」配置，输出 XML（默认）**  
   ```bash
   python scripts/get_game_policy.py
   # 或
   python scripts/get_game_policy.py 和平精英 -f gameperfconfig.xml -o xml
   ```

2. **按包名提取并输出 JSON**  
   ```bash
   python scripts/get_game_policy.py pubgmhd -f gameperfconfig.xml -o json
   ```

3. **输出文本摘要并带 PreEnv 频率表**  
   ```bash
   python scripts/get_game_policy.py 和平精英 -o summary --preenv
   ```

4. **指定配置文件路径**  
   ```bash
   python scripts/get_game_policy.py 使命召唤 -f path/to/gameperfconfig.xml -o summary
   ```

5. **按包名提取固定格式分析报告并直接写入 UTF-8 文件**  
   ```bash
   python scripts/get_game_policy.py --pkg com.tencent.lolm -o report -O GamePolicyAnalysisReport/英雄联盟手游-策略分析报告.md
   ```

6. **按游戏名提取报告输出到终端**  
   ```bash
   python scripts/get_game_policy.py 和平精英 -o report
   ```

## 匹配规则

- 在 `GamePolicy` 下遍历所有 `Game` 节点。  
- 若传入的 `game` 字符串在某个 `Game` 的 **name** 或 **pkg** 属性中出现（不区分大小写），则命中该游戏；pkg 为逗号分隔多包名时，会按单个包名拆分后匹配。  
- 若有多个游戏匹配（少见），脚本会返回第一个匹配项。

## 返回值与错误

- 成功：向标准输出写入所选格式的内容（或通过 `-O` 写入文件），退出码 0。  
- 配置文件不存在：标准错误输出提示，退出码 1。  
- 未找到匹配游戏：标准错误输出提示，退出码 2。

## 与文档的对应关系

- 提取出的 `Game` 节点结构与 `gameperfconfig_report.md` 中「Game（GamePolicy 下）」及下属标签说明一致。  
- 频点档位含义、TempLevel 生效档位、BindCore mask 等说明见报告文档；PreEnv 频率表与「和平精英」的频点解释见 `GamePolicyAnalysisReport/和平精英-策略说明.md`。
