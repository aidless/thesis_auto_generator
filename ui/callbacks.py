"""
Gradio 事件回调 + 工作流编排

所有 Gradio 事件处理函数集中在此模块，作为 UI 和核心业务逻辑之间的桥梁。

工作流：
Tab1(输入) → 解析模板 → LLM生成大纲 → Tab2(确认) → 逐章生成 → Tab3(编辑) → 文献检索 → 格式化 → Tab4(下载)

全局状态通过 gr.State() 持有的 Thesis 对象贯穿整个流程。
"""

import os
import sys
import logging
import threading
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import GenerationConfig, load_config
from core.models import (
    Thesis,
    Outline,
    OutlineNode,
    Chapter,
    Reference,
    TemplateStyles,
)
from llm.base import create_llm_client
from core.outline_generator import OutlineGenerator
from core.chapter_generator import ChapterGenerator
from core.reference_fetcher import ReferenceFetcher
from core.template_parser import TemplateParser
from core.docx_formatter import DocxFormatter
from utils.file_utils import (
    save_uploaded_file,
    generate_output_filename,
    get_output_dir,
    ensure_dir,
)
from utils.text_utils import estimate_word_count
from utils.watermark import add_watermark_and_disclaimer

# P1 新增
from core.data_importer import DataImporter
from core.models import HistoryRecord

# P2 新增
from core.history_store import get_history_store
from utils.format_checker import FormatChecker
from core.template_parser import TemplateParser

# P3 新增
from core.review_engine import ReviewEngine

# P4 新增
from core.stats_engine import StatsEngine
from utils.plagiarism_checker import PlagiarismChecker

logger = logging.getLogger(__name__)

# 全局锁，防止多个请求并发操作同一个 thesis
_thesis_lock = threading.Lock()


# ══════════════════════════════════════════════════════════════
# Tab 1: 开始生成
# ══════════════════════════════════════════════════════════════

def on_start_generation(
    topic: str,
    keywords_str: str,
    target_word_count: int,
    template_file,
    discipline: str,
    llm_choice: str,
    deepseek_key: str,
    openai_key: str,
) -> Tuple[Optional[Thesis], str]:
    """处理「开始生成」按钮点击

    完整流程：
    1. 校验输入
    2. 创建配置和 LLM 客户端
    3. 解析上传的模板（如有）
    4. 调用 LLM 生成大纲
    5. 创建 Thesis 对象，返回给 gr.State

    Args:
        topic: 论文主题
        keywords_str: 关键词字符串（逗号/空格分隔）
        target_word_count: 目标总字数
        template_file: 上传的模板文件（None 或文件路径）
        discipline: 学科方向
        llm_choice: "deepseek" 或 "openai"
        deepseek_key: DeepSeek API Key
        openai_key: OpenAI API Key

    Returns:
        Tuple[Optional[Thesis], str]: (论文状态对象, 状态消息)
    """
    # 1. 输入校验
    if not topic or not topic.strip():
        return None, "❌ 请输入论文主题"

    topic = topic.strip()

    # 解析关键词
    keywords = _parse_keywords(keywords_str)
    if not keywords:
        keywords = [topic[:20]]  # 使用主题前 20 字作为兜底关键词

    # 2. 创建配置
    config = GenerationConfig(
        llm_provider=llm_choice,
        llm_model="deepseek-chat" if llm_choice == "deepseek" else "gpt-4o",
        llm_api_key=deepseek_key if llm_choice == "deepseek" else openai_key,
        llm_api_base=(
            "https://api.deepseek.com" if llm_choice == "deepseek"
            else "https://api.openai.com/v1"
        ),
        target_word_count=target_word_count,
        discipline=discipline,
    )

    # 3. 创建 LLM 客户端
    try:
        llm_client = create_llm_client(llm_choice, config)
    except Exception as e:
        return None, f"❌ 初始化 LLM 客户端失败: {e}"

    # 4. 解析模板
    template_path = ""
    template_styles = TemplateStyles()
    if template_file:
        try:
            template_path = save_uploaded_file(template_file)
            parser = TemplateParser()
            template_styles = parser.parse(template_path)
        except Exception as e:
            logger.warning(f"模板解析失败，使用默认样式: {e}")
            template_styles = TemplateStyles()

    # 5. 生成大纲
    try:
        outline_gen = OutlineGenerator(llm_client)
        outline = outline_gen.generate(
            topic=topic,
            keywords=keywords,
            discipline=discipline,
            target_word_count=target_word_count,
        )
    except Exception as e:
        return None, f"❌ 大纲生成失败: {e}"

    # 6. 创建 Thesis 对象
    thesis = Thesis(
        topic=topic,
        keywords=keywords,
        target_word_count=target_word_count,
        outline=outline,
        template_styles=template_styles,
        template_path=template_path,
    )

    # 初始化章节列表（从大纲创建 pending 状态的章节）
    chapter_nodes = outline.get_chapters()
    thesis.chapters = [
        Chapter(node=node, status="pending")
        for node in chapter_nodes
    ]

    chapter_count = len(thesis.chapters)
    status_msg = (
        f"✅ 大纲生成成功！\n\n"
        f"- 主题：{topic}\n"
        f"- 章节数：{chapter_count} 章\n"
        f"- 关键词：{'、'.join(keywords)}\n"
        f"- 学科：{discipline}\n"
        f"- 目标字数：{target_word_count:,} 字\n"
        f"- 模板：{os.path.basename(template_path) if template_path else '默认样式'}\n\n"
        f"请切换到「📋 大纲预览」Tab 查看和确认大纲。"
    )

    return thesis, status_msg


# ══════════════════════════════════════════════════════════════
# Tab 2: 大纲预览
# ══════════════════════════════════════════════════════════════

def on_regenerate_outline(
    thesis: Optional[Thesis],
    edited_outline_text: str,
    feedback: str,
) -> Tuple[Optional[Thesis], str, str]:
    """处理「AI 重新生成大纲」按钮

    基于用户反馈意见重新生成大纲。

    Args:
        thesis: 当前论文状态
        edited_outline_text: 当前编辑器中的大纲文本
        feedback: 用户反馈意见

    Returns:
        Tuple[Thesis, str, str]: (更新后的Thesis, 新大纲Markdown, 状态消息)
    """
    if thesis is None:
        return None, "", "❌ 请先在 Tab 1 生成初始大纲"

    if not feedback or not feedback.strip():
        return thesis, edited_outline_text, "⚠️ 请输入修改意见后再重新生成"

    # 重新创建 LLM 客户端
    config = load_config()
    try:
        llm_client = create_llm_client(config.llm_provider, config)
    except Exception as e:
        return thesis, edited_outline_text, f"❌ LLM 客户端初始化失败: {e}"

    # 重新生成
    try:
        outline_gen = OutlineGenerator(llm_client)
        new_outline = outline_gen.regenerate_with_feedback(
            outline=thesis.outline,
            feedback=feedback,
        )
    except Exception as e:
        return thesis, edited_outline_text, f"❌ 大纲重新生成失败: {e}"

    # 更新 Thesis
    thesis.outline = new_outline
    new_md = new_outline.to_markdown()

    return thesis, new_md, "✅ 大纲已根据反馈重新生成，请确认。"


def on_confirm_outline(
    thesis: Optional[Thesis],
    edited_outline_text: str,
) -> Tuple[Optional[Thesis], str, int]:
    """处理「确认大纲，开始写正文」按钮

    1. 解析用户编辑后的大纲文本，更新 Outline 树
    2. 根据新大纲重建章节列表
    3. 开始逐章生成正文（后台线程）

    Args:
        thesis: 当前论文状态
        edited_outline_text: 编辑器中的大纲文本（可能已被用户修改）

    Returns:
        Tuple[Thesis, str, int]: (更新后的Thesis, 状态消息, 当前章节索引)
    """
    if thesis is None:
        return None, "❌ 请先在 Tab 1 生成大纲", 0

    # 如果用户编辑了大纲文本，尝试解析更新
    if edited_outline_text and thesis.outline:
        try:
            thesis.outline.from_markdown(edited_outline_text)
        except Exception as e:
            logger.warning(f"解析编辑后的大纲失败: {e}")

    # 重建章节列表
    chapter_nodes = thesis.outline.get_chapters()
    thesis.chapters = [
        Chapter(node=node, status="pending")
        for node in chapter_nodes
    ]

    chapter_count = len(thesis.chapters)
    status_msg = (
        f"✅ 大纲已确认！共 {chapter_count} 章。\n\n"
        f"请切换到「✍️ 章节编辑」Tab 开始逐章生成论文正文。"
    )

    return thesis, status_msg, 0


# ══════════════════════════════════════════════════════════════
# Tab 3: 章节编辑
# ══════════════════════════════════════════════════════════════

def on_select_chapter(
    thesis: Optional[Thesis],
    chapter_index: int,
) -> Tuple[int, str, str, str]:
    """处理章节选择（切换当前编辑的章节）

    Args:
        thesis: 当前论文状态
        chapter_index: 选中的章节索引

    Returns:
        Tuple[int, str, str, str]: (索引, 章节内容Markdown, 指示器文本, 状态文本)
    """
    if thesis is None or not thesis.chapters:
        return 0, "", "**第 ? 章**", "❌ 没有可编辑的章节"

    # 边界检查
    total = len(thesis.chapters)
    if chapter_index < 0:
        chapter_index = 0
    elif chapter_index >= total:
        chapter_index = total - 1

    chapter = thesis.chapters[chapter_index]

    # 如果章节还是 pending 且未生成过，自动触发生成
    if chapter.status == "pending" and not chapter.content_markdown:
        try:
            _generate_single_chapter(thesis, chapter_index)
        except Exception as e:
            logger.error(f"自动生成章节失败: {e}")

    # 刷新章节引用（可能已被更新）
    chapter = thesis.chapters[chapter_index]

    content = chapter.content_markdown or f"*（第 {chapter_index + 1} 章待生成）*"
    indicator = f"**第 {chapter_index + 1} 章 / 共 {total} 章**"

    status_text = _build_chapter_status_text(chapter, chapter_index, total)

    return chapter_index, content, indicator, status_text


def on_regenerate_chapter(
    thesis: Optional[Thesis],
    chapter_index: int,
) -> Tuple[Optional[Thesis], str, str]:
    """处理「重新生成本章」按钮

    Args:
        thesis: 当前论文状态
        chapter_index: 章节索引

    Returns:
        Tuple[Thesis, str, str]: (Thesis, 新内容, 状态消息)
    """
    if thesis is None:
        return None, "", "❌ 请先生成大纲"

    if chapter_index < 0 or chapter_index >= len(thesis.chapters):
        return thesis, "", "❌ 无效的章节索引"

    chapter = thesis.chapters[chapter_index]
    if not chapter.can_regenerate():
        return thesis, chapter.content_markdown, "⚠️ 当前章节状态不允许重新生成"

    # 重新生成
    try:
        new_chapter = _generate_single_chapter(thesis, chapter_index, force=True)
        return thesis, new_chapter.content_markdown, f"✅ 第 {chapter_index + 1} 章已重新生成（{new_chapter.word_count} 字）"
    except Exception as e:
        return thesis, chapter.content_markdown, f"❌ 重新生成失败: {e}"


def on_confirm_chapter(
    thesis: Optional[Thesis],
    chapter_index: int,
    edited_content: str,
) -> Tuple[Optional[Thesis], str, str]:
    """处理「确认本章」按钮

    保存用户编辑的内容到 Thesis 中。

    Args:
        thesis: 当前论文状态
        chapter_index: 章节索引
        edited_content: 编辑器中的内容

    Returns:
        Tuple[Thesis, str, str]: (Thesis, 状态消息, 内容回显)
    """
    if thesis is None:
        return None, "❌ 请先生成大纲", ""

    if chapter_index < 0 or chapter_index >= len(thesis.chapters):
        return thesis, "❌ 无效的章节索引", ""

    chapter = thesis.chapters[chapter_index]

    # 保存编辑内容
    if edited_content != chapter.content_markdown:
        chapter.content_markdown = edited_content
        chapter.word_count = estimate_word_count(edited_content)
        chapter.mark_edited()

    total = len(thesis.chapters)
    total_words = thesis.get_total_words()

    if chapter_index + 1 < total:
        msg = (
            f"✅ 第 {chapter_index + 1} 章已保存（{chapter.word_count} 字）。\n"
            f"累计 {total_words:,} / {thesis.target_word_count:,} 字。\n"
            f"可以点击「下一章」继续。"
        )
    else:
        msg = (
            f"🎉 所有章节已完成！\n"
            f"总计 {total_words:,} 字（目标 {thesis.target_word_count:,} 字）。\n"
            f"请切换到「📥 下载成果」Tab 导出论文。"
        )
        # 最后一章确认后，自动检索参考文献
        _auto_fetch_references(thesis)

    return thesis, msg, edited_content


def on_skip_chapter(
    thesis: Optional[Thesis],
    chapter_index: int,
) -> Tuple[Optional[Thesis], str]:
    """处理「跳过」按钮（跳过本章，不生成内容）

    Args:
        thesis: 当前论文状态
        chapter_index: 章节索引

    Returns:
        Tuple[Thesis, str]: (Thesis, 状态消息)
    """
    if thesis is None:
        return None, "❌ 请先生成大纲"

    chapter = thesis.chapters[chapter_index]
    chapter.mark_done()  # 标记为完成（跳过）

    total = len(thesis.chapters)
    return thesis, f"⏭ 已跳过第 {chapter_index + 1}/{total} 章"


# ══════════════════════════════════════════════════════════════
# Tab 4: 下载成果
# ══════════════════════════════════════════════════════════════

def on_download(
    thesis: Optional[Thesis],
    format_choice: str,
) -> str:
    """处理下载按钮

    根据 format_choice 生成对应格式的文件。

    Args:
        thesis: 论文状态
        format_choice: "docx" | "md" | "bib"

    Returns:
        str: 输出文件路径或错误消息
    """
    if thesis is None:
        return "❌ 请先完成论文生成"

    ensure_dir(get_output_dir())

    try:
        if format_choice == "docx":
            output_path = generate_output_filename("thesis", "docx")
            formatter = DocxFormatter()
            formatter.create_document(thesis, output_path)

            # 添加水印和免责声明
            watermarked_path = output_path.replace(".docx", "_final.docx")
            add_watermark_and_disclaimer(output_path, watermarked_path)

            # P1 新增：保存到历史记录
            _save_to_history(thesis, watermarked_path)

            return f"✅ 论文已保存到：{watermarked_path}"

        elif format_choice == "md":
            output_path = generate_output_filename("outline", "md")
            formatter = DocxFormatter()
            formatter.create_outline_doc(thesis, output_path)
            return f"✅ 大纲已保存到：{output_path}"

        elif format_choice == "bib":
            output_path = generate_output_filename("references", "bib")
            bib_content = "\n\n".join(
                ref.to_bibtex() for ref in thesis.references
            ) if thesis.references else "% 暂无参考文献"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(bib_content)
            return f"✅ 参考文献已保存到：{output_path}"

        else:
            return f"❌ 不支持的格式: {format_choice}"

    except Exception as e:
        logger.error(f"文件生成失败: {e}")
        return f"❌ 文件生成失败: {e}"


# ══════════════════════════════════════════════════════════════
# 内部辅助函数
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
# P1 Tab 1 追加: 数据上传 & 异步生成
# ══════════════════════════════════════════════════════════════

def on_upload_data(
    data_file,
    thesis: Optional[Thesis],
) -> Tuple[Optional[Thesis], str]:
    """处理数据文件上传（P1 新增）

    解析 .xlsx / .csv 文件并转换为 prompt 文本，注入到 Thesis 的 user_data 中。

    Args:
        data_file: 上传的文件路径或 None
        thesis: 当前论文状态

    Returns:
        Tuple[Thesis, str]: (更新后的Thesis, 状态消息)
    """
    if data_file is None:
        return thesis, ""

    if thesis is None:
        thesis = Thesis()

    try:
        importer = DataImporter()
        parsed = importer.import_file(data_file)
        prompt_text = importer.to_prompt_text(parsed)

        thesis.user_data["prompt_text"] = prompt_text
        thesis.user_data["raw_data"] = parsed.get("raw_data", [])
        thesis.user_data["data_columns"] = parsed.get("columns", [])
        thesis.user_data["data_summary"] = parsed.get("summary", "")
        thesis.user_data["data_file_name"] = parsed.get("file_name", "")

        chart_hint = importer.detect_chart_suggestion(parsed)
        if chart_hint:
            thesis.user_data["chart_suggestion"] = chart_hint

        row_count = len(parsed.get("raw_data", []))
        col_count = len(parsed.get("columns", []))
        msg = f"✅ 数据已加载：{row_count} 行 × {col_count} 列 (来自 {parsed.get('file_name', 'unknown')})"
        if chart_hint:
            msg += f"\n📊 建议图表：{chart_hint}"

        logger.info(f"数据上传成功: {row_count} 行 × {col_count} 列")
        return thesis, msg

    except Exception as e:
        logger.error(f"数据上传失败: {e}")
        return thesis, f"❌ 数据文件解析失败: {e}"


# ══════════════════════════════════════════════════════════════
# P1 Tab 5: 历史管理
# ══════════════════════════════════════════════════════════════

def on_load_history() -> Tuple[List, str]:
    """加载所有生成历史记录 (P2: 从 SQLite 读取)

    Returns:
        Tuple[List, str]: (DataFrame 行数据, 状态消息)
    """
    try:
        store = get_history_store()
        rows = store.as_dataframe_rows()
        if not rows:
            return [], "📭 暂无历史记录"
        return rows, f"📊 共 {len(rows)} 条历史记录（SQLite 持久化）"
    except Exception as e:
        logger.error(f"加载历史失败: {e}")
        return [], f"❌ 加载历史失败: {e}"


def _save_to_history(thesis: Thesis, output_path: str) -> None:
    """将当前论文保存到历史记录（P2: SQLite 持久化）

    Args:
        thesis: 论文状态
        output_path: 输出文件路径
    """
    import uuid
    record = HistoryRecord(
        id=uuid.uuid4().hex[:12],
        topic=thesis.topic,
        keywords=thesis.keywords,
        word_count=thesis.get_total_words(),
        chapter_count=len(thesis.chapters),
        ref_count=len(thesis.references),
        output_path=output_path,
        created_at=datetime.now().isoformat(),
    )
    store = get_history_store()
    store.save(record)


def on_format_check(
    thesis: Optional[Thesis],
) -> str:
    """检查生成文档与模板的格式差异（P2 新增）

    Args:
        thesis: 论文状态

    Returns:
        str: Markdown 格式对比报告
    """
    if thesis is None:
        return "❌ 请先完成论文生成。"

    checker = FormatChecker()
    if thesis.template_styles and thesis.template_path:
        report = checker.compare_by_path(thesis.template_path, thesis.template_path)
    else:
        # 对比默认模板
        default_template = TemplateParser().get_preset("qlu")
        if default_template and thesis.template_styles:
            report = checker.compare(default_template, thesis.template_styles)
        else:
            report = "⚠️ 无可对比的模板信息。请上传模板或完成论文生成后再试。"

    return report


def on_template_select(template_id: str) -> str:
    """选择预设模板（P2 新增）

    Args:
        template_id: 模板 ID

    Returns:
        str: 状态消息
    """
    parser = TemplateParser()
    preset = parser.get_preset(template_id)
    if preset:
        return (
            f"✅ 已选择模板：**{preset.template_name}**\n\n"
            f"{preset.template_description}\n\n"
            f"- 正文字体：{preset.body_style.font_name} {preset.body_style.font_size}pt\n"
            f"- 页边距：上{preset.page_margins['top']}mm 下{preset.page_margins['bottom']}mm "
            f"左{preset.page_margins['left']}mm 右{preset.page_margins['right']}mm"
        )
    return "❌ 无效的模板 ID"


# ══════════════════════════════════════════════════════════════
# P3 Tab 6: 模拟盲审
# ══════════════════════════════════════════════════════════════

def on_full_review(
    thesis: Optional[Thesis],
) -> str:
    """执行完整论文多智能体盲审（P3 新增）

    Args:
        thesis: 论文状态

    Returns:
        str: Markdown 格式的评审报告
    """
    if thesis is None:
        return "❌ 请先完成论文生成（至少需要生成大纲和章节内容）。"

    if not thesis.chapters or all(ch.status == "pending" for ch in thesis.chapters):
        return "❌ 请先生成至少一个章节的内容后再进行评审。"

    # 创建 LLM 客户端
    try:
        config = load_config()
        llm_client = create_llm_client(config.llm_provider, config)
    except Exception as e:
        return f"❌ LLM 客户端初始化失败: {e}"

    # 执行评审
    try:
        engine = ReviewEngine(llm_client)
        result = engine.review(thesis)

        if "error" in result:
            return f"❌ 评审失败: {result['error']}"

        # 输出报告
        report = result["report_md"]
        timestamp = result.get("timestamp", "")[:19]

        return f"*评审完成于 {timestamp}*\n\n{report}"

    except Exception as e:
        logger.error(f"盲审失败: {e}")
        return f"❌ 盲审执行失败: {e}"


# ══════════════════════════════════════════════════════════════
# P4 新回调：统计洞察 + 查重
# ══════════════════════════════════════════════════════════════

def on_stats_analysis(thesis: Optional[Thesis]) -> str:
    """执行数据统计洞察分析（P4 新增）

    Args:
        thesis: 论文状态

    Returns:
        str: Markdown 分析报告
    """
    if thesis is None or not thesis.user_data.get("raw_data"):
        return "❌ 请先在 Tab1 上传数据文件（.xlsx/.csv），生成论文后再进行分析。"

    try:
        engine = StatsEngine()
        data = thesis.user_data.get("raw_data", [])
        columns = thesis.user_data.get("data_columns", [])
        sample_count = len(data)

        report = [f"## 📊 数据统计洞察", f""]

        # 1. 实验设计检查
        report.append("### 1. 实验设计前置检查\n")
        design_warnings = engine.check_design(columns, sample_count)
        if design_warnings:
            for w in design_warnings:
                emoji = {"critical": "🔴", "warning": "🟡", "info": "ℹ️"}.get(w["severity"], "")
                report.append(f"- {emoji} **{w['message']}**")
                report.append(f"  → {w['suggestion']}")
        else:
            report.append("✅ 未发现明显的实验设计问题。")
        report.append("")

        # 2. 检验推荐
        report.append("### 2. 统计检验推荐\n")
        tests = engine.recommend_tests(data, columns)
        for i, t in enumerate(tests, 1):
            report.append(f"**{i}. {t['test']}**")
            report.append(f"- 原因：{t['reason']}")
            if t.get("alternative_test"):
                report.append(f"- 备选：{t['alternative_test']}")
            if t.get("post_hoc"):
                report.append(f"- 事后检验：{t['post_hoc']}")
            if t.get("note"):
                report.append(f"- ⚠️ {t['note']}")
            report.append("")

        # 3. 可复现性
        report.append("### 3. 可复现性检查\n")
        repro_issues = engine.check_reproducibility()
        if repro_issues:
            for issue in repro_issues:
                emoji = {"critical": "🔴", "warning": "🟡", "info": "ℹ️"}.get(issue["severity"], "")
                report.append(f"- {emoji} **{issue['aspect']}**：{issue['issue']}")
                report.append(f"  → {issue['fix']}")
        else:
            report.append("ℹ️ 未检测到代码片段，跳过可复现性检查。")
        report.append("")

        # 4. 如果数据允许，运行一个推荐检验
        if tests and tests[0]["test"] != "描述性统计":
            t = tests[0]
            result = engine.run_test(data, columns,
                                    "ttest" if "t" in t["test"].lower() else "pearson",
                                    t["columns"][0],
                                    t["columns"][1] if len(t["columns"]) > 1 else None)
            if "apa_text" in result:
                report.append("### 4. 自动检验结果\n")
                report.append(f"```\n{result['apa_text']}\n```")

        return "\n".join(report)

    except Exception as e:
        logger.error(f"统计分析失败: {e}")
        return f"❌ 统计分析失败: {e}"


def on_plagiarism_check(thesis: Optional[Thesis]) -> str:
    """执行文本查重预检（P4 新增）

    Args:
        thesis: 论文状态

    Returns:
        str: Markdown 查重报告
    """
    if thesis is None or not thesis.chapters:
        return "❌ 请先生成论文内容。"

    # 收集全部文本
    all_texts = []
    for ch in thesis.chapters:
        if ch.content_markdown:
            all_texts.append(ch.content_markdown)

    full_text = "\n\n".join(all_texts)
    if len(full_text) < 100:
        return "⚠️ 文本过短（< 100 字符），无法有效检查重复。"

    try:
        checker = PlagiarismChecker()
        result = checker.check_document(full_text)

        report = [f"## 🔍 查重预检", f""]
        report.append(f"**风险等级**：{result.get('risk_level', 'low')}")
        report.append(f"**摘要**：{result.get('summary', '')}")
        report.append("")

        issues = result.get("issues", [])
        if issues:
            report.append("### 疑似重复段落\n")
            for i, issue in enumerate(issues, 1):
                emoji = {"high": "🔴", "medium": "🟡"}.get(issue.get("severity", ""), "")
                report.append(f"**{i}. {emoji} {issue.get('message', '')}**")
                if issue.get("type") == "internal_duplicate":
                    report.append(f"  - 段落 {issue.get('paragraph_a', '?')}: {issue.get('preview_a', '')}")
                    report.append(f"  - 段落 {issue.get('paragraph_b', '?')}: {issue.get('preview_b', '')}")
                report.append("")
        else:
            report.append("✅ 未发现明显重复内容。")

        return "\n".join(report)

    except Exception as e:
        logger.error(f"查重失败: {e}")
        return f"❌ 查重预检失败: {e}"


# ══════════════════════════════════════════════════════════════
# Tab 内部辅助
# ══════════════════════════════════════════════════════════════

def _parse_keywords(keywords_str: str) -> List[str]:
    """解析关键词字符串

    支持逗号、空格、中英文逗号分隔。

    Args:
        keywords_str: 关键词字符串

    Returns:
        List[str]: 关键词列表
    """
    if not keywords_str:
        return []
    # 替换中英文逗号为统一分隔符
    normalized = keywords_str.replace("，", ",").replace("、", ",")
    keywords = [kw.strip() for kw in normalized.split(",") if kw.strip()]
    # 再去空格分词
    if not keywords:
        keywords = [kw.strip() for kw in keywords_str.split() if kw.strip()]
    return keywords


def _build_chapter_status_text(
    chapter: Chapter,
    index: int,
    total: int,
) -> str:
    """构建章节状态文本

    Args:
        chapter: 章节对象
        index: 章节索引
        total: 总章数

    Returns:
        str: Markdown 格式的状态文本
    """
    status_labels = {
        "pending": "⏳ 待生成",
        "generating": "🔄 生成中...",
        "done": "✅ 已生成",
        "edited": "✏️ 已编辑",
    }
    status_label = status_labels.get(chapter.status, "❓ 未知")

    lines = [
        f"**章节状态**：{status_label}",
        f"**字数**：{chapter.word_count:,} 字",
    ]
    if chapter.generated_at:
        lines.append(f"**生成时间**：{chapter.generated_at[:19]}")

    return "\n".join(lines)


def _get_llm_client_for_thesis() -> object:
    """根据当前配置创建 LLM 客户端

    Returns:
        BaseLLMClient: LLM 客户端实例
    """
    config = load_config()
    return create_llm_client(config.llm_provider, config)


def _generate_single_chapter(
    thesis: Thesis,
    chapter_index: int,
    force: bool = False,
) -> Chapter:
    """生成单个章节的正文内容

    Args:
        thesis: 论文状态
        chapter_index: 章节索引
        force: 是否强制重新生成

    Returns:
        Chapter: 生成后的章节对象

    Raises:
        RuntimeError: 生成失败时
    """
    chapter = thesis.chapters[chapter_index]

    if chapter.status == "generating" and not force:
        raise RuntimeError("章节正在生成中，请稍后")

    chapter.mark_generating()

    # 前序章节（用于上下文传递）
    prev_chapters = [
        ch for i, ch in enumerate(thesis.chapters)
        if i < chapter_index and ch.status in ("done", "edited")
    ]

    # 创建 LLM 客户端
    llm_client = _get_llm_client_for_thesis()

    # 生成章节
    generator = ChapterGenerator(llm_client)

    # 计算该章目标字数
    chapter_nodes = thesis.outline.get_chapters()
    total_chapters = len(chapter_nodes)
    words_per_chapter = _allocate_chapter_words(thesis.target_word_count, chapter_index, total_chapters)

    new_chapter = generator.generate_chapter(
        outline=thesis.outline,
        node=chapter.node,
        prev_chapters=prev_chapters,
        user_data=None,
        target_words=words_per_chapter,
    )

    # 更新 thesis 中的章节
    thesis.chapters[chapter_index] = new_chapter
    return new_chapter


def _allocate_chapter_words(
    total_words: int,
    chapter_index: int,
    total_chapters: int,
) -> int:
    """为章节分配字数

    Args:
        total_words: 目标总字数
        chapter_index: 当前章节索引（从0开始）
        total_chapters: 总章数

    Returns:
        int: 该章目标字数
    """
    if total_chapters <= 2:
        return total_words // total_chapters

    if chapter_index == 0:
        # 绪论 10%
        return int(total_words * 0.10)
    elif chapter_index == total_chapters - 1:
        # 总结 8%
        return int(total_words * 0.08)
    else:
        # 核心章节均分 82%
        core_count = total_chapters - 2
        return int(total_words * 0.82 / max(core_count, 1))


def _auto_fetch_references(thesis: Thesis) -> None:
    """自动检索参考文献（所有章节完成后调用）

    Args:
        thesis: 论文状态（原地修改）
    """
    if thesis.references:
        return  # 已有参考文献，不重复检索

    try:
        # 收集所有章节标题作为搜索关键词
        chapter_titles = [ch.node.title for ch in thesis.chapters]

        fetcher = ReferenceFetcher()
        refs = fetcher.fetch_for_outline(
            keywords=thesis.keywords,
            chapter_titles=chapter_titles,
        )
        thesis.references = refs

        logger.info(f"自动检索到 {len(refs)} 篇参考文献")
    except Exception as e:
        logger.warning(f"自动检索参考文献失败: {e}")
