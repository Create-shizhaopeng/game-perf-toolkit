# -*- coding: utf-8 -*-
"""Agent 智能助手 — CLI 子命令（Typer）。"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel

agent_app = typer.Typer(help="Agent 智能助手")
sop_app = typer.Typer(help="SOP 文档管理")
agent_app.add_typer(sop_app, name="sop")

console = Console()

_ac_context: dict | None = None


def _get_config():
    """获取 AgentConfig。"""
    if _ac_context and "ac_config" in _ac_context:
        return _ac_context["ac_config"]
    from .models import load_config_with_env
    return load_config_with_env()


def _has_any_key(config) -> bool:
    return bool(config.api_key or config.glm_api_key or config.claude_api_key)


@agent_app.command("ask")
def ask(
    message: Annotated[str, typer.Argument(help="发送给 Agent 的消息")],
    sop: Annotated[Optional[str], typer.Option("--sop", help="指定 SOP 名称")] = None,
    provider: Annotated[
        Optional[str], typer.Option("--provider", help="LLM Provider (glm/claude)")
    ] = None,
) -> None:
    """向 Agent 发送消息并获取回复。"""
    asyncio.run(_ask_async(message, sop=sop, provider=provider))


async def _ask_async(
    message: str,
    sop: str | None = None,
    provider: str | None = None,
) -> None:
    """ask 命令的异步实现。"""
    config = _get_config()
    if not _has_any_key(config):
        console.print("[bold red]错误: 未配置 API Key[/bold red]")
        console.print("请设置环境变量 ZHIPUAI_API_KEY 或 ANTHROPIC_API_KEY，")
        console.print("或在 GUI 设置中配置。")
        raise typer.Exit(code=1)

    if provider:
        config.provider = provider
        if provider == "glm" and not config.api_key:
            config.api_key = config.glm_api_key
        elif provider == "claude" and not config.api_key:
            config.api_key = config.claude_api_key

    service, store = _create_service(config)

    try:
        if not service.is_ready:
            console.print("[bold red]错误: LLM Provider 初始化失败[/bold red]")
            console.print("请检查 API Key 是否正确。")
            raise typer.Exit(code=1)

        text_started = False

        def on_chunk(chunk):
            nonlocal text_started
            from .models import StreamChunkType

            if chunk.type == StreamChunkType.TEXT:
                if not text_started:
                    text_started = True
                console.print(chunk.data, end="")

            elif chunk.type == StreamChunkType.TOOL_START:
                data = chunk.data if isinstance(chunk.data, dict) else {}
                name = data.get("name", "?")
                console.print(f"\n[dim][🔧 调用: {name}][/dim]", end="")

            elif chunk.type == StreamChunkType.TOOL_END:
                data = chunk.data if isinstance(chunk.data, dict) else {}
                is_err = data.get("is_error", False)
                elapsed = data.get("elapsed_ms", 0)
                status = "❌ 失败" if is_err else "✅ 完成"
                console.print(
                    f" [dim][{status} {elapsed:.0f}ms][/dim]"
                )

            elif chunk.type == StreamChunkType.ERROR:
                console.print(f"\n[bold red]错误: {chunk.data}[/bold red]")

            elif chunk.type == StreamChunkType.USAGE:
                data = chunk.data if isinstance(chunk.data, dict) else {}
                prompt = data.get("prompt_tokens", 0)
                completion = data.get("completion_tokens", 0)
                total = data.get("total_tokens", 0)
                console.print(
                    f"\n[dim]Token: {prompt}+{completion}={total}[/dim]"
                )

        extra_prompt = ""
        if sop:
            extra_prompt = f"用户指定 SOP: {sop}"

        response = await service.chat(
            user_message=message,
            on_chunk=on_chunk,
            system_prompt=extra_prompt,
        )

        if text_started:
            console.print()

    finally:
        if store:
            store.close()


def _create_service(config):
    """创建 AgentService 和 ConversationStore。

    集成 PluginManager 工具注册和 SkillsManager。
    """
    from .memory.conversation import ConversationStore
    from .service import AgentService
    from .skills.manager import SkillsManager
    from .tools.registry import ToolRegistry

    from toolkit.core.app_paths import get_db_path, get_exe_dir

    data_dir = get_exe_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    store = ConversationStore(get_db_path("agent_chat", "conversation"))

    tool_registry = ToolRegistry()
    pm = _ac_context.get("plugin_manager") if _ac_context else None
    if pm:
        tool_registry.collect_from_plugins(pm)

    skill_search_paths = [
        module_dir / "skills",
        module_dir.parent / "perfetto_analysis" / "skills",
    ]
    skills_manager = SkillsManager(skill_search_paths)
    skills_manager.scan()
    tool_registry.register_many(skills_manager.create_agent_tools())

    service = AgentService(
        config=config,
        conversation_store=store,
        tool_registry=tool_registry,
        skills_manager=skills_manager,
    )
    return service, store


@agent_app.command("info")
def info() -> None:
    """显示 Agent 模块信息与当前配置。"""
    config = _get_config()
    has_glm = bool(config.glm_api_key)
    has_claude = bool(config.claude_api_key)
    console.print(Panel(
        f"Provider: {config.provider}\n"
        f"Model: {config.model_name}\n"
        f"Temperature: {config.temperature}\n"
        f"Language: {config.language}\n"
        f"Smart Switch: {config.smart_switch}\n"
        f"GLM Key: {'✅ 已配置' if has_glm else '❌ 未配置'}\n"
        f"Claude Key: {'✅ 已配置' if has_claude else '❌ 未配置'}\n"
        f"Workflow Learning: {config.workflow_learning_enabled}",
        title="Agent 智能助手",
    ))


@sop_app.command("list")
def sop_list() -> None:
    """列出所有可用的 SOP 文档。"""
    from rich.table import Table

    mgr = _get_sop_manager()
    sops = mgr.load_all()

    if not sops:
        console.print("[dim]暂无 SOP 文档。[/dim]")
        return

    table = Table(title="SOP 文档列表")
    table.add_column("名称", style="bold")
    table.add_column("来源")
    table.add_column("关键词")
    table.add_column("描述")

    for sop in sops:
        source_label = "内置" if sop.source.value == "builtin" else "自定义"
        table.add_row(
            sop.title or sop.path.stem,
            source_label,
            ", ".join(sop.keywords[:5]),
            (sop.description[:60] + "...") if len(sop.description) > 60 else sop.description,
        )

    console.print(table)


@sop_app.command("show")
def sop_show(
    name: Annotated[str, typer.Argument(help="SOP 名称")],
) -> None:
    """显示指定 SOP 的完整内容。"""
    mgr = _get_sop_manager()
    mgr.load_all()
    content = mgr.get_sop_content(name)

    if content is None:
        console.print(f"[bold red]SOP '{name}' 未找到。[/bold red]")
        raise typer.Exit(code=1)

    from rich.markdown import Markdown
    console.print(Panel(Markdown(content), title=f"SOP: {name}"))


def _get_sop_manager():
    """获取 SOPManager 实例。"""
    from .sop.manager import SOPManager

    module_dir = Path(__file__).resolve().parent.parent
    return SOPManager(
        builtin_dir=module_dir / "assets" / "sops",
        custom_dir=module_dir / "data" / "sops",
    )
