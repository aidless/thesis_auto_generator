"""
可复用 UI 组件

提供 Gradio 界面中使用的自定义组件，包括：
- 进度条（模拟章节生成进度）
- 章节选择器（水平按钮组，显示状态）
- Markdown 编辑器封装
"""

from typing import List, Optional, Callable

import gradio as gr


def create_progress_bar() -> gr.Progress:
    """创建进度条组件（Gradio 内置）

    使用 gr.Progress() 实现，在回调中通过 gr.Progress().tqdm 风格的
    迭代器或手动 (index, total) 参数更新。

    Returns:
        gr.Progress: Gradio 进度条
    """
    return gr.Progress()


def create_chapter_selector(
    chapters: List[dict],
    label: str = "章节选择",
) -> gr.Radio:
    """创建章节选择器（Radio 按钮组）

    Args:
        chapters: 章节信息列表，每项包含 id, title, status
        label: 组件标签

    Returns:
        gr.Radio: Gradio Radio 组件
    """
    choices = []
    for i, ch in enumerate(chapters):
        status_emoji = {
            "pending": "⏳",
            "generating": "🔄",
            "done": "✅",
            "edited": "✏️",
        }.get(ch.get("status", "pending"), "❓")

        title = ch.get("title", f"第{i+1}章")
        label_text = f"{status_emoji} {title}"
        choices.append((label_text, i))

    return gr.Radio(
        choices=choices,
        value=0 if choices else None,
        label=label,
        interactive=True,
    )


def create_chapter_buttons(
    chapters: List[dict],
    on_select: Optional[Callable] = None,
) -> List[gr.Button]:
    """创建章节按钮组（水平排列）

    Args:
        chapters: 章节信息列表
        on_select: 选中回调（暂不使用，由 callbacks 绑定）

    Returns:
        List[gr.Button]: 按钮列表
    """
    buttons = []
    status_colors = {
        "pending": "secondary",
        "generating": "primary",
        "done": "success",
        "edited": "warning",
    }

    for i, ch in enumerate(chapters):
        status = ch.get("status", "pending")
        title = ch.get("title", f"第{i+1}章")
        # 截断标题
        if len(title) > 10:
            display_title = title[:9] + "…"
        else:
            display_title = title

        status_emoji = {
            "pending": "⏳",
            "generating": "🔄",
            "done": "✅",
            "edited": "✏️",
        }.get(status, "❓")

        btn = gr.Button(
            value=f"{status_emoji} {display_title}",
            variant=status_colors.get(status, "secondary"),
            size="sm",
            elem_id=f"ch_btn_{i}",
        )
        buttons.append(btn)

    return buttons


def create_markdown_editor(
    value: str = "",
    label: str = "Markdown 编辑器",
    height: int = 600,
) -> gr.Textbox:
    """创建 Markdown 编辑器（大文本框）

    Args:
        value: 初始文本
        label: 标签
        height: 编辑器高度（行数）

    Returns:
        gr.Textbox: Gradio 文本框
    """
    return gr.Textbox(
        value=value,
        label=label,
        lines=height // 20,  # 大约每行 20px
        max_lines=height // 20 * 3,
        interactive=True,
        elem_classes=["markdown-editor"],
    )


def create_markdown_preview(
    value: str = "",
    label: str = "预览",
) -> gr.Markdown:
    """创建 Markdown 预览组件

    Args:
        value: 初始 Markdown 内容
        label: 标签

    Returns:
        gr.Markdown: Gradio Markdown 组件
    """
    return gr.Markdown(
        value=value,
        label=label,
        elem_classes=["markdown-preview"],
        latex_delimiters=[
            {"left": "$$", "right": "$$", "display": True},
            {"left": "$", "right": "$", "display": False},
        ],
    )


def create_api_key_input(
    label: str = "API Key",
    placeholder: str = "sk-...",
) -> gr.Textbox:
    """创建 API Key 输入框

    Args:
        label: 标签
        placeholder: 占位文本

    Returns:
        gr.Textbox: 密码输入框
    """
    return gr.Textbox(
        label=label,
        placeholder=placeholder,
        type="password",
        elem_classes=["api-key-input"],
    )


def create_word_count_slider(
    label: str = "目标总字数",
    minimum: int = 5000,
    maximum: int = 50000,
    value: int = 15000,
    step: int = 1000,
) -> gr.Slider:
    """创建字数滑块

    Args:
        label: 标签
        minimum: 最小值
        maximum: 最大值
        value: 默认值
        step: 步长

    Returns:
        gr.Slider: Gradio 滑块
    """
    return gr.Slider(
        minimum=minimum,
        maximum=maximum,
        value=value,
        step=step,
        label=label,
    )
