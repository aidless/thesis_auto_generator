"""
文本处理工具

提供字数统计、Markdown 解析、章节拆分等文本处理功能。
"""

import re
from typing import List, Dict, Optional, Tuple


def count_chinese_chars(text: str) -> int:
    """统计文本中中文字符的数量

    Args:
        text: 输入文本

    Returns:
        int: 中文字符数
    """
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def count_english_words(text: str) -> int:
    """统计文本中英文单词的数量

    Args:
        text: 输入文本

    Returns:
        int: 英文单词数
    """
    return len(re.findall(r'[a-zA-Z]+', text))


def estimate_word_count(text: str) -> int:
    """估算文本总字数

    中文字符 1 个 = 1 字，英文单词 1 个 ≈ 1 字。
    标点、空格不计入。

    Args:
        text: 输入文本

    Returns:
        int: 估算字数
    """
    chinese = count_chinese_chars(text)
    english = count_english_words(text)
    return chinese + english


def parse_markdown_headings(md_text: str) -> List[Dict]:
    """解析 Markdown 文本中的标题结构

    Args:
        md_text: Markdown 格式文本

    Returns:
        List[Dict]: 标题列表，每项包含 level, title, line_number
    """
    headings: List[Dict] = []
    for i, line in enumerate(md_text.split("\n")):
        match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
        if match:
            headings.append({
                "level": len(match.group(1)),
                "title": match.group(2).strip(),
                "line_number": i + 1,
            })
    return headings


def split_chapters(md_text: str) -> List[Tuple[str, str]]:
    """按 ##（二级标题）拆分为章节列表

    Args:
        md_text: Markdown 格式文本

    Returns:
        List[Tuple[str, str]]: [(章节标题, 章节内容), ...]
    """
    chapters: List[Tuple[str, str]] = []
    lines = md_text.split("\n")
    current_title = ""
    current_content: List[str] = []

    for line in lines:
        # 匹配 ## 开头（章级标题），但不匹配 ### 等更深层级
        if re.match(r'^##\s+', line) and not re.match(r'^###+\s+', line):
            # 保存上一章（允许空内容章节）
            if current_title:
                chapters.append((current_title, "\n".join(current_content).strip()))

            current_title = re.sub(r'^##\s+', '', line).strip()
            current_content = []
        else:
            current_content.append(line)

    # 保存最后一章（允许空内容章节）
    if current_title:
        chapters.append((current_title, "\n".join(current_content).strip()))

    return chapters


def extract_keywords_from_text(text: str, top_n: int = 10) -> List[str]:
    """从文本中提取高频关键词（简单实现）

    实际生产环境可使用 jieba 分词，此处提供基于频率的轻量实现。

    Args:
        text: 输入文本
        top_n: 返回前 N 个关键词

    Returns:
        List[str]: 关键词列表
    """
    # 提取中文字符序列作为候选词（简化实现）
    chinese_phrases = re.findall(r'[\u4e00-\u9fff]{2,}', text)
    from collections import Counter
    counter = Counter(chinese_phrases)

    # 过滤停用词
    stopwords = {
        '本文', '研究', '进行', '通过', '一个', '可以', '使用', '基于',
        '以及', '其中', '因此', '所以', '但是', '而且', '或者', '没有',
        '这一', '这一些', '那种', '这个', '一种', '他们', '我们', '它们',
        '主要', '相关', '不同', '需要', '已经', '目前', '问题', '方面',
        '例如', '包括', '根据', '对于', '关于', '具有', '这些', '一些',
    }

    keywords: List[str] = []
    for phrase, _ in counter.most_common(top_n * 3):
        if phrase not in stopwords and len(phrase) >= 2:
            keywords.append(phrase)
        if len(keywords) >= top_n:
            break

    return keywords


def strip_markdown_formatting(md_text: str) -> str:
    """去除 Markdown 格式标记，提取纯文本

    用于字数统计和预览。

    Args:
        md_text: Markdown 文本

    Returns:
        str: 纯文本
    """
    text = md_text
    # 去除标题标记
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # 去除加粗斜体
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # 去除行内代码
    text = re.sub(r'`(.+?)`', r'\1', text)
    # 去除图片（必须在链接之前，避免 ![...](...) 被链接正则部分匹配）
    text = re.sub(r'!\[.*?\]\(.+?\)', '', text)
    # 去除链接
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    # 去除引用标记
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    # 去除列表标记
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    # 去除水平线
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    return text.strip()


def truncate_text(text: str, max_chars: int, ellipsis: str = "...") -> str:
    """截断文本到指定长度

    Args:
        text: 原始文本
        max_chars: 最大字符数
        ellipsis: 省略号字符串

    Returns:
        str: 截断后的文本
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(ellipsis)] + ellipsis
