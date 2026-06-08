"""
大纲生成器

将论文主题和关键词输入 LLM，生成结构化的论文大纲树。

核心流程：
1. 构建 Prompt（System + User）
2. 调用 LLM 获取 Markdown 大纲文本
3. 解析 Markdown → Outline 树结构
4. 支持用户反馈后重新生成
"""

import re
import json
import logging
from typing import List, Optional

from llm.base import BaseLLMClient
from core.models import Outline, OutlineNode
from prompts.outline_prompts import (
    OUTLINE_SYSTEM_PROMPT,
    OUTLINE_FEEDBACK_SYSTEM_PROMPT,
    build_outline_user_prompt,
    build_outline_feedback_prompt,
)

logger = logging.getLogger(__name__)


class OutlineGenerator:
    """大纲生成器

    将主题+关键词输入 LLM，解析返回的 Markdown 为大 Outline 树结构。

    Attributes:
        llm: LLM 客户端实例
    """

    def __init__(self, llm: BaseLLMClient):
        """初始化大纲生成器

        Args:
            llm: LLM 客户端（DeepSeek 或 OpenAI）
        """
        self.llm = llm

    def generate(
        self,
        topic: str,
        keywords: List[str],
        discipline: str,
        target_word_count: int = 15000,
    ) -> Outline:
        """生成论文大纲

        完整流程：构建 Prompt → 调用 LLM → 解析 Markdown → 构建树

        Args:
            topic: 论文主题
            keywords: 关键词列表
            discipline: 学科方向
            target_word_count: 目标总字数

        Returns:
            Outline: 结构化的论文大纲对象

        Raises:
            RuntimeError: LLM 调用失败时
        """
        # 1. 构建消息
        system_msg = OUTLINE_SYSTEM_PROMPT
        user_msg = build_outline_user_prompt(
            topic=topic,
            keywords=keywords,
            discipline=discipline,
            target_word_count=target_word_count,
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        logger.info(f"开始生成大纲: topic='{topic}', discipline='{discipline}'")

        # 2. 调用 LLM
        try:
            md_text = self.llm.chat(
                messages=messages,
                temperature=0.6,  # 大纲生成使用较低温度以确保结构严谨
            )
        except Exception as e:
            logger.error(f"大纲生成失败: {e}")
            raise RuntimeError(f"大纲生成失败: {e}") from e

        if not md_text or not md_text.strip():
            raise RuntimeError("LLM 返回的大纲内容为空，请重试")

        # 3. 解析 Markdown → Outline 树
        try:
            outline = self._parse_markdown_to_outline(
                md_text=md_text,
                topic=topic,
                keywords=keywords,
                discipline=discipline,
            )
        except Exception as e:
            logger.error(f"大纲解析失败: {e}\n原始文本:\n{md_text[:500]}")
            raise RuntimeError(
                f"大纲解析失败: {e}。LLM 返回格式异常，请重试"
            ) from e

        logger.info(
            f"大纲生成成功: {len(outline.flat_list())} 个节点, "
            f"{len(outline.get_chapters())} 章"
        )
        return outline

    def regenerate_with_feedback(
        self,
        outline: Outline,
        feedback: str,
    ) -> Outline:
        """根据用户反馈重新生成大纲

        保留原始主题和关键词，基于用户反馈重新生成。

        Args:
            outline: 原始大纲（用于提取主题信息）
            feedback: 用户反馈文本

        Returns:
            Outline: 更新后的大纲
        """
        original_md = outline.to_markdown()
        system_msg = OUTLINE_FEEDBACK_SYSTEM_PROMPT
        user_msg = build_outline_feedback_prompt(
            original_outline_md=original_md,
            feedback=feedback,
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        logger.info(f"根据反馈重新生成大纲: '{feedback[:100]}...'")

        try:
            md_text = self.llm.chat(messages=messages, temperature=0.6)
        except Exception as e:
            raise RuntimeError(f"大纲重新生成失败: {e}") from e

        if not md_text or not md_text.strip():
            raise RuntimeError("LLM 返回的大纲内容为空，请重试")

        try:
            new_outline = self._parse_markdown_to_outline(
                md_text=md_text,
                topic=outline.topic,
                keywords=outline.keywords,
                discipline=outline.discipline,
            )
        except Exception as e:
            raise RuntimeError(f"大纲重新解析失败: {e}") from e

        return new_outline

    # ── 内部方法 ──────────────────────────────────────────────

    def _parse_markdown_to_outline(
        self,
        md_text: str,
        topic: str,
        keywords: List[str],
        discipline: str,
    ) -> Outline:
        """将 Markdown 大纲文本解析为 Outline 树结构

        解析规则：
        - ## 开头 → level 1（章节点）
        - ### 开头 → level 2（节节点）
        - #### 开头 → level 3（子节节点）
        - > 引用 → 上一节点的 content 描述

        Args:
            md_text: Markdown 大纲文本
            topic: 论文主题
            keywords: 关键词
            discipline: 学科

        Returns:
            Outline: 结构化的论文大纲
        """
        # 创建根节点
        root = OutlineNode(
            id="root",
            title=topic,
            level=0,
        )

        # 节点栈：用于跟踪层级关系
        # stack[0] = root, stack[1] = 最近的章级节点, stack[2] = 最近的节级节点
        stack: List[OutlineNode] = [root]
        chapter_counter = 0
        section_counters: List[int] = [0, 0, 0]  # [章计数, 节计数, 子节计数]

        lines = md_text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 跳过空行和水平线
            if not line or re.match(r'^[-*_]{3,}$', line):
                i += 1
                continue

            # 解析标题: ## 章, ### 节, #### 子节
            heading_match = re.match(r'^(#{2,4})\s+(.+)$', line)
            if heading_match:
                hashes = heading_match.group(1)
                title = heading_match.group(2).strip()
                # 去除 Markdown 加粗/斜体标记
                title = re.sub(r'[\*_]{1,3}', '', title)

                level = len(hashes) - 1  # ## → 1, ### → 2, #### → 3

                # 生成节点 ID
                if level == 1:
                    chapter_counter += 1
                    node_id = f"ch{chapter_counter}"
                    section_counters = [chapter_counter, 0, 0]
                elif level == 2:
                    section_counters[1] += 1
                    node_id = f"ch{section_counters[0]}_sec{section_counters[1]}"
                    section_counters[2] = 0
                else:  # level == 3
                    section_counters[2] += 1
                    node_id = f"ch{section_counters[0]}_sec{section_counters[1]}_sub{section_counters[2]}"

                # 创建节点
                node = OutlineNode(
                    id=node_id,
                    title=title,
                    level=level,
                )

                # 确定父节点：向上回溯栈找到 level 比当前小的最近节点
                while len(stack) > 1 and stack[-1].level >= level:
                    stack.pop()

                parent = stack[-1]
                parent.children.append(node)
                stack.append(node)

                i += 1
                continue

            # 解析描述行: > 引用
            desc_match = re.match(r'^>\s*(.+)$', line)
            if desc_match and len(stack) > 1:
                description = desc_match.group(1).strip()
                # 添加到当前节点（栈顶）的 content
                current_node = stack[-1]
                if current_node.content:
                    current_node.content += "\n" + description
                else:
                    current_node.content = description

            # 跳过注释和无格式行
            i += 1

        # 验证：至少要有章节节点
        if not root.children:
            raise ValueError("解析失败：未找到任何章级标题（##）")

        outline = Outline(
            topic=topic,
            keywords=keywords,
            discipline=discipline,
            root=root,
        )
        return outline
