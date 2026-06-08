"""
参考文献相关 Prompt 模板（P1-R8）

指导 LLM 在生成章节时插入引用标记 + 关联真实文献。
"""


SYSTEM_PROMPT = """你是一位{discipline}领域的学术论文作者。你正在撰写论文的一个章节。

以下是一组真实存在的参考文献。请在正文中适当位置插入引用标记，
标记格式为 [{key}]（用花括号包裹文献的引用键）。

参考文献列表：
{references_text}

引用要求：
1. 每个关键论述或技术点至少引用 1 篇文献
2. 引用标记放在句末标点之前，如"深度学习模型在图像分类中表现优异[{Smith2024}]。"
3. 不要编造不存在于上述列表的引用
4. 同一文献可多次引用
"""


def build_user_prompt(
    chapter_title: str,
    chapter_context: str,
    references_text: str,
    user_data: str = "",
) -> str:
    """构建带参考文献的章节生成 prompt

    Args:
        chapter_title: 当前章节标题
        chapter_context: 前文章节摘要/上下文
        references_text: 格式化后的参考文献列表文本
        user_data: 用户上传的结构化数据文本（可选）

    Returns:
        str: 完整的 user prompt
    """
    prompt_parts = [f"请撰写以下论文章节的内容："]

    if chapter_context:
        prompt_parts.append(f"\n前文摘要（保持上下文连贯）：\n{chapter_context}")

    prompt_parts.append(f"\n当前章节：{chapter_title}")

    if user_data:
        prompt_parts.append(f"\n用户提供的真实数据：\n{user_data}")

    prompt_parts.append("""
写作要求：
- 学术语言，严谨规范
- 逻辑清晰，段落分明
- 每个论点应有论据支撑（可以是参考文献、数据或理论）
- 适当使用 Markdown 格式（标题用 ##、###，列表用 - 或 1.）
- 如有表格数据，使用 Markdown 表格语法
- 所有引用使用 [{key}] 格式

请直接开始撰写正文，不需要前置说明。""")

    return "\n".join(prompt_parts)


def build_references_text(references: list, refs_per_chapter: int = 10) -> str:
    """将参考文献列表格式化为 prompt 可用的文本

    Args:
        references: Reference 对象列表
        refs_per_chapter: 每章最多展示的参考文献数

    Returns:
        str: 格式化的参考文献文本
    """
    if not references:
        return "（暂无可用参考文献）"

    lines = []
    for i, ref in enumerate(references[:refs_per_chapter], 1):
        authors_short = ref.authors[0].split()[-1] if ref.authors else "Unknown"
        lines.append(
            f"[{ref.key}] {authors_short} ({ref.year}). "
            f"{ref.title}. {ref.venue}."
        )
        if ref.abstract:
            lines.append(f"  摘要: {ref.abstract[:200]}...")

    return "\n".join(lines)
