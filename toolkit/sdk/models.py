"""公共数据模型 — 模块间数据交换的结构化定义"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PluginInfo(BaseModel):
    """模块基本信息"""

    name: str
    display_name: str
    version: str
    description: str = ""


class DeviceInfo(BaseModel):
    """设备基本信息"""

    serial: str
    brand: str = ""
    manufacturer: str = ""
    model: str = ""
    status: str = "unknown"


class AnalysisResult(BaseModel):
    """分析结果基类 — 各分析模块继承此类定义具体结果"""

    module_name: str
    timestamp: datetime = datetime.now()
    device_id: str | None = None
    success: bool = True
    summary: str = ""
    details: dict = {}
    report_file: str | None = None


class CLIResponse(BaseModel):
    """CLI 统一响应格式"""

    success: bool
    data: dict | list | None = None
    message: str = ""
    errors: list[str] = []
    metadata: dict = {}
