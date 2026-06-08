"""
测试核心数据模型 (test_models.py)

覆盖：
- OutlineNode 树构建、is_leaf/is_chapter
- Outline.flat_list() / get_chapters() / get_node_by_id() / to_markdown() / from_markdown()
- Chapter 状态机 (pending→generating→done→edited)
- Reference 字段完整性、to_gb7714()、to_bibtex()
- StyleDef / TemplateStyles 默认值
- Thesis 默认值、get_total_words()、get_progress()、to_summary()
- GenerationConfig 默认值
"""

import sys
import os
import unittest

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


class TestOutlineNode(unittest.TestCase):
    """测试 OutlineNode 数据类"""

    def test_create_basic_node(self):
        """测试创建基础节点"""
        node = OutlineNode(id="ch1", title="第一章 绪论", level=1)
        self.assertEqual(node.id, "ch1")
        self.assertEqual(node.title, "第一章 绪论")
        self.assertEqual(node.level, 1)
        self.assertEqual(node.children, [])
        self.assertIsNone(node.content)

    def test_create_node_with_children(self):
        """测试创建带子节点的节点"""
        child = OutlineNode(id="ch1_sec1", title="1.1 背景", level=2)
        parent = OutlineNode(id="ch1", title="第一章", level=1, children=[child])
        self.assertEqual(len(parent.children), 1)
        self.assertEqual(parent.children[0].id, "ch1_sec1")

    def test_create_node_with_content(self):
        """测试创建带描述的节点"""
        node = OutlineNode(id="ch1", title="第一章", level=1, content="本章介绍背景")
        self.assertEqual(node.content, "本章介绍背景")

    def test_is_leaf_true(self):
        """测试叶子节点判断（无子节点）"""
        node = OutlineNode(id="leaf", title="叶子", level=3)
        self.assertTrue(node.is_leaf())

    def test_is_leaf_false(self):
        """测试非叶子节点判断"""
        child = OutlineNode(id="c1", title="子节点", level=2)
        node = OutlineNode(id="parent", title="父节点", level=1, children=[child])
        self.assertFalse(node.is_leaf())

    def test_is_chapter_true(self):
        """测试章级节点判断"""
        node = OutlineNode(id="ch1", title="第一章", level=1)
        self.assertTrue(node.is_chapter())

    def test_is_chapter_false_for_level2(self):
        """测试 level 2 不是章级"""
        node = OutlineNode(id="sec1", title="节", level=2)
        self.assertFalse(node.is_chapter())

    def test_is_chapter_false_for_level3(self):
        """测试 level 3 不是章级"""
        node = OutlineNode(id="sub1", title="子节", level=3)
        self.assertFalse(node.is_chapter())

    def test_default_factory_children(self):
        """测试 children 默认值为空列表"""
        node = OutlineNode(id="n1", title="test", level=1)
        self.assertIsInstance(node.children, list)
        self.assertEqual(len(node.children), 0)
        # 验证不同实例不共享同一列表
        node2 = OutlineNode(id="n2", title="test2", level=1)
        node.children.append(OutlineNode(id="n3", title="test3", level=2))
        self.assertEqual(len(node2.children), 0)


class TestOutline(unittest.TestCase):
    """测试 Outline 大纲类"""

    def setUp(self):
        """构建测试用大纲树"""
        self.root = OutlineNode(id="root", title="论文主题", level=0)
        ch1 = OutlineNode(id="ch1", title="第一章 绪论", level=1)
        ch1_sec1 = OutlineNode(id="ch1_sec1", title="1.1 背景", level=2)
        ch1_sec2 = OutlineNode(id="ch1_sec2", title="1.2 方法", level=2)
        ch1.children = [ch1_sec1, ch1_sec2]

        ch2 = OutlineNode(id="ch2", title="第二章 相关工作", level=1)
        ch2_sec1 = OutlineNode(id="ch2_sec1", title="2.1 综述", level=2)
        ch2.children = [ch2_sec1]

        self.root.children = [ch1, ch2]
        self.outline = Outline(
            topic="测试论文",
            keywords=["测试", "论文"],
            discipline="软件工程",
            root=self.root,
        )

    def test_create_outline(self):
        """测试创建 Outline 对象"""
        self.assertEqual(self.outline.topic, "测试论文")
        self.assertEqual(self.outline.keywords, ["测试", "论文"])
        self.assertEqual(self.outline.discipline, "软件工程")
        self.assertEqual(self.outline.root.id, "root")

    def test_flat_list(self):
        """测试 BFS 扁平化"""
        flat = self.outline.flat_list()
        ids = [n.id for n in flat]
        # BFS: root, ch1, ch2, ch1_sec1, ch1_sec2, ch2_sec1
        self.assertEqual(ids, ["root", "ch1", "ch2", "ch1_sec1", "ch1_sec2", "ch2_sec1"])
        self.assertEqual(len(flat), 6)

    def test_flat_list_empty(self):
        """测试空大纲的扁平化"""
        root = OutlineNode(id="root", title="空", level=0)
        outline = Outline(topic="空", keywords=[], discipline="", root=root)
        flat = outline.flat_list()
        self.assertEqual(len(flat), 1)
        self.assertEqual(flat[0].id, "root")

    def test_get_chapters(self):
        """测试获取所有章级节点"""
        chapters = self.outline.get_chapters()
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0].id, "ch1")
        self.assertEqual(chapters[1].id, "ch2")

    def test_get_chapters_empty(self):
        """测试无章节时返回空列表"""
        root = OutlineNode(id="root", title="空", level=0)
        outline = Outline(topic="空", keywords=[], discipline="", root=root)
        chapters = outline.get_chapters()
        self.assertEqual(chapters, [])

    def test_get_node_by_id_exists(self):
        """测试按 ID 查找存在的节点"""
        node = self.outline.get_node_by_id("ch2_sec1")
        self.assertIsNotNone(node)
        self.assertEqual(node.title, "2.1 综述")

    def test_get_node_by_id_not_exists(self):
        """测试按 ID 查找不存在的节点"""
        node = self.outline.get_node_by_id("nonexistent")
        self.assertIsNone(node)

    def test_get_node_by_id_root(self):
        """测试查找根节点"""
        node = self.outline.get_node_by_id("root")
        self.assertIsNotNone(node)
        self.assertEqual(node.level, 0)

    def test_to_markdown(self):
        """测试大纲渲染为 Markdown"""
        md = self.outline.to_markdown()
        self.assertIn("# 论文大纲：测试论文", md)
        self.assertIn("**关键词**：测试、论文", md)
        self.assertIn("**学科方向**：软件工程", md)
        self.assertIn("## 第一章 绪论", md)
        self.assertIn("### 1.1 背景", md)
        self.assertIn("## 第二章 相关工作", md)

    def test_to_markdown_no_content(self):
        """测试无 content 节点的 Markdown（不输出空描述）"""
        md = self.outline.to_markdown()
        # ch1 has no content, so no ">" lines for it
        self.assertNotIn(">", md)  # none of our test nodes have content

    def test_to_markdown_with_content(self):
        """测试带描述的节点渲染"""
        root = OutlineNode(id="root", title="T", level=0)
        ch = OutlineNode(id="ch1", title="第一章", level=1, content="本章介绍")
        root.children = [ch]
        outline = Outline(topic="T", keywords=["K"], discipline="D", root=root)
        md = outline.to_markdown()
        self.assertIn("> 本章介绍", md)

    def test_from_markdown_updates_titles(self):
        """测试 from_markdown 更新标题"""
        md = "## 新标题一\n### 新节1\n## 新标题二\n"
        self.outline.from_markdown(md)
        chapters = self.outline.get_chapters()
        self.assertEqual(chapters[0].title, "新标题一")
        self.assertEqual(chapters[1].title, "新标题二")

    def test_from_markdown_updates_content(self):
        """测试 from_markdown 更新描述"""
        root = OutlineNode(id="root", title="T", level=0)
        ch = OutlineNode(id="ch1", title="第一章", level=1)
        root.children = [ch]
        outline = Outline(topic="T", keywords=["K"], discipline="D", root=root)
        md = "## 第一章\n> 新描述\n"
        outline.from_markdown(md)
        self.assertEqual(ch.content, "新描述")

    def test_from_markdown_returns_self(self):
        """测试 from_markdown 返回 self 支持链式调用"""
        result = self.outline.from_markdown("## X\n")
        self.assertIs(result, self.outline)

    def test_iter(self):
        """测试迭代器"""
        ids = [n.id for n in self.outline]
        self.assertIn("root", ids)
        self.assertIn("ch1", ids)
        self.assertIn("ch2", ids)

    def test_single_level_outline(self):
        """测试只有章级、无节的简单大纲"""
        root = OutlineNode(id="root", title="T", level=0)
        ch1 = OutlineNode(id="ch1", title="第一章", level=1)
        ch2 = OutlineNode(id="ch2", title="第二章", level=1)
        root.children = [ch1, ch2]
        outline = Outline(topic="T", keywords=["K"], discipline="D", root=root)
        self.assertEqual(len(outline.get_chapters()), 2)
        self.assertEqual(len(outline.flat_list()), 3)


class TestChapter(unittest.TestCase):
    """测试 Chapter 章节类与状态机"""

    def setUp(self):
        self.node = OutlineNode(id="ch1", title="第一章", level=1)
        self.chapter = Chapter(node=self.node)

    def test_default_values(self):
        """测试 Chapter 默认值"""
        self.assertEqual(self.chapter.node.id, "ch1")
        self.assertEqual(self.chapter.content_markdown, "")
        self.assertEqual(self.chapter.status, "pending")
        self.assertEqual(self.chapter.word_count, 0)
        self.assertIsNone(self.chapter.generated_at)

    def test_mark_generating(self):
        """测试标记为生成中"""
        self.chapter.mark_generating()
        self.assertEqual(self.chapter.status, "generating")

    def test_mark_done(self):
        """测试标记为已完成"""
        self.chapter.mark_done()
        self.assertEqual(self.chapter.status, "done")

    def test_mark_edited(self):
        """测试标记为已编辑"""
        self.chapter.mark_edited()
        self.assertEqual(self.chapter.status, "edited")

    def test_state_transition_full_flow(self):
        """测试完整状态流转：pending→generating→done→edited"""
        self.assertEqual(self.chapter.status, "pending")

        self.chapter.mark_generating()
        self.assertEqual(self.chapter.status, "generating")

        self.chapter.mark_done()
        self.assertEqual(self.chapter.status, "done")

        self.chapter.mark_edited()
        self.assertEqual(self.chapter.status, "edited")

    def test_can_regenerate_when_done(self):
        """测试 done 状态允许重新生成"""
        self.chapter.mark_done()
        self.assertTrue(self.chapter.can_regenerate())

    def test_can_regenerate_when_edited(self):
        """测试 edited 状态允许重新生成"""
        self.chapter.mark_edited()
        self.assertTrue(self.chapter.can_regenerate())

    def test_cannot_regenerate_when_pending(self):
        """测试 pending 状态不允许重新生成"""
        self.assertFalse(self.chapter.can_regenerate())

    def test_cannot_regenerate_when_generating(self):
        """测试 generating 状态不允许重新生成"""
        self.chapter.mark_generating()
        self.assertFalse(self.chapter.can_regenerate())

    def test_full_chapter_with_content(self):
        """测试完整章节对象"""
        node = OutlineNode(id="ch2", title="第二章", level=1)
        chapter = Chapter(
            node=node,
            content_markdown="## 第二章\n\n内容...",
            status="done",
            word_count=1500,
            generated_at="2025-01-01T00:00:00",
        )
        self.assertEqual(chapter.word_count, 1500)
        self.assertEqual(chapter.generated_at, "2025-01-01T00:00:00")
        self.assertIn("第二章", chapter.content_markdown)


class TestReference(unittest.TestCase):
    """测试 Reference 参考文献类"""

    def test_default_values(self):
        """测试 Reference 默认值"""
        ref = Reference(key="Test2024", title="Test Title")
        self.assertEqual(ref.key, "Test2024")
        self.assertEqual(ref.title, "Test Title")
        self.assertEqual(ref.authors, [])
        self.assertEqual(ref.year, 2024)
        self.assertEqual(ref.venue, "")
        self.assertIsNone(ref.doi)
        self.assertIsNone(ref.url)
        self.assertEqual(ref.citation_text, "")

    def test_full_reference(self):
        """测试完整参考文献"""
        ref = Reference(
            key="Smith2024",
            title="Deep Learning for NLP",
            authors=["John Smith", "Jane Doe"],
            year=2024,
            venue="Nature",
            doi="10.1234/abc",
            url="https://doi.org/10.1234/abc",
        )
        self.assertEqual(ref.key, "Smith2024")
        self.assertEqual(len(ref.authors), 2)
        self.assertEqual(ref.year, 2024)
        self.assertEqual(ref.venue, "Nature")

    def test_to_gb7714_with_citation_text(self):
        """测试已有 citation_text 时直接返回"""
        ref = Reference(key="X", title="T", citation_text="预生成的引用文本")
        result = ref.to_gb7714()
        self.assertEqual(result, "预生成的引用文本")

    def test_to_gb7714_auto_generate(self):
        """测试自动生成 GB7714 格式"""
        ref = Reference(
            key="Smith2024",
            title="Deep Learning",
            authors=["John Smith"],
            year=2024,
            venue="Nature",
            doi="10.1234/abc",
        )
        result = ref.to_gb7714()
        self.assertIn("Smith.", result)
        self.assertIn("Deep Learning", result)
        self.assertIn("Nature", result)
        self.assertIn("2024", result)
        self.assertIn("10.1234/abc", result)

    def test_to_gb7714_multiple_authors(self):
        """测试多作者 GB7714（超3人截断）"""
        ref = Reference(
            key="Multi2024",
            title="Multi Author Paper",
            authors=["A", "B", "C", "D"],
            year=2024,
            venue="Journal",
        )
        result = ref.to_gb7714()
        self.assertIn("等", result)

    def test_to_gb7714_no_venue(self):
        """测试无 venue 的 GB7714"""
        ref = Reference(
            key="Web2024",
            title="Web Resource",
            authors=["Author"],
            year=2024,
            url="https://example.com",
        )
        result = ref.to_gb7714()
        self.assertIn("[EB/OL]", result)
        self.assertIn("https://example.com", result)

    def test_to_bibtex_article(self):
        """测试 BibTeX 格式（有 venue → article）"""
        ref = Reference(
            key="Smith2024",
            title="Deep Learning",
            authors=["John Smith"],
            year=2024,
            venue="Nature",
            doi="10.1234/abc",
        )
        result = ref.to_bibtex()
        self.assertIn("@article{Smith2024,", result)
        self.assertIn("title = {Deep Learning}", result)
        self.assertIn("author = {John Smith}", result)

    def test_to_bibtex_misc(self):
        """测试 BibTeX 格式（无 venue → misc）"""
        ref = Reference(
            key="Web2024",
            title="Web Resource",
            authors=["Author"],
            year=2024,
            url="https://example.com",
        )
        result = ref.to_bibtex()
        self.assertIn("@misc{Web2024,", result)

    def test_to_bibtex_no_authors(self):
        """测试无作者的 BibTeX"""
        ref = Reference(key="Anon2024", title="Anonymous", year=2024)
        result = ref.to_bibtex()
        self.assertNotIn("author", result)


class TestStyleDef(unittest.TestCase):
    """测试 StyleDef 样式定义"""

    def test_default_values(self):
        """测试 StyleDef 默认值"""
        style = StyleDef()
        self.assertEqual(style.name, "正文")
        self.assertEqual(style.font_name, "宋体")
        self.assertEqual(style.font_size, 12)
        self.assertFalse(style.bold)
        self.assertEqual(style.alignment, 0)

    def test_custom_values(self):
        """测试自定义值"""
        style = StyleDef(
            name="标题1",
            font_name="黑体",
            font_size=16,
            bold=True,
            alignment=1,
        )
        self.assertEqual(style.name, "标题1")
        self.assertEqual(style.font_name, "黑体")
        self.assertEqual(style.font_size, 16)
        self.assertTrue(style.bold)
        self.assertEqual(style.alignment, 1)


class TestTemplateStyles(unittest.TestCase):
    """测试 TemplateStyles 模板样式"""

    def test_default_values(self):
        """测试 TemplateStyles 默认值"""
        ts = TemplateStyles()
        self.assertIsNotNone(ts.page_margins)
        self.assertEqual(ts.page_margins["top"], 25.4)
        self.assertEqual(ts.page_margins["bottom"], 25.4)
        self.assertEqual(ts.page_margins["left"], 31.7)
        self.assertEqual(ts.page_margins["right"], 25.4)
        self.assertEqual(len(ts.heading_styles), 3)
        self.assertIn(1, ts.heading_styles)
        self.assertIn(2, ts.heading_styles)
        self.assertIn(3, ts.heading_styles)
        self.assertIsNotNone(ts.body_style)
        self.assertEqual(ts.body_style.font_name, "宋体")
        self.assertIsNone(ts.header_footer)

    def test_heading_style_level1(self):
        """测试一级标题默认样式"""
        ts = TemplateStyles()
        h1 = ts.heading_styles[1]
        self.assertEqual(h1.font_name, "黑体")
        self.assertEqual(h1.font_size, 16)
        self.assertTrue(h1.bold)
        self.assertEqual(h1.alignment, 1)  # 居中

    def test_heading_style_level2(self):
        """测试二级标题默认样式"""
        ts = TemplateStyles()
        h2 = ts.heading_styles[2]
        self.assertEqual(h2.font_size, 14)
        self.assertEqual(h2.alignment, 0)  # 左对齐

    def test_custom_page_margins(self):
        """测试自定义页边距"""
        ts = TemplateStyles(page_margins={"top": 30, "bottom": 30, "left": 40, "right": 30})
        self.assertEqual(ts.page_margins["top"], 30)
        self.assertEqual(ts.page_margins["left"], 40)

    def test_custom_body_style(self):
        """测试自定义正文样式"""
        custom = StyleDef(name="正文", font_name="仿宋", font_size=14)
        ts = TemplateStyles(body_style=custom)
        self.assertEqual(ts.body_style.font_name, "仿宋")
        self.assertEqual(ts.body_style.font_size, 14)


class TestThesis(unittest.TestCase):
    """测试 Thesis 论文总状态"""

    def setUp(self):
        self.thesis = Thesis(
            topic="测试论文",
            keywords=["AI", "测试"],
            target_word_count=15000,
        )

    def test_default_values(self):
        """测试 Thesis 默认值"""
        thesis = Thesis()
        self.assertEqual(thesis.topic, "")
        self.assertEqual(thesis.keywords, [])
        self.assertEqual(thesis.target_word_count, 15000)
        self.assertIsNone(thesis.outline)
        self.assertEqual(thesis.chapters, [])
        self.assertEqual(thesis.references, [])
        self.assertIsNone(thesis.template_styles)
        self.assertEqual(thesis.template_path, "")

    def test_get_total_words_empty(self):
        """测试空章节总字数"""
        self.assertEqual(self.thesis.get_total_words(), 0)

    def test_get_total_words_with_chapters(self):
        """测试有章节的总字数"""
        node = OutlineNode(id="ch1", title="第一章", level=1)
        ch1 = Chapter(node=node, word_count=1000, status="done")
        ch2 = Chapter(node=OutlineNode(id="ch2", title="第二章", level=1), word_count=2000, status="done")
        self.thesis.chapters = [ch1, ch2]
        self.assertEqual(self.thesis.get_total_words(), 3000)

    def test_get_progress_empty(self):
        """测试空章节进度"""
        self.assertEqual(self.thesis.get_progress(), 0.0)

    def test_get_progress_half(self):
        """测试一半完成进度"""
        node = OutlineNode(id="ch1", title="第一章", level=1)
        ch1 = Chapter(node=node, status="done")
        ch2 = Chapter(node=OutlineNode(id="ch2", title="第二章", level=1), status="pending")
        self.thesis.chapters = [ch1, ch2]
        self.assertEqual(self.thesis.get_progress(), 0.5)

    def test_get_progress_all_done(self):
        """测试全部完成进度"""
        ch1 = Chapter(node=OutlineNode(id="ch1", title="第一章", level=1), status="done")
        ch2 = Chapter(node=OutlineNode(id="ch2", title="第二章", level=1), status="edited")
        self.thesis.chapters = [ch1, ch2]
        self.assertEqual(self.thesis.get_progress(), 1.0)

    def test_get_chapter_by_index_valid(self):
        """测试按有效索引获取章节"""
        node = OutlineNode(id="ch1", title="第一章", level=1)
        ch1 = Chapter(node=node)
        self.thesis.chapters = [ch1]
        result = self.thesis.get_chapter_by_index(0)
        self.assertIsNotNone(result)
        self.assertEqual(result.node.id, "ch1")

    def test_get_chapter_by_index_out_of_range(self):
        """测试按越界索引获取章节"""
        self.assertIsNone(self.thesis.get_chapter_by_index(0))
        self.assertIsNone(self.thesis.get_chapter_by_index(-1))
        self.assertIsNone(self.thesis.get_chapter_by_index(100))

    def test_to_summary(self):
        """测试生成摘要"""
        node = OutlineNode(id="root", title="T", level=0)
        ch1_node = OutlineNode(id="ch1", title="第一章", level=1)
        node.children = [ch1_node]
        outline = Outline(topic="T", keywords=["K"], discipline="D", root=node)
        ch1 = Chapter(node=ch1_node, word_count=1000, status="done")

        thesis = Thesis(
            topic="测试论文",
            keywords=["AI"],
            target_word_count=15000,
            outline=outline,
            chapters=[ch1],
        )

        summary = thesis.to_summary()
        self.assertIn("测试论文", summary)
        self.assertIn("AI", summary)
        self.assertIn("15,000", summary)
        self.assertIn("1,000", summary)

    def test_to_summary_minimal(self):
        """测试最小 Thesis 的摘要"""
        summary = self.thesis.to_summary()
        self.assertIn("测试论文", summary)
        self.assertIn("0 字", summary)


class TestGenerationConfig(unittest.TestCase):
    """测试 GenerationConfig 全局配置"""

    def test_default_values(self):
        """测试默认值"""
        config = GenerationConfig()
        self.assertEqual(config.llm_provider, "deepseek")
        self.assertEqual(config.llm_model, "deepseek-chat")
        self.assertEqual(config.llm_api_key, "")
        self.assertEqual(config.llm_api_base, "https://api.deepseek.com")
        self.assertEqual(config.target_word_count, 15000)
        self.assertEqual(config.discipline, "软件工程")
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.max_tokens_per_chapter, 4096)

    def test_custom_values(self):
        """测试自定义值"""
        config = GenerationConfig(
            llm_provider="openai",
            llm_model="gpt-4o",
            llm_api_key="sk-test",
            llm_api_base="https://api.openai.com/v1",
            target_word_count=20000,
            discipline="计算机科学",
            temperature=0.5,
            max_tokens_per_chapter=8192,
        )
        self.assertEqual(config.llm_provider, "openai")
        self.assertEqual(config.llm_model, "gpt-4o")
        self.assertEqual(config.llm_api_key, "sk-test")
        self.assertEqual(config.target_word_count, 20000)
        self.assertEqual(config.temperature, 0.5)
        self.assertEqual(config.max_tokens_per_chapter, 8192)


if __name__ == "__main__":
    unittest.main()
