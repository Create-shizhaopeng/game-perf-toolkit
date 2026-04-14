"""集中定义 Catppuccin 调色板 — 所有模块共享的主题颜色常量。

暗色基于 Catppuccin Mocha，亮色基于 Catppuccin Latte。
模块应从此处导入颜色，而不是自行定义 _THEME_COLORS 字典。
"""

from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        # 背景层级
        "bg": "#1e1e2e",
        "bg_surface": "#181825",
        "card_bg": "#313244",
        "panel_bg": "#313244",
        # 边框
        "border": "#45475a",
        "border_subtle": "#313244",
        # 前景层级
        "fg": "#cdd6f4",
        "fg_dim": "#a6adc8",
        "fg_muted": "#6c7086",
        # 强调色
        "accent": "#cba6f7",
        "accent_hover": "#b490e0",
        "blue": "#89b4fa",
        # 语义色
        "success": "#a6e3a1",
        "error": "#f38ba8",
        "warning": "#fab387",
        "info": "#89b4fa",
        # 按钮 — 主要
        "btn_primary_bg": "#cba6f7",
        "btn_primary_fg": "#1e1e2e",
        # 按钮 — 次要
        "btn_secondary_bg": "#45475a",
        "btn_secondary_fg": "#cdd6f4",
        # 按钮 — 危险
        "btn_danger_bg": "#f38ba8",
        "btn_danger_fg": "#1e1e2e",
        # 输入框
        "input_bg": "#313244",
        "input_border": "#45475a",
        # 悬停
        "hover": "#45475a",
        # 消息气泡 (agent_chat)
        "user_bubble": "#313244",
        "tool_card_bg": "#181825",
        "msg_user": "#585b70",
        "msg_ai": "#313244",
        # 流程/学习边框
        "workflow_border": "#cba6f7",
        "learn_border": "#f9e2af",
        # 发送/停止按钮
        "btn_send_bg": "#cba6f7",
        "btn_stop_bg": "#f38ba8",
        # perfetto_capture 专用
        "btn_save_bg": "#f9e2af",
        "btn_save_fg": "#1e1e2e",
        "btn_stop_fg": "#1e1e2e",
        # home_tab 专用
        "subtitle": "#a6adc8",
        "muted": "#6c7086",
        "card_title": "#a6adc8",
        "version_fg": "#585b70",
    },
    "light": {
        # 背景层级
        "bg": "#eff1f5",
        "bg_surface": "#e6e9ef",
        "card_bg": "#e6e9ef",
        "panel_bg": "#e6e9ef",
        # 边框
        "border": "#ccd0da",
        "border_subtle": "#ccd0da",
        # 前景层级
        "fg": "#4c4f69",
        "fg_dim": "#6c6f85",
        "fg_muted": "#9ca0b0",
        # 强调色
        "accent": "#8839ef",
        "accent_hover": "#7030d0",
        "blue": "#1e66f5",
        # 语义色
        "success": "#40a02b",
        "error": "#d20f39",
        "warning": "#fe640b",
        "info": "#1e66f5",
        # 按钮 — 主要
        "btn_primary_bg": "#8839ef",
        "btn_primary_fg": "#ffffff",
        # 按钮 — 次要
        "btn_secondary_bg": "#ccd0da",
        "btn_secondary_fg": "#4c4f69",
        # 按钮 — 危险
        "btn_danger_bg": "#d20f39",
        "btn_danger_fg": "#ffffff",
        # 输入框
        "input_bg": "#dce0e8",
        "input_border": "#bcc0cc",
        # 悬停
        "hover": "#dce0e8",
        # 消息气泡 (agent_chat)
        "user_bubble": "#dce0e8",
        "tool_card_bg": "#e6e9ef",
        "msg_user": "#dce0e8",
        "msg_ai": "#e6e9ef",
        # 流程/学习边框
        "workflow_border": "#8839ef",
        "learn_border": "#df8e1d",
        # 发送/停止按钮
        "btn_send_bg": "#8839ef",
        "btn_stop_bg": "#d20f39",
        # perfetto_capture 专用
        "btn_save_bg": "#df8e1d",
        "btn_save_fg": "#ffffff",
        "btn_stop_fg": "#ffffff",
        # home_tab 专用
        "subtitle": "#616161",
        "muted": "#888888",
        "card_title": "#616161",
        "version_fg": "#888888",
    },
}


def get_colors(theme: str = "dark") -> dict[str, str]:
    """返回指定主题的颜色字典。"""
    return THEMES.get(theme, THEMES["dark"])
