"""插件基类 — 所有模块的 plugin.py 必须继承此类"""

from __future__ import annotations

from abc import ABC


class BasePlugin(ABC):
    """所有模块插件的抽象基类。

    模块的 plugin.py 中定义一个继承此类的具体类，
    并通过 @hookimpl 标记实现 ToolkitHookSpec 中定义的钩子。
    """

    context: dict = {}
