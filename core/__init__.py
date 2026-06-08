"""core - 核心业务逻辑模块

包含：
- models: 数据类定义（无外部依赖，总是可用）
- outline_generator: 大纲生成
- chapter_generator: 章节生成
- reference_fetcher: 文献检索
- template_parser: 模板解析
- docx_formatter: DOCX 格式化
"""

# 数据模型（无外部依赖，总是可导入）
from core.models import (
    OutlineNode,
    Outline,
    Chapter,
    Reference,
    StyleDef,
    TemplateStyles,
    Thesis,
    GenerationConfig,
)

# 业务模块（可能有外部依赖，使用 try/except 友好降级）
try:
    from core.outline_generator import OutlineGenerator
except ImportError:
    OutlineGenerator = None  # type: ignore

try:
    from core.chapter_generator import ChapterGenerator
except ImportError:
    ChapterGenerator = None  # type: ignore

try:
    from core.reference_fetcher import ReferenceFetcher
except ImportError:
    ReferenceFetcher = None  # type: ignore

try:
    from core.template_parser import TemplateParser
except ImportError:
    TemplateParser = None  # type: ignore

try:
    from core.docx_formatter import DocxFormatter
except ImportError:
    DocxFormatter = None  # type: ignore


__all__ = [
    "OutlineNode",
    "Outline",
    "Chapter",
    "Reference",
    "StyleDef",
    "TemplateStyles",
    "Thesis",
    "GenerationConfig",
    "OutlineGenerator",
    "ChapterGenerator",
    "ReferenceFetcher",
    "TemplateParser",
    "DocxFormatter",
]
