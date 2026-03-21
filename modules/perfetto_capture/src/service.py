"""Perfetto卡顿抓取 — 服务层"""


class PerfettoCaptureService:
    """Perfetto卡顿抓取 核心业务逻辑。"""

    def get_service_info(self) -> dict:
        return {"name": "perfetto_capture", "display_name": "Perfetto卡顿抓取"}
