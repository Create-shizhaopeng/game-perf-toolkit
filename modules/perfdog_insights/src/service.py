"""PerfDog 分析 — 服务层占位（逻辑在 toolkit.core.perfdog）。"""


class PerfdogInsightsService:
    """模块服务占位，便于后续扩展持久化等。"""

    def get_service_info(self) -> dict:
        return {"name": "perfdog_insights", "display_name": "PerfDog分析"}
