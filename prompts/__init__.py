"""prompts - Prompt 模板模块

集中管理所有 LLM Prompt，便于维护和调优。
"""

from prompts.outline_prompts import (
    OUTLINE_SYSTEM_PROMPT,
    OUTLINE_FEEDBACK_SYSTEM_PROMPT,
    build_outline_user_prompt,
    build_outline_feedback_prompt,
)

from prompts.chapter_prompts import (
    CHAPTER_SYSTEM_PROMPT,
    CITATION_GUIDELINES,
    build_chapter_user_prompt,
    build_prev_chapters_summary,
)

__all__ = [
    "OUTLINE_SYSTEM_PROMPT",
    "OUTLINE_FEEDBACK_SYSTEM_PROMPT",
    "build_outline_user_prompt",
    "build_outline_feedback_prompt",
    "CHAPTER_SYSTEM_PROMPT",
    "CITATION_GUIDELINES",
    "build_chapter_user_prompt",
    "build_prev_chapters_summary",
]
