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
    """LLM 全局配置"""

    provider: str = Field(default="glm", pattern=r"^(glm|claude)$")
    glm_api_key: str = ""
    claude_api_key: str = ""
    model_name: str = "glm-4-plus"
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=256)
    smart_switch: bool = False
    token_budget: int = Field(default=100000, ge=1000)
    budget_alert_threshold: float = Field(default=0.8, ge=0.1, le=1.0)

    def get_api_key(self, provider: str | None = None) -> str:
        p = provider or self.provider
        return self.glm_api_key if p == "glm" else self.claude_api_key

    def is_configured(self) -> bool:
        return bool(self.get_api_key())
