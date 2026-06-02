# Re-export AgentTab for backward compatibility
# The new AgentPanel replaces AgentTab; keep stub for tests
from PyQt6.QtWidgets import QWidget

class AgentTab(QWidget):
    """Stub — Agent now uses AgentPanel as right-side panel."""
    tab_title = "Agent 智能助手"
    tab_icon = "robot"

    def __init__(self, context=None, parent=None):
        super().__init__(parent)
        self.context = context

    def set_theme(self, theme): pass
    def on_activated(self): pass
