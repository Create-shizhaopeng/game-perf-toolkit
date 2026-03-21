"""游戏性能配置 — 服务层"""


class GamePerfService:
    """游戏性能配置核心业务逻辑。"""

    def get_service_info(self) -> dict:
        return {"name": "game_perf", "display_name": "游戏性能配置"}
