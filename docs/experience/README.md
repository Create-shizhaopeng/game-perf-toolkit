# 项目经验库

## 目录

- [概述](#概述)
- [经验清单](#经验清单)
- [经验沉淀流程](#经验沉淀流程)

## 概述

本目录存放 lv-game-toolkit 项目的开发经验积累，包括踩坑指南和经验模式提炼。

## 经验清单

| 文档 | 说明 | 最后更新 |
|------|------|---------|
| [development-pitfalls.md](development-pitfalls.md) | 踩坑指南（25 项 + 按子系统快速索引） | 2026-03-31 |

## 经验沉淀流程

```text
开发中遇到问题
    ↓
判断经验层级
    ├── 模块特定 → modules/<name>/docs/
    ├── 项目通用 → docs/experience/ 或 docs/knowledge/
    └── 团队通用 → docs/team/
    ↓
记录格式：现象 → 根因 → 解法 → 预防
    ↓
更新索引文件（README.md / INDEX.md）
```
