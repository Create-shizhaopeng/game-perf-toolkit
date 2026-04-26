# lv-game-toolkit 开发速查

（完整硬约束见根目录 `CLAUDE.md` 「开发规范」章节。本文件仅保留知识源指针和补充速查。）

## 常用命令

```bash
python -m toolkit.app              # 启动 GUI
python scripts/run_all_tests.py    # 运行全部测试
python scripts/create_module.py <name>  # 创建新模块
```

## 知识源指针（按需查阅，不要全量加载）

| 需要了解 | 查阅位置 |
|---------|---------|
| 架构原则与技术栈 | `.specify/memory/constitution.md` |
| 开发流程 | `.claude/rules/spec-workflow.md` |
| 项目进度 | `docs/PROGRESS.md` |
| 踩坑经验 | `docs/experience/development-pitfalls.md` |
| 模块开发指南 | `docs/knowledge/module-development-guide.md` |
| 特定模块约束 | `modules/<name>/AGENTS.md` |
| 项目知识库 | `docs/knowledge/README.md` |
| 团队规范 | `docs/team/` |
| 架构设计 | `docs/architecture/architecture-overview.md` |
