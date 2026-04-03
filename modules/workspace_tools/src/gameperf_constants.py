"""gameperfconfig 路径与缓存常量（与 game_perf 产品约定对齐，本模块内文档化复制）"""

from __future__ import annotations

# 设备上标准路径（与 GamePerfService.REMOTE_CONFIG_PATH 一致）
REMOTE_GAMEPERF_CONFIG_PATH: str = "/system/etc/gameperfconfig.xml"

# 拉取到本地后的固定文件名（与 game_perf pull 缓存一致）
LOCAL_GAMEPERF_CONFIG_BASENAME: str = "gameperfconfig.xml"

# 位于应用 data_dir 下，与 game_perf 的 pull_cache 语义一致
PULL_CACHE_SUBDIR: str = "pull_cache"
