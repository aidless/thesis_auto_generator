"""
批判性综述生成器（P3）

基于知识图谱的数据，使用 LLM 生成批判性文献综述。
"""

import json
import logging
from typing import Dict, List, Optional

from llm.base import BaseLLMClient
from core.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


CRITICAL_REVIEW_SYSTEM_PROMPT = """你是一位计算机科学领域的资深研究者，擅长撰写批判性文献综述。

你的任务是：基于提供的文献知识图谱数据，生成一段学术水准的"研究现状综述"。

## 要求

1. **识别研究脉络**：从经典文献到前沿研究，清晰描述该领域的发展路径
2. **发现研究群落**：指出不同研究方向/社区的核心贡献和差异
3. **标注争议点**：如果图谱中存在不同方向，指出它们的方法论分歧
4. **指出研究空白**：基于图谱覆盖范围，分析未充分探索的方向

## 输出格式

请输出 Markdown 格式的综述文本，包含：
- ## 1. 领域发展脉络
- ## 2. 主要研究群落
- ## 3. 方法对比与争议
- ## 4. 研究空白与机遇
"""


class CriticalReviewer:
    """批判性综述生成器

    基于 KnowledgeGraph 的 JSON 摘要 + LLM 生成综述段落。

    Attributes:
        llm: LLM 客户端
        graph: 知识图谱实例
    """

    def __init__(self, llm: BaseLLMClient):
        """初始化综述生成器

        Args:
            llm: LLM 客户端
        """
        self.llm = llm

    def generate(
        self,
        graph: KnowledgeGraph,
        topic: str = "",
    ) -> str:
        """生成批判性文献综述

        Args:
            graph: 已构建的知识图谱
            topic: 论文主题

        Returns:
            str: Markdown 格式的综述文本
        """
        # 获取图谱摘要
        summary = graph.to_json_summary()
        if summary["statistics"]["nodes"] == 0:
            return "（图谱中无文献节点，无法生成综述）"

        # 构建 Prompt
        graph_text = json.dumps(summary, ensure_ascii=False, indent=2)
        user_msg = (
            f"论文主题：{topic}\n\n"
            f"以下是一个文献知识图谱的结构化摘要（JSON 格式）：\n\n"
            f"```json\n{graph_text}\n```\n\n"
            f"请基于以上数据，撰写批判性文献综述。"
            f"确保所有引用的论文都来自图谱数据，不要编造不存在的文献。"
        )

        messages = [
            {"role": "system", "content": CRITICAL_REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        try:
            response = self.llm.chat(
                messages=messages,
                temperature=0.4,
                max_tokens=4096,
            )
            logger.info(f"批判性综述已生成: {len(response)} 字符")
            return response
        except Exception as e:
            logger.error(f"综述生成失败: {e}")
            return f"*（综述生成失败: {e}）*\n\n{self._fallback_review(graph)}"

    @staticmethod
    def _fallback_review(graph: KnowledgeGraph) -> str:
        """LLM 不可用时的回退综述（纯统计描述）

        Args:
            graph: 知识图谱

        Returns:
            str: 回退综述文本
        """
        stats = graph.get_statistics()
        critical_path = graph.get_critical_path()[:5]

        lines = [
            "## 1. 文献统计（离线模式）",
            "",
            f"- 共检索到 {stats.get('nodes', 0)} 篇相关文献",
            f"- 文献时间范围：{stats.get('year_range', 'N/A')}",
        ]

        if critical_path:
            lines.append("\n## 2. 关键文献\n")
            for i, key in enumerate(critical_path, 1):
                p = graph.papers.get(key)
                if p:
                    title = p.title[:80]
                    year = p.year
                    authors = ", ".join(p.authors[:2])
                    lines.append(f"{i}. **{title}** ({year}) — {authors}")
                    if p.abstract:
                        lines.append(f"   > {p.abstract[:150]}...")

        return "\n".join(lines)
