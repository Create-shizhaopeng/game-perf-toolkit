"""设备伪装工具 — 服务层"""


class DeviceDisguiseService:
    """设备伪装核心业务逻辑。"""

    def get_service_info(self) -> dict:
        return {"name": "device_disguise", "display_name": "设备伪装工具"}
