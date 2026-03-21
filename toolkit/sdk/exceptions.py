"""统一异常体系"""


class ToolkitError(Exception):
    """工具集基础异常"""


class ModuleError(ToolkitError):
    """模块相关异常"""


class AdbError(ToolkitError):
    """ADB 操作异常"""


class ConfigError(ToolkitError):
    """配置相关异常"""


class DatabaseError(ToolkitError):
    """数据库操作异常"""


class WorkflowError(ToolkitError):
    """工作流执行异常"""


class DeviceNotFoundError(AdbError):
    """设备未找到"""


class DeviceOfflineError(AdbError):
    """设备离线"""
