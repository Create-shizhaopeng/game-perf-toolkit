# Implementation Plan: Skill 知识层级应用 (G5)

**Branch**: `016-skill-knowledge-integration` | **Date**: 2026-04-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/016-skill-knowledge-integration/spec.md`

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
- [Phase 0: Research](#phase-0-research)
- [Phase 1: Design](#phase-1-design)
  - [pa_read_knowledge 工具实现](#pa_read_knowledge-工具实现)
  - [_build_toc_summary 辅助函数](#_build_toc_summary-辅助函数)
  - [_extract_section_by_anchor 辅助函数](#_extract_section_by_anchor-辅助函数)
  - [工具注册和压缩配置](#工具注册和压缩配置)
  - [SOP 引用指针模板](#sop-引用指针模板)

## Summary

新增第 10 个 pa_* 工具 `pa_read_knowledge`，实现两级按需加载 Skill 知识资产。Level 1 返回文件目录概览（摘要），Level 2 返回指定章节详情。同时在 SOP 文件中添加引用指针，指向 Skill 的 L2/L3 知识资产（patterns、SQL 模板、案例），建立 SubAgent 到 Skill 知识层级的通道。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: pydantic_ai (ToolReturn), pathlib
**Storage**: 文件系统（Skill 目录下的 Markdown 文件）
**Testing**: pytest
**Target Platform**: Windows + Linux
**Project Type**: desktop-app (module: perfetto_analysis)

## Constitution Check

| Gate | Status | Note |
|------|--------|------|
| Plugin-First | ✅ Pass | 修改仅限 perfetto_analysis 模块内部 |
| Three-Surface Unity | ✅ Pass | 工具通过 SubAgent 暴露，不涉及 GUI/CLI |
| Presentation Separation | ✅ Pass | 无 GUI/CLI 代码变更 |
| Dependency Inversion | ✅ Pass | 不引入跨模块依赖 |
| Spec-Driven | ✅ Pass | 遵循 Speckit 完整工作流 |

## Project Structure

```text
modules/perfetto_analysis/
├── src/agent/
│   └── tools.py               # [修改] 新增 pa_read_knowledge 工具 + 压缩配置
├── skills/perfetto-analysis/
│   ├── sop/*.md                # [修改] 添加引用指针
│   ├── patterns/*.md           # [只读] L2 知识资产
│   ├── sql-patterns.md         # [只读] L2 知识资产
│   └── cases/*.md              # [只读] L3 知识资产
└── tests/
    └── test_g5_skill_knowledge.py  # [新增] G5 单元测试
```

## Phase 0: Research

### R1: Skill 目录路径解析

**Decision**: 使用相对路径从 `tools.py` 定位 Skill 目录。

```python
_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills" / "perfetto-analysis"
```

`tools.py` 位于 `modules/perfetto_analysis/src/agent/tools.py`，`parents[2]` = `modules/perfetto_analysis/`，加上 `skills/perfetto-analysis` 即可定位。

**Rationale**: 避免硬编码绝对路径，适配不同安装位置。

### R2: 锚点匹配策略

**Decision**: 锚点从 Markdown 标题生成，规则为：标题转小写、去中文标点、空格改 `-`。与项目 `markdown-docs` 规则一致。

```python
def _heading_to_anchor(heading: str) -> str:
    """Markdown 标题 → 锚点。"""
    anchor = heading.lstrip("#").strip().lower()
    anchor = re.sub(r"[，。、；：！？（）【】]", "", anchor)
    return re.sub(r"\s+", "-", anchor)
```

### R3: pa_read_knowledge 直接构造 ToolReturn

**Decision**: `pa_read_knowledge` 直接返回 `ToolReturn`，不经过 `_make_tool_return` + `ResultCompressor`。原因：
1. 知识文本不是 trace 数据，不需要结构化压缩
2. L1/L2 输出已有内置长度限制（L1 ~200 token, L2 ≤2000 字符）
3. 在 `COMPRESSION_PROFILES` 中注册 `keep_all` 以保持工具注册表完整性（便于遥测和审计），但工具内部直接构造 ToolReturn 而非调用 `_make_tool_return`

## Phase 1: Design

### pa_read_knowledge 工具实现

在 `tools.py` 的 `build_analysis_tools` 函数内新增：

```python
_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills" / "perfetto-analysis"

def pa_read_knowledge(resource_path: str) -> ToolReturn:
    """两级加载 Perfetto 分析知识库资源。

    Level 1（无锚点）: 返回文件章节目录 + 每章节一句话摘要
    Level 2（带锚点）: 返回指定章节完整内容（≤2000字符）

    Args:
        resource_path: 相对于 skills/perfetto-analysis/ 的路径
            Level 1: "patterns/root-cause-patterns.md"
            Level 2: "patterns/root-cause-patterns.md#cpu-调度抢占"
    """
    _notify_tool_call("pa_read_knowledge", {"resource_path": resource_path})

    path_part, _, anchor = resource_path.partition("#")
    full_path = (_SKILLS_DIR / path_part).resolve()

    if not full_path.exists():
        _notify_tool_result("pa_read_knowledge", {"error": f"资源不存在: {path_part}"})
        return _make_error_return("pa_read_knowledge", f"资源不存在: {path_part}")

    try:
        if not full_path.is_relative_to(_SKILLS_DIR.resolve()):
            return _make_error_return("pa_read_knowledge", "路径越界")
    except ValueError:
        return _make_error_return("pa_read_knowledge", "路径越界")

    content = full_path.read_text(encoding="utf-8")

    if anchor:
        section = _extract_section_by_anchor(content, anchor)
        if not section:
            _notify_tool_result("pa_read_knowledge", {"error": f"锚点不存在: #{anchor}"})
            return _make_error_return("pa_read_knowledge", f"锚点不存在: #{anchor}")
        _notify_tool_result("pa_read_knowledge", f"Level 2: {len(section)} chars")
        return ToolReturn(
            return_value=section[:2000],
            metadata={
                "resource_path": resource_path, "level": 2,
                "tool_name": "pa_read_knowledge",
            },
        )
    else:
        toc = _build_toc_summary(content)
        _notify_tool_result("pa_read_knowledge", f"Level 1: {len(toc)} chars")
        return ToolReturn(
            return_value=toc if toc else content[:500],
            metadata={
                "resource_path": resource_path, "level": 1,
                "tool_name": "pa_read_knowledge",
                "hint": "使用 #锚点 获取具体章节详情",
            },
        )
```

### _build_toc_summary 辅助函数

在 `tools.py` 模块级别（`build_analysis_tools` 外部）定义：

```python
def _build_toc_summary(content: str) -> str:
    """从 Markdown 内容提取章节目录 + 每章节首句摘要。"""
    lines = content.split("\n")
    toc_parts: list[str] = []
    current_heading: str | None = None
    first_line_after: str | None = None

    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            if current_heading and first_line_after:
                toc_parts.append(f"{current_heading} — {first_line_after}")
            elif current_heading:
                toc_parts.append(current_heading)
            current_heading = line.strip()
            first_line_after = None
        elif current_heading and not first_line_after and line.strip():
            first_line_after = line.strip()[:80]

    if current_heading:
        if first_line_after:
            toc_parts.append(f"{current_heading} — {first_line_after}")
        else:
            toc_parts.append(current_heading)

    return "\n".join(toc_parts)
```

### _extract_section_by_anchor 辅助函数

```python
def _extract_section_by_anchor(content: str, anchor: str) -> str:
    """根据锚点提取 Markdown 章节内容。"""
    import re

    lines = content.split("\n")
    target_anchor = anchor.lower().strip()
    start_idx: int | None = None
    start_level: int = 0

    for i, line in enumerate(lines):
        if line.startswith("#"):
            heading_anchor = _heading_to_anchor(line)
            if heading_anchor == target_anchor:
                start_idx = i
                start_level = len(line) - len(line.lstrip("#"))
                continue
            if start_idx is not None:
                current_level = len(line) - len(line.lstrip("#"))
                if current_level <= start_level:
                    return "\n".join(lines[start_idx:i]).strip()

    if start_idx is not None:
        return "\n".join(lines[start_idx:]).strip()
    return ""


def _heading_to_anchor(heading: str) -> str:
    """Markdown 标题 → 锚点。"""
    import re
    anchor = heading.lstrip("#").strip().lower()
    anchor = re.sub(r"[，。、；：！？（）【】]", "", anchor)
    return re.sub(r"\s+", "-", anchor)
```

### 工具注册和压缩配置

在 `COMPRESSION_PROFILES` 中注册：

```python
"pa_read_knowledge": CompressionProfile(strategy="keep_all"),
```

在 `build_analysis_tools` 返回列表中添加：

```python
return [
    pa_trace_overview,
    pa_detect_jank,
    pa_analyze_dimension,
    pa_list_dimensions,
    pa_get_history,
    pa_find_slices,
    pa_execute_sql,
    pa_analyze_anr,
    pa_analyze_memory,
    pa_read_knowledge,  # G5 新增
]
```

### SOP 引用指针模板

在每个 SOP 文件末尾或关键判断条件后追加引用指针块：

```markdown
## 深入分析资源

调用 `pa_read_knowledge` 获取以下知识资产:
- 根因模式库: `pa_read_knowledge("patterns/root-cause-patterns.md")`
- SQL 查询模板: `pa_read_knowledge("sql-patterns.md")`
- 历史案例: `pa_read_knowledge("cases/face-unlock-audio-stutter.md")`
```

每个场景 SOP 追加与该场景相关的引用指针，例如 jank-analysis.md 追加 CPU 调度、Binder 超时等相关引用。
