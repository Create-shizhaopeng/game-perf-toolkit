# Quickstart: Agent 核心重构开发指南

**Feature**: 021-agent-core-refactor | **Date**: 2026-05-26

## 环境准备

```bash
# 在 dev 分支上工作
git checkout dev

# 确保依赖最新
uv pip install -e ".[dev]"

# 运行现有测试确认基线
python scripts/run_all_tests.py
```

## Phase 1: 基础设施下沉

### 运行测试

每个步骤完成后运行相关测试：

```bash
# agent_chat 模块测试（289 个）
python -m pytest modules/agent_chat/tests/ -v

# MCP Server 相关测试
python -m pytest tests/ -k "mcp" -v

# 全量测试
python scripts/run_all_tests.py
```

### 关键验证点

1. `toolkit/core/mcp_server.py` 不再 import `modules.agent_chat`
2. `ToolRegistry` 单例可从 `toolkit.core.tool_registry` 导入
3. `SkillRegistry` 支持 `add_search_path` 和 `scan`
4. MCP Client 可从 `toolkit.core.mcp` 导入

## Phase 2: Agent 框架化

### 目录变更

```bash
# 移动前备份确认
ls modules/agent_chat/

# 验证新目录结构
ls toolkit/agent/
ls toolkit/agent/gui/
```

### UI 验证

启动 GUI 后验证：
1. 左侧导航栏无 "Agent 智能助手" Tab
2. 右侧面板可展开/折叠
3. 输入消息后 Agent 正常回复
4. 工具调用卡片正常渲染
5. 停止按钮正常工作

## Phase 3: 模块适配

### perfetto_analysis 适配检查

```bash
# 验证 SKILL.md 存在
cat modules/perfetto_analysis/skills/perfetto-analysis/SKILL.md

# 验证 Skill 被正确索引
python -c "
from toolkit.core.skill_registry import SkillRegistry
sr = SkillRegistry()
sr.add_search_path(Path('modules/perfetto_analysis/skills'))
skills = sr.scan()
assert any(s.name == 'perfetto-analysis' for s in skills)
"
```

## 常见问题

### ImportError: cannot import name 'ToolRegistry'

Phase 1 中部分文件已移动，需要检查 import 路径：
- 旧: `from modules.agent_chat.src.tools.registry import ToolRegistry`
- 新: `from toolkit.core.tool_registry import ToolRegistry`

### Skill 未在 Agent 系统提示词中出现

1. 检查 SKILL.md 的 YAML frontmatter 格式正确
2. 检查 `platforms` 字段是否过滤了当前平台
3. 检查 Skill 目录下是否有有效的 SKILL.md 文件

### MCP Server 连接失败

1. 检查 `data/config/mcp_servers.json` 格式
2. 查看日志中的连接错误详情
3. 确认 MCP Server 进程可通过命令行单独启动
