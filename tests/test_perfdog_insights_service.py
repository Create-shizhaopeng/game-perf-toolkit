"""PerfdogInsightsService 烟测（与 modules/perfdog_insights 集成，不启动 GUI）。"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from modules.perfdog_insights.src.service import PerfdogInsightsService


def _minimal_xlsx(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "all"
    ws.append(["Data_v4"])
    ws.append(["Time(ms)", "FPS"])
    for i in range(10):
        ws.append([float(i * 1000), 59.0])
    wb.save(path)


def test_service_report_to_plain_dict(tmp_path: Path) -> None:
    p = tmp_path / "b.xlsx"
    _minimal_xlsx(p)
    svc = PerfdogInsightsService()
    report = svc.load_report(str(p))
    d = svc.report_to_plain_dict(report, include_chunk_rows=False)
    assert d.get("schema_version") == 1
    assert "anomaly_data_chunks" in d


def test_service_load_and_compose_markdown(tmp_path: Path) -> None:
    p = tmp_path / "a.xlsx"
    _minimal_xlsx(p)
    svc = PerfdogInsightsService()
    report = svc.load_report(str(p))
    md = svc.compose_export_markdown(report)
    assert "# PerfDog" in md
    assert "## 异常关联采样（Data_v4）" in md
    assert "## 其余时段说明" in md
