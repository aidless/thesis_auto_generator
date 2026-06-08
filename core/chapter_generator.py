"""
章节内容生成器

逐章生成论文正文内容，支持：
- 上下文传递（前序章节摘要）
- 进度回调（用于 Gradio 进度条更新）
- 用户补充数据注入
- 字数自动分配
"""

import logging
import threading
from datetime import datetime
from typing import List, Optional, Callable

from llm.base import BaseLLMClient
from core.models import Outline, OutlineNode, Chapter, Thesis
from prompts.chapter_prompts import (
    CHAPTER_SYSTEM_PROMPT,
    CITATION_GUIDELINES,
    build_chapter_user_prompt,
    build_prev_chapters_summary,
)
from utils.text_utils import estimate_word_count

logger = logging.getLogger(__name__)


class ChapterGenerator:
    """章节内容生成器

    对大纲中的每个章节点，调用 LLM 生成完整的章节正文（Markdown 格式）。

    Attributes:
        llm: LLM 客户端实例
    """

    def __init__(self, llm: BaseLLMClient):
        """初始化章节生成器

        Args:
            llm: LLM 客户端
        """
        self.llm = llm
        self._lock = threading.Lock()  # 防止并发回调冲突

    def generate_chapter(
        self,
        outline: Outline,
        node: OutlineNode,
        prev_chapters: List[Chapter],
        user_data: Optional[str] = None,
        target_words: Optional[int] = None,
        references_text: Optional[str] = None,
    ) -> Chapter:
        """生成单个章节的正文内容

        Args:
            outline: 完整论文大纲
            node: 要生成内容的章节点（level==1）
            prev_chapters: 已生成的前序章节列表
            user_data: 用户补充的数据/要求（可选）
            target_words: 该章目标字数（None 则由系统自动分配）
            references_text: 参考文献 prompt 文本（P1 新增）

        Returns:
            Chapter: 填充了内容的章节对象

        Raises:
            RuntimeError: LLM 调用失败时
        """
        if node.level != 1:
            raise ValueError(f"generate_chapter 只接受章级节点（level==1），当前 level={node.level}")

        # 构建前序章节摘要
        prev_summary = build_prev_chapters_summary(prev_chapters)

        # 确定目标字数
        if target_words is None:
            target_words = self._allocate_words(
                outline=outline,
                node=node,
                total_chapters=len(outline.get_chapters()),
                prev_chapters=prev_chapters,
            )

        # 构建章节描述
        chapter_desc = node.content or ""
        chapter_title = node.title

        # 组装完整标题（含子节点概要）
        section_titles = [child.title for child in node.children]
        if section_titles:
            chapter_desc += "\n\n本章包含以下各节：\n" + "\n".join(
                f"- {t}" for t in section_titles
            )

        # 构建 Prompt
        outline_md = outline.to_markdown()
        user_msg = build_chapter_user_prompt(
            chapter_title=chapter_title,
            chapter_description=chapter_desc,
            full_outline_md=outline_md,
            target_word_count=target_words,
            prev_chapters_summary=prev_summary,
            user_data=user_data or "",
        )

        # 添加引用规范到 System Prompt
        system_msg = CHAPTER_SYSTEM_PROMPT + "\n" + CITATION_GUIDELINES

        # P1 新增：如果有真实参考文献，用 reference prompt 替换引用规范
        if references_text:
            discipline = outline.discipline
            system_msg = system_msg.replace(
                "{discipline}", discipline
            )
            system_msg += f"\n\n{references_text}"

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        logger.info(f"开始生成章节: '{chapter_title}', 目标 {target_words} 字")

        # 调用 LLM
        try:
            content = self.llm.chat(
                messages=messages,
                temperature=0.7,
                max_tokens=min(self.llm.max_tokens, target_words * 2 + 500),
            )
        except Exception as e:
            logger.error(f"章节生成失败 [{chapter_title}]: {e}")
            raise RuntimeError(f"章节「{chapter_title}」生成失败: {e}") from e

        if not content or not content.strip():
            raise RuntimeError(f"章节「{chapter_title}」生成内容为空")

        # 统计字数
        word_count = estimate_word_count(content)

        # 构建 Chapter 对象
        chapter = Chapter(
            node=node,
            content_markdown=content,
            status="done",
            word_count=word_count,
            generated_at=datetime.now().isoformat(),
        )

        logger.info(f"章节生成完成: '{chapter_title}', 实际 {word_count} 字")
        return chapter

    def generate_all(
        self,
        outline: Outline,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        user_data: Optional[str] = None,
    ) -> List[Chapter]:
        """顺序生成大纲中所有章节

        逐章调用 generate_chapter()，通过 progress_callback 通知进度。

        Args:
            outline: 论文大纲
            progress_callback: 进度回调 (current, total, status_text)
            user_data: 用户补充数据（应用于所有章节）

        Returns:
            List[Chapter]: 已生成的所有章节
        """
        chapter_nodes = outline.get_chapters()
        total = len(chapter_nodes)
        chapters: List[Chapter] = []

        for i, node in enumerate(chapter_nodes):
            # 更新进度
            if progress_callback:
                progress_callback(
                    i,
                    total,
                    f"正在生成第 {i+1}/{total} 章：{node.title}...",
                )

            try:
                chapter = self.generate_chapter(
                    outline=outline,
                    node=node,
                    prev_chapters=chapters,
                    user_data=user_data,
                )
                chapters.append(chapter)
            except Exception as e:
                logger.error(f"第 {i+1} 章生成失败: {e}")
                # 创建失败标记章节
                failed_chapter = Chapter(
                    node=node,
                    content_markdown=f"*[生成失败: {e}]*",
                    status="pending",  # 保持 pending 允许重试
                    word_count=0,
                )
                chapters.append(failed_chapter)

            # 更新进度
            if progress_callback:
                progress_callback(
                    i + 1,
                    total,
                    f"已完成 {i+1}/{total} 章",
                )

        return chapters

    def retry_chapter(
        self,
        outline: Outline,
        chapter: Chapter,
        prev_chapters: List[Chapter],
        user_data: Optional[str] = None,
    ) -> Chapter:
        """重新生成指定章节

        Args:
            outline: 论文大纲
            chapter: 要重新生成的章节（含原始大纲节点）
            prev_chapters: 前序章节列表
            user_data: 用户补充数据

        Returns:
            Chapter: 重新生成后的章节
        """
        return self.generate_chapter(
            outline=outline,
            node=chapter.node,
            prev_chapters=prev_chapters,
            user_data=user_data,
            target_words=chapter.word_count or None,
        )

    # ── 内部方法 ──────────────────────────────────────────────

    def _allocate_words(
        self,
        outline: Outline,
        node: OutlineNode,
        total_chapters: int,
        prev_chapters: List[Chapter],
    ) -> int:
        """为章节分配目标字数

        分配策略：
        - 绪论（第1章）：10%
        - 总结（最后1章）：8%
        - 其余章节：均分剩余的 82%

        Args:
            outline: 大纲
            node: 当前章节节点
            total_chapters: 总章数
            prev_chapters: 前序章节（用于定位当前章节索引）

        Returns:
            int: 该章目标字数
        """
        if total_chapters <= 2:
            # 只有 2 章的情况：各半
            return 7500

        # 计算当前章节是第几章
        chapter_nodes = outline.get_chapters()
        chapter_index = 0
        for i, cn in enumerate(chapter_nodes):
            if cn.id == node.id:
                chapter_index = i
                break

        # 默认目标总字数
        total_words = 15000

        if total_chapters >= 3:
            if chapter_index == 0:
                # 绪论 10%
                return int(total_words * 0.10)
            elif chapter_index == total_chapters - 1:
                # 总结 8%
                return int(total_words * 0.08)
            else:
                # 核心章节均分 82%
                core_chapters = total_chapters - 2
                return int(total_words * 0.82 / max(core_chapters, 1))
        else:
            # 兜底：均分
            return int(total_words / total_chapters)
