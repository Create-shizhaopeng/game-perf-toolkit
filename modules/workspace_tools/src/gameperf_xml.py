"""gameperfconfig 文件名规则与 XML 解析封装"""

from __future__ import annotations

from lxml import etree

from .gameperf_diff_errors import InvalidGamePerfFileError, XmlParseError


def is_valid_gameperf_config_filename(name: str) -> bool:
    """文件名须包含子串 gameperfconfig 且扩展名为 .xml（与 game_perf 一致）。"""
    return "gameperfconfig" in name and name.lower().endswith(".xml")


def parse_gameperf_xml(path: str) -> etree._Element:
    """读取 XML：UTF-8 + errors=replace，良构校验；根节点须为 GameOptPolicy。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except OSError as e:
        raise XmlParseError(f"无法读取文件：{e}") from e
    try:
        root = etree.fromstring(raw.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        raise XmlParseError(f"XML 非良构：{e}") from e
    if root.tag != "GameOptPolicy":
        raise InvalidGamePerfFileError("根节点须为 GameOptPolicy")
    return root
