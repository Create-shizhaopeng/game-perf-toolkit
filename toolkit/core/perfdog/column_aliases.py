"""PerfDog 导出列名别名 → 内部统一列名（snake_case）。"""

from __future__ import annotations

import re
import unicodedata


def normalize_header_cell(value: object) -> str:
    """将表头单元格规范化为可匹配的小写键。"""
    if value is None:
        return ""
    s = str(value).strip()
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s)
    return s.lower()


# 规范化别名 → 内部列名
_ALIASES: dict[str, str] = {
    # 时间
    "time": "time_ms",
    "time(ms)": "time_ms",
    "time (ms)": "time_ms",
    "时间": "time_ms",
    "时间(ms)": "time_ms",
    "timestamp": "time_ms",
    # 绝对/相对时间（与 time 列并存时互不覆盖内部名）
    "captime": "cap_time_ms",
    "abstime": "abs_time_ms",
    "absolutetime": "abs_time_ms",
    "relativetime": "rel_time_ms",
    "monotime": "mono_time",
    # FPS
    "fps": "fps",
    "1%low(fps)": "fps_p1_low",
    "1% low(fps)": "fps_p1_low",
    "frame rate": "fps",
    "framerate": "fps",
    "帧率": "fps",
    # 平滑 / 卡顿
    "smooth": "smooth",
    "smoothness": "smooth",
    "流畅度": "smooth",
    "stutter": "stutter_pct",
    "stutter(%)": "stutter_pct",
    "stutter[%]": "stutter_pct",
    "卡顿时长占比": "stutter_pct",
    "jank": "jank",
    "small jank": "jank_small",
    "big jank": "jank_big",
    "bigjank": "jank_big",
    "smalljank": "jank_small",
    # PerfDog 英文导出常见变体
    "stuttertimepercent": "stutter_pct",
    "stuttertime": "stutter_pct",
    "fpsavg": "fps",
    "avgfps": "fps",
    # 采样序号 / 场景
    "num": "sample_num",
    "label": "scene_label",
    "notes": "notes",
    "interframe": "inter_frame",
    # CPU / GPU（汇总列）
    "appcpu": "app_cpu_pct",
    "app cpu(%)": "app_cpu_pct",
    "appcpu(%)": "app_cpu_pct",
    "appcpu[%]": "app_cpu_pct",
    "appcpu[%] normalized": "app_cpu_pct_normalized",
    "totalcpu": "total_cpu_pct",
    "total cpu(%)": "total_cpu_pct",
    "totalcpu[%]": "total_cpu_pct",
    "totalcpu[%] normalized": "total_cpu_pct_normalized",
    "cpu usage": "total_cpu_pct",
    "gusage": "gpu_usage_pct",
    "gusage[%]": "gpu_usage_pct",
    "gpu usage": "gpu_usage_pct",
    "gpu usage(%)": "gpu_usage_pct",
    "gclock[mhz]": "gpu_clock_mhz",
    # 温度 / 功耗 / 环境
    "btemp": "battery_temp",
    "btemp[℃]": "battery_temp",
    "btemp[°c]": "battery_temp",
    "battery temp": "battery_temp",
    "电池温度": "battery_temp",
    "gtemp": "gpu_temp",
    "gpu temp": "gpu_temp",
    "thermalstatus": "thermal_status",
    "brightness": "brightness",
    "batterylevel[%]": "battery_level_pct",
    "功耗": "power_mw",
    "power": "power_mw",
    "current[ma]": "current_ma",
    "voltage[mv]": "voltage_mv",
    "fpower[mw]": "fpower_mw",
    "current1[ma]": "current_1_ma",
    "power1[mw]": "power_1_mw",
    "voltage1[mv]": "voltage_1_mv",
    "screenshot": "screenshot",
}

# 各核频点 / 占用（PerfDog 常见 0～7 核）
for _i in range(8):
    _ALIASES[f"cpuclock{_i}[mhz]"] = f"cpu_clock_{_i}_mhz"
    _ALIASES[f"cpuusage{_i}[%]"] = f"cpu_usage_{_i}_pct"
    _ALIASES[f"cpuusage{_i}[%] normalized"] = f"cpu_usage_{_i}_pct_normalized"


def _compact_key(key: str) -> str:
    """去掉空格、括号、百分号等，便于匹配 SmallJank、AppCPU(%) 等导出列名。"""
    return re.sub(r"[\s()%（），,]", "", key)


def _strip_trailing_bracket_unit(key: str) -> str:
    """去掉末尾 [xxx] 单位再查表（如 xxx[mhz] 已单独注册时跳过）。"""
    return re.sub(r"\[[^\]]+\]$", "", key).strip()


def map_column_name(raw: str) -> str | None:
    """将单列表头映射到内部名；未知返回 None。"""
    if raw is None:
        return None
    key = normalize_header_cell(str(raw))
    if not key:
        return None
    hit = _ALIASES.get(key)
    if hit is not None:
        return hit
    compact = _compact_key(key)
    if compact:
        hit = _ALIASES.get(compact)
        if hit is not None:
            return hit
    # 常见后缀：xxx (ms)、xxx(%)
    base = re.sub(r"\([^)]*\)$", "", key).strip()
    if base and base != key:
        hit = _ALIASES.get(base) or _ALIASES.get(_compact_key(base))
        if hit is not None:
            return hit
    stripped = _strip_trailing_bracket_unit(key)
    if stripped and stripped != key:
        hit = _ALIASES.get(stripped) or _ALIASES.get(_compact_key(stripped))
        if hit is not None:
            return hit
    return None


def rename_dataframe_columns(columns: list[str]) -> dict[str, str]:
    """返回 {原列名: 内部列名}，冲突时后者覆盖前者。"""
    out: dict[str, str] = {}
    used_internal: set[str] = set()
    for col in columns:
        internal = map_column_name(col)
        if internal is None:
            continue
        if internal in used_internal:
            continue
        out[col] = internal
        used_internal.add(internal)
    return out
