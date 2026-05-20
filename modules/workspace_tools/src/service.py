"""性能配置对比 — 服务层（模块 workspace_tools）"""

from __future__ import annotations

from . import strings_service as s


class WorkspaceToolsService:
    """性能配置对比模块业务逻辑（Bootstrap 阶段仅占位）。"""

    def get_service_info(self) -> dict[str, str]:
        return {"name": "workspace_tools", "display_name": s.SERVICE_DISPLAY_NAME}
