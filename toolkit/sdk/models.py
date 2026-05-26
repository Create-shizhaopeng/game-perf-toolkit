"""公共数据模型 — 模块间数据交换的结构化定义"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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


class DeviceState(BaseModel):
    """设备伪装状态 — 对比 ODM (current) 与 vendor (original) 属性判断是否伪装"""

    is_connected: bool = False
    current_brand: str = ""
    current_manufacturer: str = ""
    current_model: str = ""
    original_brand: str = ""
    original_manufacturer: str = ""
    original_model: str = ""

    @property
    def is_disguised(self) -> bool:
        if not self.is_connected:
            return False
        return (
            self.current_brand != self.original_brand
            or self.current_manufacturer != self.original_manufacturer
            or self.current_model != self.original_model
        )


class CLIResponse(BaseModel):
    """CLI 统一响应格式"""

    success: bool
    data: dict | list | None = None
    message: str = ""
    errors: list[str] = []
    metadata: dict = {}


class LLMConfig(BaseModel):
    """LLM 运行时配置（精简版）。

    Provider 定义和 API Key 已迁移到 llm_providers.json。
    此处仅保留运行时会话需要的字段。
    """

    provider: str = "glm"
    model_name: str = "glm-4-plus"
