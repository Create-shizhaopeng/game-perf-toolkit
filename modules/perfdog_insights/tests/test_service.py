"""PerfdogInsightsService 单测（不启动 GUI）。"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from modules.perfdog_insights.src.service import PerfdogInsightsService


def _write_minimal_perfdog_xlsx(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "all"
    ws.append(["Data_v4"])
    ws.append(["Time(ms)", "FPS"])
    for i in range(10):
        ws.append([float(i * 1000), 59.0])
    wb.save(path)


def test_service_load_report(tmp_path: Path) -> None:
    p = tmp_path / "min.xlsx"
    _write_minimal_perfdog_xlsx(p)
    svc = PerfdogInsightsService()
    report = svc.load_report(str(p))
    assert report.summary_metrics.get("采样点数") == 10


def test_service_get_info() -> None:
    meta = PerfdogInsightsService().get_service_info()
    assert meta["name"] == "perfdog_insights"
