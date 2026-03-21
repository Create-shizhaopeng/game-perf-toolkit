"""Perfetto卡顿抓取 基础测试"""

from modules.perfetto_capture.src.service import PerfettoCaptureService


def test_service_info():
    svc = PerfettoCaptureService()
    info = svc.get_service_info()
    assert info["name"] == "perfetto_capture"
