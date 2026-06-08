"""
测试文本处理工具 (test_text_utils.py)

覆盖：
- count_chinese_chars() — 中文字符计数
- count_english_words() — 英文单词计数
- estimate_word_count() — 混合字数估算
- parse_markdown_headings() — Markdown 标题解析
- split_chapters() — 章节拆分
- extract_keywords_from_text() — 关键词提取
- strip_markdown_formatting() — Markdown 格式去除
- truncate_text() — 文本截断
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


class TestCountChineseChars(unittest.TestCase):
    """测试中文字符统计"""

    def test_pure_chinese(self):
        """测试纯中文"""
        self.assertEqual(count_chinese_chars("你好世界"), 4)

    def test_pure_english(self):
        """测试纯英文返回 0"""
        self.assertEqual(count_chinese_chars("Hello World"), 0)

    def test_mixed_text(self):
        """测试中英混合"""
        self.assertEqual(count_chinese_chars("Hello 世界 123"), 2)

    def test_empty_string(self):
        """测试空字符串"""
        self.assertEqual(count_chinese_chars(""), 0)

    def test_punctuation_not_counted(self):
        """测试标点不计入"""
        self.assertEqual(count_chinese_chars("你好，世界！"), 4)

    def test_long_text(self):
        """测试长文本"""
        text = "这是一段比较长的中文文本，用于测试中文字符的统计功能是否正常工作。"
        result = count_chinese_chars(text)
        self.assertGreater(result, 20)


class TestCountEnglishWords(unittest.TestCase):
    """测试英文单词统计"""

    def test_simple_words(self):
        """测试简单英文"""
        self.assertEqual(count_english_words("hello world"), 2)

    def test_pure_chinese(self):
        """测试纯中文返回 0"""
        self.assertEqual(count_english_words("你好世界"), 0)

    def test_mixed(self):
        """测试中英混合"""
        self.assertEqual(count_english_words("hello 世界 world"), 2)

    def test_empty(self):
        """测试空字符串"""
        self.assertEqual(count_english_words(""), 0)

    def test_numbers_not_counted(self):
        """测试数字不单独计入"""
        self.assertEqual(count_english_words("hello123 world456"), 2)


class TestEstimateWordCount(unittest.TestCase):
    """测试混合字数估算"""

    def test_pure_chinese(self):
        """测试纯中文估算"""
        self.assertEqual(estimate_word_count("你好世界"), 4)

    def test_pure_english(self):
        """测试纯英文估算"""
        self.assertEqual(estimate_word_count("hello world test"), 3)

    def test_mixed(self):
        """测试中英混合估算"""
        result = estimate_word_count("hello 世界 world")
        self.assertEqual(result, 4)  # 2 英文 + 2 中文

    def test_empty(self):
        """测试空文本"""
        self.assertEqual(estimate_word_count(""), 0)

    def test_with_markdown(self):
        """测试含 Markdown 标记的文本"""
        text = "## 标题\n这是**加粗**内容"
        result = estimate_word_count(text)
        # ## 不是中英文, 标题(2) + 这是(2) + 加粗(2) + 内容(2) = 8
        self.assertGreater(result, 4)


class TestParseMarkdownHeadings(unittest.TestCase):
    """测试 Markdown 标题解析"""

    def test_single_h1(self):
        """测试单级标题"""
        headings = parse_markdown_headings("# 标题1")
        self.assertEqual(len(headings), 1)
        self.assertEqual(headings[0]["level"], 1)
        self.assertEqual(headings[0]["title"], "标题1")
        self.assertEqual(headings[0]["line_number"], 1)

    def test_multiple_levels(self):
        """测试多级标题"""
        md = """# 一级
## 二级
### 三级
#### 四级"""
        headings = parse_markdown_headings(md)
        self.assertEqual(len(headings), 4)
        self.assertEqual(headings[0]["level"], 1)
        self.assertEqual(headings[1]["level"], 2)
        self.assertEqual(headings[2]["level"], 3)
        self.assertEqual(headings[3]["level"], 4)

    def test_no_headings(self):
        """测试无标题文本"""
        headings = parse_markdown_headings("这是一段普通文本")
        self.assertEqual(headings, [])

    def test_empty(self):
        """测试空文本"""
        headings = parse_markdown_headings("")
        self.assertEqual(headings, [])

    def test_line_numbers(self):
        """测试行号正确性"""
        md = "普通文本\n# 标题\n内容"
        headings = parse_markdown_headings(md)
        self.assertEqual(headings[0]["line_number"], 2)

    def test_trim_titles(self):
        """测试标题去除首尾空格"""
        headings = parse_markdown_headings("#   带空格标题   ")
        self.assertEqual(headings[0]["title"], "带空格标题")

    def test_not_heading_like_text(self):
        """测试类似标题但不是标题的文本"""
        headings = parse_markdown_headings("这不是#标题")
        self.assertEqual(headings, [])


class TestSplitChapters(unittest.TestCase):
    """测试章节拆分"""

    def test_two_chapters(self):
        """测试两个章节拆分"""
        md = """## 第一章
内容一

## 第二章
内容二"""
        chapters = split_chapters(md)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0][0], "第一章")
        self.assertIn("内容一", chapters[0][1])
        self.assertEqual(chapters[1][0], "第二章")
        self.assertIn("内容二", chapters[1][1])

    def test_single_chapter(self):
        """测试单章"""
        md = """## 第一章
内容"""
        chapters = split_chapters(md)
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0][0], "第一章")

    def test_no_chapters(self):
        """测试无章标题"""
        md = "这是一段普通文本"
        chapters = split_chapters(md)
        self.assertEqual(chapters, [])

    def test_empty(self):
        """测试空文本"""
        self.assertEqual(split_chapters(""), [])

    def test_sub_heading_not_split(self):
        """测试子标题不拆分"""
        md = """## 第一章
### 1.1 节
内容
## 第二章"""
        chapters = split_chapters(md)
        self.assertEqual(len(chapters), 2)

    def test_preamble_ignored(self):
        """测试章前文本被忽略"""
        md = """前言内容
## 第一章
内容"""
        chapters = split_chapters(md)
        self.assertEqual(len(chapters), 1)

    def test_trim_content(self):
        """测试内容首尾空白去除"""
        md = """## 第一章

内容行


## 第二章
内容"""
        chapters = split_chapters(md)
        self.assertEqual(chapters[0][1], "内容行")


class TestExtractKeywords(unittest.TestCase):
    """测试关键词提取"""

    def test_basic_extraction(self):
        """测试基本关键词提取"""
        text = "深度学习是一种人工智能技术，深度学习在图像识别中应用广泛"
        keywords = extract_keywords_from_text(text, top_n=3)
        self.assertIsInstance(keywords, list)
        self.assertLessEqual(len(keywords), 3)

    def test_stopwords_filtered(self):
        """测试停用词过滤"""
        text = "本文研究了深度学习技术，通过实验进行了验证"
        keywords = extract_keywords_from_text(text, top_n=5)
        # "本文"、"进行"、"通过" 等应为停用词被过滤
        self.assertNotIn("本文", keywords)
        self.assertNotIn("进行", keywords)
        self.assertNotIn("通过", keywords)

    def test_empty_text(self):
        """测试空文本"""
        keywords = extract_keywords_from_text("")
        self.assertEqual(keywords, [])

    def test_short_text(self):
        """测试短文本（2字及以上会被提取）"""
        keywords = extract_keywords_from_text("测试")
        # "测试" 是 2 字且非停用词，应被提取
        self.assertEqual(keywords, ["测试"])

    def test_min_length_filter(self):
        """测试最短短语过滤"""
        text = "A B C 深度学习 人工智能"
        keywords = extract_keywords_from_text(text, top_n=5)
        for kw in keywords:
            self.assertGreaterEqual(len(kw), 2)


class TestStripMarkdownFormatting(unittest.TestCase):
    """测试 Markdown 格式去除"""

    def test_strip_bold(self):
        """测试去除加粗"""
        result = strip_markdown_formatting("这是**加粗**文本")
        self.assertEqual(result, "这是加粗文本")

    def test_strip_italic(self):
        """测试去除斜体"""
        result = strip_markdown_formatting("这是*斜体*文本")
        self.assertEqual(result, "这是斜体文本")

    def test_strip_code(self):
        """测试去除行内代码"""
        result = strip_markdown_formatting("这是`代码`文本")
        self.assertEqual(result, "这是代码文本")

    def test_strip_links(self):
        """测试去除链接"""
        result = strip_markdown_formatting("这是[链接](http://example.com)")
        self.assertEqual(result, "这是链接")

    def test_strip_images(self):
        """测试去除图片"""
        result = strip_markdown_formatting("这是![图片](img.png)文本")
        self.assertEqual(result, "这是文本")

    def test_strip_headings(self):
        """测试去除标题标记"""
        result = strip_markdown_formatting("## 标题内容")
        self.assertEqual(result, "标题内容")

    def test_strip_quotes(self):
        """测试去除引用标记"""
        result = strip_markdown_formatting("> 引用内容")
        self.assertEqual(result, "引用内容")

    def test_strip_lists(self):
        """测试去除列表标记"""
        result = strip_markdown_formatting("- 列表项1\n* 列表项2\n1. 列表项3")
        self.assertNotIn("- ", result)
        self.assertNotIn("* ", result)
        self.assertNotIn("1. ", result)

    def test_strip_horizontal_rules(self):
        """测试去除水平线"""
        result = strip_markdown_formatting("---\n内容\n***")
        self.assertNotIn("---", result)
        self.assertNotIn("***", result)

    def test_combined_formatting(self):
        """测试复合格式"""
        text = "## **标题** [链接](url) `代码`"
        result = strip_markdown_formatting(text)
        self.assertEqual(result, "标题 链接 代码")

    def test_empty(self):
        """测试空文本"""
        self.assertEqual(strip_markdown_formatting(""), "")


class TestTruncateText(unittest.TestCase):
    """测试文本截断"""

    def test_no_truncation(self):
        """测试不需要截断"""
        result = truncate_text("短文本", 10)
        self.assertEqual(result, "短文本")

    def test_truncation(self):
        """测试需要截断"""
        result = truncate_text("这是一段很长的文本需要被截断", 10)
        self.assertEqual(len(result), 10)
        self.assertTrue(result.endswith("..."))

    def test_exact_length(self):
        """测试恰好等于限制长度"""
        text = "12345"
        result = truncate_text(text, 5)
        self.assertEqual(result, "12345")

    def test_custom_ellipsis(self):
        """测试自定义省略号"""
        text = "这是一段很长的文本"
        result = truncate_text(text, 8, ellipsis="…")
        self.assertEqual(len(result), 8)
        self.assertTrue(result.endswith("…"))

    def test_very_short_limit(self):
        """测试极短限制"""
        text = "很长的文本"
        result = truncate_text(text, 5)
        self.assertLessEqual(len(result), 5)

    def test_empty(self):
        """测试空文本"""
        result = truncate_text("", 10)
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
