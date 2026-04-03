"""workspace_tools（性能配置对比）基础测试"""

from modules.workspace_tools.src.service import WorkspaceToolsService


def test_service_info():
    svc = WorkspaceToolsService()
    info = svc.get_service_info()
    assert info["name"] == "workspace_tools"
