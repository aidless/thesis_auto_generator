"""ui - Gradio 界面模块

包含 Tab 定义、事件回调和可复用 UI 组件。
"""

from ui.tabs import build_ui
from ui.callbacks import (
    on_start_generation,
    on_confirm_outline,
    on_confirm_chapter,
    on_download,
    on_regenerate_outline,
    on_regenerate_chapter,
    on_skip_chapter,
)

__all__ = [
    "build_ui",
    "on_start_generation",
    "on_confirm_outline",
    "on_confirm_chapter",
    "on_download",
    "on_regenerate_outline",
    "on_regenerate_chapter",
    "on_skip_chapter",
]
