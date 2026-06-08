"""
核心数据模型定义

本模块定义论文生成系统中所有核心数据类，包括：
- Thesis: 论文总状态（Gr State 持有）
- Outline / OutlineNode: 大纲树结构
- Chapter: 单章内容 + 状态机
- Reference: 参考文献条目
- TemplateStyles / StyleDef: 模板样式信息
- GenerationConfig: 全局生成配置

命名规范：类名 PascalCase，字段 snake_case
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Iterator, Any
from collections import deque


# ══════════════════════════════════════════════════════════════
# 大纲结构
# ══════════════════════════════════════════════════════════════

@dataclass
class OutlineNode:
    """大纲节点（树形结构）

    每节点代表论文大纲中的一级标题（章/节/子节）。
    level: 1=章, 2=节, 3=子节
    """
    id: str                                           # 唯一标识，如 "ch1", "ch1_sec1"
    title: str                                        # 节点标题
    level: int                                        # 层级深度（1/2/3）
    children: List['OutlineNode'] = field(default_factory=list)
    content: Optional[str] = None                     # 该节点的摘要/描述（可选）

    def is_leaf(self) -> bool:
        """判断是否为叶子节点（无子节点）"""
        return len(self.children) == 0

    def is_chapter(self) -> bool:
        """判断是否为章级节点"""
        return self.level == 1


@dataclass
class Outline:
    """论文大纲

    以树形结构存储整篇论文的大纲，root 为逻辑根节点，
    其 children 为各章。
    """
    topic: str                                        # 论文主题
    keywords: List[str]                                # 关键词列表
    discipline: str                                   # 学科方向
    root: OutlineNode                                 # 根节点，children 为章列表

    def flat_list(self) -> List[OutlineNode]:
        """BFS 展开大纲为扁平列表

        Returns:
            List[OutlineNode]: 按 BFS 顺序排列的所有节点
        """
        result: List[OutlineNode] = []
        queue: deque[OutlineNode] = deque([self.root])
        while queue:
            node = queue.popleft()
            result.append(node)
            queue.extend(node.children)
        return result

    def get_chapters(self) -> List[OutlineNode]:
        """获取所有章级节点（level==1）

        Returns:
            List[OutlineNode]: 章节点列表
        """
        return [child for child in self.root.children if child.level == 1]

    def get_node_by_id(self, node_id: str) -> Optional[OutlineNode]:
        """根据 id 查找节点

        Args:
            node_id: 节点唯一标识

        Returns:
            Optional[OutlineNode]: 找到的节点，或 None
        """
        for node in self.flat_list():
            if node.id == node_id:
                return node
        return None

    def to_markdown(self) -> str:
        """将大纲树渲染为 Markdown 格式文本

        适用于在 Gradio 中展示和用户编辑。

        Returns:
            str: Markdown 格式的大纲文本
        """
        lines: List[str] = [
            f"# 论文大纲：{self.topic}",
            f"",
            f"**关键词**：{'、'.join(self.keywords)}",
            f"**学科方向**：{self.discipline}",
            f"",
            "---",
            "",
        ]

        def _render_node(node: OutlineNode, depth: int = 0) -> None:
            """递归渲染节点"""
            if node.level >= 1:  # 跳过 root（level=0）
                prefix = "#" * (node.level + 1)   # level1→##，level2→###
                lines.append(f"{prefix} {node.title}")
                if node.content:
                    lines.append(f"")
                    lines.append(f"> {node.content}")
                lines.append(f"")

            for child in node.children:
                _render_node(child, depth + 1)

        for chapter_node in self.root.children:
            _render_node(chapter_node)

        return "\n".join(lines)

    def from_markdown(self, md_text: str) -> 'Outline':
        """从 Markdown 文本解析并更新大纲树

        注意：此方法仅更新节点标题和内容，不改变树结构。
        如需重建树结构，应调用 OutlineGenerator.regenerate_with_feedback()。

        Args:
            md_text: 用户编辑后的 Markdown 大纲文本

        Returns:
            Outline: self（链式调用）
        """
        import re

        current_node: Optional[OutlineNode] = None
        flat_nodes = self.flat_list()
        # 跳过 root 节点
        content_nodes = [n for n in flat_nodes if n.level >= 1]
        matched_indices: set = set()

        lines = md_text.split("\n")
        for line in lines:
            stripped = line.strip()

            # 匹配标题行
            heading_match = re.match(r'^(#{2,4})\s+(.+)$', stripped)
            if heading_match:
                level = len(heading_match.group(1)) - 1  # ## → level1, ### → level2
                title = heading_match.group(2).strip()
                # 每次从开头搜索，避免 node_index 递增跳过节点
                found = False
                for j in range(len(content_nodes)):
                    if j not in matched_indices and content_nodes[j].level == level:
                        content_nodes[j].title = title
                        current_node = content_nodes[j]
                        matched_indices.add(j)
                        found = True
                        break
                if not found:
                    continue
                continue

            # 匹配引用/描述行
            desc_match = re.match(r'^>\s*(.+)$', stripped)
            if desc_match and current_node:
                current_node.content = desc_match.group(1).strip()

        return self

    def __iter__(self) -> Iterator[OutlineNode]:
        """迭代所有节点（BFS）"""
        yield from self.flat_list()


# ══════════════════════════════════════════════════════════════
# 章节状态
# ══════════════════════════════════════════════════════════════

@dataclass
class Chapter:
    """单章内容

    状态机：pending → generating → done → edited
    - pending: 等待生成
    - generating: 正在生成
    - done: 生成完成
    - edited: 用户已编辑
    """
    node: OutlineNode                          # 对应的大纲节点
    content_markdown: str = ""                 # 章节正文（Markdown 格式）
    status: str = "pending"                    # pending | generating | done | edited
    word_count: int = 0                        # 字数统计
    generated_at: Optional[str] = None         # 生成时间戳
    citations: List[str] = field(default_factory=list)  # 本章引用的 ref.key 列表
    tables: List[Dict] = field(default_factory=list)    # 本章的三线表数据

    def can_regenerate(self) -> bool:
        """是否允许重新生成"""
        return self.status in ("done", "edited")

    def mark_done(self) -> None:
        """标记为已完成"""
        self.status = "done"

    def mark_edited(self) -> None:
        """标记为已编辑"""
        self.status = "edited"

    def mark_generating(self) -> None:
        """标记为生成中"""
        self.status = "generating"


# ══════════════════════════════════════════════════════════════
# 参考文献
# ══════════════════════════════════════════════════════════════

@dataclass
class Reference:
    """单条参考文献

    包含标准 BibTeX 字段 + 格式化的引用文本。
    """
    key: str                                      # 引用键，如 "Smith2024"
    title: str                                    # 文献标题
    authors: List[str] = field(default_factory=list)
    year: int = 2024
    venue: str = ""                               # 期刊/会议名
    doi: Optional[str] = None
    url: Optional[str] = None
    citation_text: str = ""                       # 格式化后的 GB7714 引用文本
    cache_key: str = ""                           # 缓存键，用于 API 去重
    abstract: str = ""                            # 文献摘要

    def to_gb7714(self) -> str:
        """生成 GB/T 7714 格式的引用文本

        Returns:
            str: 格式化后的参考文献条目
        """
        if self.citation_text:
            return self.citation_text

        # 自动构建 GB7714 格式
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += ", 等"

        parts = [f"{authors_str}."]
        parts.append(f" {self.title}[J]." if self.venue else f" {self.title}[EB/OL].")
        if self.venue:
            parts.append(f" {self.venue},")
        parts.append(f" {self.year}.")
        if self.doi:
            parts.append(f" DOI: {self.doi}.")
        if self.url and not self.doi:
            parts.append(f" {self.url}.")

        return "".join(parts)

    def to_bibtex(self) -> str:
        """生成 BibTeX 格式

        Returns:
            str: BibTeX 条目
        """
        entry_type = "article" if self.venue else "misc"
        lines = [f"@{entry_type}{{{self.key},"]
        lines.append(f"  title = {{{self.title}}},")
        if self.authors:
            lines.append(f"  author = {{{' and '.join(self.authors)}}},")
        lines.append(f"  year = {{{self.year}}},")
        if self.venue:
            lines.append(f"  journal = {{{self.venue}}},")
        if self.doi:
            lines.append(f"  doi = {{{self.doi}}},")
        if self.url:
            lines.append(f"  url = {{{self.url}}},")
        lines.append("}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 模板样式
# ══════════════════════════════════════════════════════════════

@dataclass
class StyleDef:
    """单个样式定义

    描述字体、大小、加粗、对齐等属性。
    alignment: 0=左对齐, 1=居中, 2=右对齐
    """
    name: str = "正文"
    font_name: str = "宋体"
    font_size: int = 12
    bold: bool = False
    alignment: int = 0


@dataclass
class TemplateStyles:
    """从模板 .docx 提取的样式集合

    包含页边距、各级标题样式、正文样式、页眉页脚信息。
    """
    page_margins: Dict = field(default_factory=lambda: {
        "top": 25.4,    # mm，默认 2.54cm
        "bottom": 25.4,
        "left": 31.7,   # 装订线侧略宽
        "right": 25.4,
    })
    heading_styles: Dict[int, StyleDef] = field(default_factory=lambda: {
        1: StyleDef(name="标题1", font_name="黑体", font_size=16, bold=True, alignment=1),
        2: StyleDef(name="标题2", font_name="黑体", font_size=14, bold=True, alignment=0),
        3: StyleDef(name="标题3", font_name="黑体", font_size=12, bold=True, alignment=0),
    })
    body_style: Optional[StyleDef] = field(default_factory=lambda: StyleDef(
        name="正文", font_name="宋体", font_size=12, bold=False, alignment=0
    ))
    header_footer: Optional[Dict] = None
    template_name: str = "默认模板"           # 模板名称（P2 新增）
    template_description: str = ""            # 模板描述（P2 新增）


# ══════════════════════════════════════════════════════════════
# 论文总状态
# ══════════════════════════════════════════════════════════════

@dataclass
class Thesis:
    """论文总状态对象

    由 Gradio gr.State() 持有，贯穿整个生成流程。
    """
    topic: str = ""                                   # 论文主题
    keywords: List[str] = field(default_factory=list) # 关键词
    target_word_count: int = 15000                    # 目标字数
    outline: Optional[Outline] = None                 # 论文大纲
    chapters: List[Chapter] = field(default_factory=list)  # 章节列表
    references: List[Reference] = field(default_factory=list)  # 参考文献
    template_styles: Optional[TemplateStyles] = None  # 模板样式
    template_path: str = ""                           # 上传的模板路径
    history_id: str = ""                              # SQLite 历史记录 ID
    user_data: Dict[str, Any] = field(default_factory=dict)  # 用户上传的结构化数据
    task_id: Optional[str] = None                     # 异步任务 ID

    def get_total_words(self) -> int:
        """计算已生成章节的总字数

        Returns:
            int: 总字数
        """
        return sum(ch.word_count for ch in self.chapters)

    def get_progress(self) -> float:
        """计算生成进度（0.0 ~ 1.0）

        基于已完成章节数占总章节数的比例。

        Returns:
            float: 进度百分比
        """
        if not self.chapters:
            return 0.0
        done_count = sum(1 for ch in self.chapters if ch.status in ("done", "edited"))
        return done_count / len(self.chapters)

    def get_chapter_by_index(self, index: int) -> Optional[Chapter]:
        """按索引获取章节

        Args:
            index: 章节索引（从 0 开始）

        Returns:
            Optional[Chapter]: 章节对象或 None
        """
        if 0 <= index < len(self.chapters):
            return self.chapters[index]
        return None

    def to_summary(self) -> str:
        """生成论文信息摘要文本

        Returns:
            str: 格式化的摘要信息
        """
        lines = [
            f"## 论文信息摘要",
            f"",
            f"- **主题**：{self.topic}",
            f"- **关键词**：{'、'.join(self.keywords)}",
            f"- **目标字数**：{self.target_word_count:,} 字",
            f"- **已完成字数**：{self.get_total_words():,} 字",
            f"- **章节数**：{len(self.chapters)} 章",
            f"- **参考文献**：{len(self.references)} 篇",
            f"- **模板文件**：{self.template_path or '默认模板'}",
        ]
        if self.outline:
            lines.append(f"- **大纲层级**：{len(self.outline.flat_list())} 个节点")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 全局生成配置
# ══════════════════════════════════════════════════════════════

@dataclass
class GenerationConfig:
    """论文生成全局配置数据类

    所有字段均提供合理的默认值，用户可通过 UI 覆盖部分字段。
    此数据类在 config.py 中也有使用，定义在此以便 core 模块内引用。
    """
    # LLM 配置
    llm_provider: str = "deepseek"                    # "deepseek" | "openai"
    llm_model: str = "deepseek-chat"                   # 模型名称
    llm_api_key: str = ""                              # API Key
    llm_api_base: str = "https://api.deepseek.com"     # API Base URL

    # 生成参数
    target_word_count: int = 15000                     # 目标总字数
    discipline: str = "软件工程"                        # 学科方向
    temperature: float = 0.7                           # LLM 温度
    max_tokens_per_chapter: int = 4096                 # 每章最大 token

    # 异步任务配置（P1 新增）
    async_mode: bool = False                            # 是否启用异步模式
    redis_url: str = ""                                 # Redis 连接 URL
    celery_broker_url: str = ""                         # Celery broker URL
    semantic_scholar_api_key: str = ""                  # Semantic Scholar API Key


# ══════════════════════════════════════════════════════════════
# P1 新增：三线表 & 历史记录
# ══════════════════════════════════════════════════════════════

@dataclass
class ThreeLineTable:
    """三线表数据

    符合学术规范的表格：顶线粗、栏目线细、底线粗，无左右竖线。
    """
    table_id: str                               # 表序，如 "表3-1"
    caption: str                                # 表题
    headers: List[str]                          # 表头列名
    rows: List[List[str]]                       # 数据行
    source: str = "LLM生成"                     # 数据来源


@dataclass
class HistoryRecord:
    """生成历史记录

    P2 阶段用 SQLite 持久化，当前内存持有。
    """
    id: str                                     # 唯一 ID
    topic: str                                  # 论文主题
    keywords: List[str] = field(default_factory=list)
    word_count: int = 0                         # 实际字数
    chapter_count: int = 0                      # 章节数
    ref_count: int = 0                          # 参考文献数
    output_path: str = ""                       # 输出文件路径
    created_at: str = ""                        # 创建时间
