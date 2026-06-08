"""
Gradio Tab 页面定义

定义 5 个 Tab 页面的 UI 布局：
- Tab 1「开始生成」：主题输入、模板上传、LLM 选择、数据上传
- Tab 2「大纲预览」：Markdown 大纲编辑与确认
- Tab 3「章节编辑」：双栏（Markdown 编辑器 + Word 预览）
- Tab 4「下载成果」：导出文件与摘要
- Tab 5「历史管理」：生成历史查看（P1 新增）
"""

from typing import Dict, Any, Tuple, List

import gradio as gr

from ui.components import (
    create_markdown_editor,
    create_markdown_preview,
    create_api_key_input,
    create_word_count_slider,
)
from utils.text_utils import estimate_word_count


def build_ui(config) -> gr.Blocks:
    """构建完整的 Gradio UI

    创建 4 个 Tab 页面并绑定所有事件回调。

    Args:
        config: GenerationConfig 实例

    Returns:
        gr.Blocks: 完整的 Gradio 应用
    """
    # 导入回调函数（延迟导入避免循环依赖）
    from ui.callbacks import (
        on_start_generation,
        on_confirm_outline,
        on_confirm_chapter,
        on_download,
        on_regenerate_outline,
        on_regenerate_chapter,
        on_skip_chapter,
        on_select_chapter,
        on_upload_data,       # P1 新增
        on_load_history,      # P1 新增
        on_template_select,   # P2 新增
        on_format_check,      # P2 新增
        on_full_review,       # P3 新增
        on_stats_analysis,    # P4 新增
        on_plagiarism_check,  # P4 新增
    )

    css = """
    .markdown-editor textarea {
        font-family: 'Consolas', 'Microsoft YaHei', monospace;
        font-size: 14px;
    }
    .api-key-input input {
        font-family: monospace;
    }
    .status-pending { color: #888; }
    .status-generating { color: #2196F3; }
    .status-done { color: #4CAF50; }
    .status-edited { color: #FF9800; }
    .chapter-preview { border-left: 1px solid #e0e0e0; padding-left: 16px; }
    footer { visibility: hidden; }
    """

    with gr.Blocks(
        title="论文自动生成系统",
        theme=gr.themes.Soft(),
        css=css,
    ) as app:
        # ── 全局状态 ──
        # thesis_state: 持有 Thesis 对象（核心状态）
        thesis_state = gr.State(None)
        # current_chapter_index: 当前编辑的章节索引
        current_chapter_idx = gr.State(0)

        # ── 应用标题 ──
        gr.Markdown(
            """
            # 📝 论文自动生成系统
            ### AI 辅助学术论文写作工具

            ⚠️ **伦理声明**：本工具基于 AI 大语言模型辅助生成论文内容，仅供学习和研究参考。
            严禁将生成内容直接作为学位论文提交。使用者应自行核实所有内容的准确性和原创性。
            """
        )

        with gr.Tabs():
            # ════════════════════════════════════════════════════
            # Tab 1: 开始生成
            # ════════════════════════════════════════════════════
            with gr.TabItem("🚀 开始生成", id="tab_input"):
                with gr.Row():
                    with gr.Column(scale=2):
                        topic_input = gr.Textbox(
                            label="论文主题",
                            placeholder="请输入论文主题，例如：基于深度学习的网络入侵检测系统设计与实现",
                            lines=3,
                        )
                        keywords_input = gr.Textbox(
                            label="关键词（逗号或空格分隔）",
                            placeholder="深度学习, 入侵检测, 网络安全, CNN",
                        )

                        with gr.Row():
                            word_count_slider = create_word_count_slider(
                                value=config.target_word_count,
                            )
                            discipline_dropdown = gr.Dropdown(
                                choices=[
                                    "软件工程", "计算机科学与技术", "人工智能",
                                    "数据科学", "网络安全", "电子信息工程",
                                    "通信工程", "自动化", "机械工程",
                                    "土木工程", "其他工科", "管理学", "经济学",
                                ],
                                value=config.discipline,
                                label="学科方向",
                            )

                        # P2 新增：模板选择
                        template_dropdown = gr.Dropdown(
                            choices=[
                                ("齐鲁理工学院标准", "qlu"),
                                ("通用英文学术", "academic"),
                                ("工科规范", "engineering"),
                                ("自定义模板（上传）", "custom"),
                            ],
                            value="qlu",
                            label="论文模板",
                        )

                        template_upload = gr.File(
                            label="上传模板（.docx 格式，可选，选「自定义模板」时生效）",
                            file_types=[".docx"],
                            type="filepath",
                        )

                        # P1 新增：数据文件上传
                        data_upload = gr.File(
                            label="上传数据文件（.xlsx / .csv，可选）",
                            file_types=[".xlsx", ".csv"],
                            type="filepath",
                        )

                    with gr.Column(scale=1):
                        gr.Markdown("### ⚙️ LLM 设置")

                        llm_choice = gr.Radio(
                            choices=["deepseek", "openai"],
                            value=config.llm_provider,
                            label="LLM 提供商",
                        )

                        deepseek_key = create_api_key_input(
                            label="DeepSeek API Key",
                            placeholder="sk-...",
                        )
                        openai_key = create_api_key_input(
                            label="OpenAI API Key",
                            placeholder="sk-...",
                        )

                        # P1 新增：异步模式 toggle
                        async_toggle = gr.Checkbox(
                            label="异步生成模式（后台 worker，可关闭页面等待）",
                            value=config.async_mode,
                        )

                        start_btn = gr.Button(
                            "🎓 开始生成论文",
                            variant="primary",
                            size="lg",
                        )

                        progress_bar = gr.Progress()

                        status_text = gr.Markdown("")

                # ── 绑定回调 ──
                start_btn.click(
                    fn=on_start_generation,
                    inputs=[
                        topic_input,
                        keywords_input,
                        word_count_slider,
                        template_upload,
                        discipline_dropdown,
                        llm_choice,
                        deepseek_key,
                        openai_key,
                    ],
                    outputs=[thesis_state, status_text],
                ).then(
                    fn=lambda: gr.Tabs(selected="tab_outline"),
                    inputs=None,
                    outputs=None,
                    js="() => document.querySelector('[id*=\"tab_outline\"]')?.closest('button')?.click()",
                )

            # ════════════════════════════════════════════════════
            # Tab 2: 大纲预览
            # ════════════════════════════════════════════════════
            with gr.TabItem("📋 大纲预览", id="tab_outline"):
                gr.Markdown("### 论文大纲预览与编辑")
                gr.Markdown(
                    "AI 已生成以下大纲。您可以直接编辑，或输入反馈意见让 AI 重新生成。"
                )

                outline_editor = create_markdown_editor(
                    label="大纲内容（Markdown 格式，可编辑）",
                    height=500,
                )

                with gr.Row():
                    feedback_input = gr.Textbox(
                        label="修改意见（可选）",
                        placeholder="例如：增加一节关于数据预处理的讨论...",
                        lines=2,
                    )

                with gr.Row():
                    regenerate_outline_btn = gr.Button(
                        "🔄 AI 重新生成",
                        variant="secondary",
                    )
                    confirm_outline_btn = gr.Button(
                        "✅ 确认大纲，开始写正文",
                        variant="primary",
                    )

                outline_status = gr.Markdown("")

                # ── 绑定回调 ──
                regenerate_outline_btn.click(
                    fn=on_regenerate_outline,
                    inputs=[thesis_state, outline_editor, feedback_input],
                    outputs=[thesis_state, outline_editor, outline_status],
                )

                confirm_outline_btn.click(
                    fn=on_confirm_outline,
                    inputs=[thesis_state, outline_editor],
                    outputs=[thesis_state, outline_status, current_chapter_idx],
                ).then(
                    fn=lambda: gr.Tabs(selected="tab_chapter"),
                    inputs=None,
                    outputs=None,
                    js="() => document.querySelector('[id*=\"tab_chapter\"]')?.closest('button')?.click()",
                )

            # ════════════════════════════════════════════════════
            # Tab 3: 章节编辑（P1 升级：双栏 Markdown 编辑 + Word 预览）
            # ════════════════════════════════════════════════════
            with gr.TabItem("✍️ 章节编辑", id="tab_chapter"):
                gr.Markdown("### 章节内容编辑（左侧编辑，右侧预览）")

                # 章节导航按钮组
                with gr.Row():
                    prev_chapter_btn = gr.Button("◀ 上一章", size="sm")
                    chapter_indicator = gr.Markdown("**第 1 章**")
                    next_chapter_btn = gr.Button("下一章 ▶", size="sm")

                # 章节选择下拉
                chapter_dropdown = gr.Dropdown(
                    label="快速跳转到",
                    choices=[],
                    interactive=True,
                )

                # 双栏布局：编辑 + 预览
                with gr.Row(equal_height=False):
                    with gr.Column(scale=1):
                        chapter_editor = create_markdown_editor(
                            label="章节正文（Markdown 格式，可编辑）",
                            height=500,
                        )
                    with gr.Column(scale=1, elem_classes=["chapter-preview"]):
                        chapter_preview = gr.Markdown(
                            value="*选择章节后将在此显示渲染预览*",
                            label="Word 预览",
                            latex_delimiters=[
                                {"left": "$$", "right": "$$", "display": True},
                                {"left": "$", "right": "$", "display": False},
                            ],
                        )
                        chapter_word_count = gr.Textbox(
                            label="字数统计",
                            value="0 字",
                            interactive=False,
                        )

                # 章节状态
                chapter_status = gr.Markdown("")

                # 操作按钮组
                with gr.Row():
                    regenerate_chapter_btn = gr.Button(
                        "🔄 重新生成本章",
                        variant="secondary",
                    )
                    confirm_chapter_btn = gr.Button(
                        "✅ 确认本章",
                        variant="primary",
                    )
                    skip_chapter_btn = gr.Button(
                        "⏭ 跳过",
                        variant="secondary",
                    )

                # 生成下一章
                with gr.Row():
                    generate_next_btn = gr.Button(
                        "▶ 生成下一章",
                        variant="primary",
                    )

                chapter_feedback = gr.Markdown("")

                # ── 绑定回调 ──
                def _render_chapter_preview(state, idx):
                    """更新视图时同步渲染预览和字数"""
                    new_idx, content, indicator, status = on_select_chapter(state, idx)
                    from utils.text_utils import estimate_word_count
                    wc = estimate_word_count(content) if content else 0
                    return new_idx, content, indicator, status, content, f"{wc:,} 字"

                prev_chapter_btn.click(
                    fn=lambda s, i: _render_chapter_preview(s, i - 1),
                    inputs=[thesis_state, current_chapter_idx],
                    outputs=[
                        current_chapter_idx,
                        chapter_editor,
                        chapter_indicator,
                        chapter_status,
                        chapter_preview,
                        chapter_word_count,
                    ],
                )

                next_chapter_btn.click(
                    fn=lambda s, i: _render_chapter_preview(s, i + 1),
                    inputs=[thesis_state, current_chapter_idx],
                    outputs=[
                        current_chapter_idx,
                        chapter_editor,
                        chapter_indicator,
                        chapter_status,
                        chapter_preview,
                        chapter_word_count,
                    ],
                )

                chapter_dropdown.change(
                    fn=lambda s, d: _render_chapter_preview(s, d),
                    inputs=[thesis_state, chapter_dropdown],
                    outputs=[
                        current_chapter_idx,
                        chapter_editor,
                        chapter_indicator,
                        chapter_status,
                        chapter_preview,
                        chapter_word_count,
                    ],
                )

                # 编辑器内容变化时实时更新预览和字数
                chapter_editor.change(
                    fn=lambda content: (content, f"{estimate_word_count(content) if content else 0:,} 字"),
                    inputs=[chapter_editor],
                    outputs=[chapter_preview, chapter_word_count],
                )

                confirm_chapter_btn.click(
                    fn=on_confirm_chapter,
                    inputs=[thesis_state, current_chapter_idx, chapter_editor],
                    outputs=[thesis_state, chapter_feedback, chapter_editor],
                )

                regenerate_chapter_btn.click(
                    fn=on_regenerate_chapter,
                    inputs=[thesis_state, current_chapter_idx],
                    outputs=[thesis_state, chapter_editor, chapter_feedback],
                )

                skip_chapter_btn.click(
                    fn=on_skip_chapter,
                    inputs=[thesis_state, current_chapter_idx],
                    outputs=[thesis_state, chapter_feedback],
                )

                generate_next_btn.click(
                    fn=lambda s, i: _render_chapter_preview(s, i + 1),
                    inputs=[thesis_state, current_chapter_idx],
                    outputs=[
                        current_chapter_idx,
                        chapter_editor,
                        chapter_indicator,
                        chapter_status,
                        chapter_preview,
                        chapter_word_count,
                    ],
                )

            # ════════════════════════════════════════════════════
            # Tab 4: 下载成果
            # ════════════════════════════════════════════════════
            with gr.TabItem("📥 下载成果", id="tab_download"):
                gr.Markdown("### 📥 下载论文成果")

                summary_md = gr.Markdown("（完成所有章节后将显示摘要）")

                with gr.Row():
                    download_thesis_btn = gr.Button(
                        "📄 下载完整论文 (.docx)",
                        variant="primary",
                    )
                    download_outline_btn = gr.Button(
                        "📋 下载大纲 (.md)",
                        variant="secondary",
                    )

                with gr.Row():
                    download_bib_btn = gr.Button(
                        "📚 下载参考文献 (.bib)",
                        variant="secondary",
                    )

                download_path_output = gr.Textbox(
                    label="文件保存位置",
                    interactive=False,
                )

                # P2 新增：格式对比
                gr.Markdown("---")
                gr.Markdown("### 🔍 格式一致性检查")
                format_check_btn = gr.Button(
                    "🔍 检查格式一致性",
                    variant="secondary",
                )
                format_check_result = gr.Markdown("")

                gr.Markdown(
                    """
                    ---
                    ### ⚠️ 免责声明

                    本文档由 AI 辅助生成系统自动生成，仅供学习和研究参考。

                    - 生成内容可能存在事实性错误或逻辑不严谨
                    - 严禁将生成内容直接作为学位论文提交
                    - 使用者应自行核实所有内容的准确性
                    - 引用规范请参照 GB/T 7714-2015

                    使用本系统即表示您已阅读并同意上述条款。
                    """
                )

                # ── 绑定回调 ──
                download_thesis_btn.click(
                    fn=lambda s: on_download(s, "docx"),
                    inputs=[thesis_state],
                    outputs=[download_path_output],
                )

                download_outline_btn.click(
                    fn=lambda s: on_download(s, "md"),
                    inputs=[thesis_state],
                    outputs=[download_path_output],
                )

                download_bib_btn.click(
                    fn=lambda s: on_download(s, "bib"),
                    inputs=[thesis_state],
                    outputs=[download_path_output],
                )

                # P2: 格式对比
                format_check_btn.click(
                    fn=on_format_check,
                    inputs=[thesis_state],
                    outputs=[format_check_result],
                )

            # ════════════════════════════════════════════════════
            # Tab 5: 历史管理（P1 新增）
            # ════════════════════════════════════════════════════
            with gr.TabItem("📊 历史管理", id="tab_history"):
                gr.Markdown("### 📊 生成历史")

                history_list = gr.DataFrame(
                    headers=["ID", "主题", "章节数", "字数", "参考文献", "输出路径", "创建时间"],
                    datatype=["str", "str", "number", "number", "number", "str", "str"],
                    interactive=False,
                    label="历史记录",
                )

                with gr.Row():
                    refresh_history_btn = gr.Button(
                        "🔄 刷新",
                        variant="secondary",
                    )
                    clear_history_btn = gr.Button(
                        "🗑 清空历史",
                        variant="stop",
                        size="sm",
                    )

                history_status = gr.Markdown("")

                # ── 绑定回调 ──
                refresh_history_btn.click(
                    fn=on_load_history,
                    inputs=None,
                    outputs=[history_list, history_status],
                )

                clear_history_btn.click(
                    fn=lambda: ([], "🗑 所有历史记录已清空"),
                    inputs=None,
                    outputs=[history_list, history_status],
                )

                # -- 数据上传回调 --
                data_upload.change(
                    fn=on_upload_data,
                    inputs=[data_upload, thesis_state],
                    outputs=[thesis_state, status_text],
                )

                # P2 新增：模板选择
                template_status = gr.Markdown("")
                template_dropdown.change(
                    fn=on_template_select,
                    inputs=[template_dropdown],
                    outputs=[template_status],
                )

            # ════════════════════════════════════════════════════
            # P3 Tab 6: 模拟盲审
            # ════════════════════════════════════════════════════
            with gr.TabItem("🎓 模拟盲审", id="tab_review"):
                gr.Markdown("### 🎓 多智能体模拟盲审")
                gr.Markdown(
                    "由三个独立 AI Agent（创新性/方法/规范性）并行评审，"
                    "生成结构化盲审报告。"
                )

                with gr.Row():
                    full_review_btn = gr.Button(
                        "📝 完整论文盲审",
                        variant="primary",
                    )
                    chapter_review_btn = gr.Button(
                        "📄 单章评审",
                        variant="secondary",
                    )

                # P4 新增：统计 + 查重
                with gr.Row():
                    stats_btn = gr.Button(
                        "📊 数据统计洞察",
                        variant="secondary",
                    )
                    plagiarism_btn = gr.Button(
                        "🔍 查重预检",
                        variant="secondary",
                    )

                review_output = gr.Markdown(
                    value="*点击按钮开始分析...*",
                    label="评审/分析报告",
                )

                # ── 绑定回调 ──
                full_review_btn.click(
                    fn=on_full_review,
                    inputs=[thesis_state],
                    outputs=[review_output],
                )

                chapter_review_btn.click(
                    fn=lambda s: on_full_review(s),
                    inputs=[thesis_state],
                    outputs=[review_output],
                )

                stats_btn.click(
                    fn=on_stats_analysis,
                    inputs=[thesis_state],
                    outputs=[review_output],
                )

                plagiarism_btn.click(
                    fn=on_plagiarism_check,
                    inputs=[thesis_state],
                    outputs=[review_output],
                )

            # ── 底部 ──
            gr.Markdown(
                """
                ---
                <div style="text-align: center; color: #999; font-size: 12px;">
                论文自动生成系统 v2.0 (P4) | 基于 DeepSeek/OpenAI 大语言模型 | 仅供学习研究参考
                </div>
                """
            )

    return app
