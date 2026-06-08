"""utils - 工具函数模块

包含文件管理、文本处理、水印注入等工具函数。
"""

from utils.file_utils import (
    ensure_dir,
    get_output_dir,
    get_template_dir,
    generate_output_filename,
    save_uploaded_file,
    cleanup_temp_files,
    get_file_size_mb,
)

from utils.text_utils import (
    count_chinese_chars,
    count_english_words,
    estimate_word_count,
    parse_markdown_headings,
    split_chapters,
    extract_keywords_from_text,
    strip_markdown_formatting,
    truncate_text,
)

from utils.watermark import (
    add_watermark_and_disclaimer,
    inject_ethical_header,
    WATERMARK_TEXT,
    DISCLAIMER_TITLE,
    DISCLAIMER_BODY,
)

__all__ = [
    "ensure_dir",
    "get_output_dir",
    "get_template_dir",
    "generate_output_filename",
    "save_uploaded_file",
    "cleanup_temp_files",
    "get_file_size_mb",
    "count_chinese_chars",
    "count_english_words",
    "estimate_word_count",
    "parse_markdown_headings",
    "split_chapters",
    "extract_keywords_from_text",
    "strip_markdown_formatting",
    "truncate_text",
    "add_watermark_and_disclaimer",
    "inject_ethical_header",
    "WATERMARK_TEXT",
    "DISCLAIMER_TITLE",
    "DISCLAIMER_BODY",
]
