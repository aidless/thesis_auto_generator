"""
文献检索器

通过 Semantic Scholar API 和 Crossref API 检索相关学术文献。
支持按关键词搜索，返回格式化的 Reference 对象。

注意：
- 检索失败不阻断主流程，返回空列表 + warning
- 对两个 API 均做超时处理（10 秒）
- 结果按引用数降序排列
"""

import logging
import time
from typing import List, Optional, Dict, Any, Tuple
from collections import OrderedDict

import requests

from core.models import Reference

logger = logging.getLogger(__name__)

# API 配置
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
CROSSREF_API = "https://api.crossref.org/works"
REQUEST_TIMEOUT = 10  # 秒
MAX_RESULTS = 30


class ReferenceFetcher:
    """文献检索器

    通过公开 API 检索学术文献，生成 Reference 对象列表。
    内置 LRU 缓存避免重复 API 请求。

    Attributes:
        timeout: HTTP 请求超时时间（秒）
        max_results: 最大返回结果数
        _cache: LRU 缓存（类级别，所有实例共享）
        _last_request_time: 上次 API 请求时间（限流控制）
    """

    # 类级别 LRU 缓存：容量 200，键格式 "{keyword}:{limit}"
    _cache: OrderedDict = OrderedDict()
    _cache_maxsize: int = 200
    _last_request_time: float = 0.0
    _min_request_interval: float = 3.0  # P4 优化: 3秒间隔避免 Semantic Scholar 429
    _retry_count: int = 0               # 连续限流计数（指数退避）

    def __init__(self, timeout: int = REQUEST_TIMEOUT, max_results: int = MAX_RESULTS):
        """初始化文献检索器

        Args:
            timeout: HTTP 请求超时秒数
            max_results: 单次查询最大结果数
        """
        self.timeout = timeout
        self.max_results = max_results

    def fetch_by_keywords(
        self,
        keywords: List[str],
        limit: int = 30,
        topic: str = "",
    ) -> List[Reference]:
        """根据关键词检索文献

        优先使用 Semantic Scholar，失败则回退到 Crossref。
        P4 优化: 自动过滤低相关性文献。

        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            topic: 论文主题（用于相关性过滤）

        Returns:
            List[Reference]: 文献列表（可能为空）
        """
        if not keywords:
            logger.warning("关键词为空，跳过文献检索")
            return []

        # P4: 关键词优化 — 拆分复合词，去掉通用词
        tech_keywords = self._extract_tech_keywords(keywords, topic)
        query = " ".join(tech_keywords)
        logger.info(f"文献检索: query='{query}' (原始: {keywords})")

        # 尝试 Semantic Scholar
        refs = self._search_semantic_scholar(query, limit * 2)  # 多取一些，后续过滤
        if refs:
            logger.info(f"Semantic Scholar 检索: {len(refs)} 篇")
        else:
            logger.info("Semantic Scholar 无结果，回退 Crossref")
            refs = self._search_crossref(query, limit * 2)

        # P4: 相关性过滤
        if refs and tech_keywords:
            refs = self._filter_relevance(refs, tech_keywords, limit)

        if refs:
            logger.info(f"检索完成: {len(refs)} 篇 (已过滤)")
        else:
            logger.warning(f"两 API 均无结果或全部被过滤: query='{query}'")

        return refs[:limit]

    @staticmethod
    def _extract_tech_keywords(
        keywords: List[str], topic: str = ""
    ) -> List[str]:
        """P4: 从关键词中提取技术栈相关词，去掉通用词

        Args:
            keywords: 原始关键词
            topic: 论文主题

        Returns:
            List[str]: 过滤后的技术关键词
        """
        # 通用词黑名单（学术检索噪声大）
        generic_words = {
            "系统", "管理", "设计", "实现", "研究", "应用", "开发",
            "基于", "分析", "方法", "技术", "平台", "方案", "测试",
            "论文", "毕业", "优化", "改进", "实践", "项目", "工程",
        }
        # 提取技术关键词
        tech_kw = [k for k in keywords if k not in generic_words]
        if not tech_kw:
            tech_kw = keywords  # 回退
        # 从主题中提取额外技术词
        if topic:
            import re
            # 提取英文技术栈
            eng_terms = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', topic)
            for t in eng_terms:
                if len(t) > 3 and t.lower() not in [k.lower() for k in tech_kw]:
                    tech_kw.insert(0, t)
        return tech_kw[:5]  # 最多5个关键词，避免API查询过长

    @staticmethod
    def _filter_relevance(
        refs: List["Reference"],
        keywords: List[str],
        target_count: int,
    ) -> List["Reference"]:
        """P4: 按关键词在标题/摘要中出现的频率过滤低相关性文献

        Args:
            refs: 原始文献列表
            keywords: 技术关键词
            target_count: 目标保留数量

        Returns:
            List[Reference]: 过滤后的文献
        """
        scored = []
        for ref in refs:
            text = (ref.title + " " + ref.abstract).lower()
            # 计算关键词命中率
            hits = sum(1 for kw in keywords if kw.lower() in text)
            score = hits + (0.5 if ref.year and ref.year >= 2020 else 0)
            if hits >= 1:  # 至少命中一个技术关键词
                scored.append((score, ref))

        # 按分数降序，保留目标数量
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ref for score, ref in scored[:target_count]]

    def fetch_for_outline(
        self,
        keywords: List[str],
        chapter_titles: List[str],
    ) -> List[Reference]:
        """为完整论文大纲检索文献

        对每个章节目录关键词分别检索，合并去重。

        Args:
            keywords: 论文总体关键词
            chapter_titles: 各章节标题列表

        Returns:
            List[Reference]: 去重后的文献列表
        """
        all_refs: List[Reference] = []
        seen_keys: set = set()

        # 用总体关键词检索
        for ref in self.fetch_by_keywords(keywords, limit=15):
            if ref.key not in seen_keys:
                all_refs.append(ref)
                seen_keys.add(ref.key)

        # 为每个章节的关键词检索（取章节标题中的关键词）
        for title in chapter_titles[:5]:  # 最多取 5 章
            # 简单提取标题中的关键词（中文 2-4 字短语）
            import re
            title_kws = re.findall(r'[\u4e00-\u9fff]{2,4}', title)
            if title_kws:
                for ref in self.fetch_by_keywords(title_kws[:3], limit=3):
                    if ref.key not in seen_keys:
                        all_refs.append(ref)
                        seen_keys.add(ref.key)

        return all_refs[:self.max_results]

    def format_references(
        self,
        refs: List[Reference],
        style: str = "gb7714",
    ) -> str:
        """将文献列表格式化为指定引用格式的文本

        Args:
            refs: 文献列表
            style: 引用格式，"gb7714" 或 "bibtex"

        Returns:
            str: 格式化后的文本
        """
        if not refs:
            return "暂无参考文献"

        if style == "bibtex":
            return "\n\n".join(ref.to_bibtex() for ref in refs)

        # 默认 GB7714
        lines = ["# 参考文献", ""]
        for i, ref in enumerate(refs, 1):
            lines.append(f"[{i}] {ref.to_gb7714()}")
            lines.append("")

        return "\n".join(lines)

    def fetch_with_citations(
        self,
        keywords: List[str],
        chapter_content: str = "",
    ) -> Tuple[List['Reference'], str]:
        """检索文献并生成带引用标记的 prompt 文本

        Args:
            keywords: 关键词列表
            chapter_content: 当前章节内容（用于提取更精准的关键词）

        Returns:
            Tuple: (参考文献列表, 格式化的引用 prompt 文本)
        """
        refs = self.fetch_by_keywords(keywords, limit=20)

        # 为每个 ref 设置 cache_key
        for ref in refs:
            if not ref.cache_key:
                ref.cache_key = f"{ref.key}:{ref.year}"

        # 生成引用 prompt 文本
        from prompts.reference_prompts import build_references_text
        refs_text = build_references_text(refs)

        return refs, refs_text

    # ── 缓存与限流 ────────────────────────────────────────

    @classmethod
    def _get_cached(cls, cache_key: str) -> Optional[List['Reference']]:
        """从本地 LRU 缓存获取文献

        Args:
            cache_key: 缓存键

        Returns:
            Optional[List[Reference]]: 缓存命中则返回列表，否则 None
        """
        return cls._cache.get(cache_key)

    @classmethod
    def _set_cache(cls, cache_key: str, refs: List['Reference']) -> None:
        """写入 LRU 缓存，超出容量时淘汰最旧条目

        Args:
            cache_key: 缓存键
            refs: 文献列表
        """
        if cache_key in cls._cache:
            cls._cache.move_to_end(cache_key)
        else:
            cls._cache[cache_key] = refs
            if len(cls._cache) > cls._cache_maxsize:
                cls._cache.popitem(last=False)

    @classmethod
    def _throttle(cls) -> None:
        """API 限流：确保两次请求间隔 ≥ 3 秒，连续限流时指数退避"""
        elapsed = time.time() - cls._last_request_time
        wait = cls._min_request_interval - elapsed
        # 指数退避：连续被限流时翻倍等待
        if cls._retry_count > 0:
            wait += cls._min_request_interval * (2 ** (cls._retry_count - 1))
        if wait > 0:
            logger.debug(f"API 限流等待 {wait:.1f}s (retry={cls._retry_count})")
            time.sleep(wait)
        cls._last_request_time = time.time()

    @classmethod
    def _mark_rate_limited(cls) -> None:
        """标记一次限流，触发指数退避"""
        cls._retry_count = min(cls._retry_count + 1, 4)  # 最多 3*2^4=48s
        logger.warning(f"API 限流: retry_count={cls._retry_count}")

    @classmethod
    def _reset_rate_limit(cls) -> None:
        """重置限流计数（请求成功后调用）"""
        cls._retry_count = 0

    # ── 内部检索方法 ──────────────────────────────────────────

    def _search_semantic_scholar(self, query: str, limit: int) -> List[Reference]:
        """通过 Semantic Scholar API 检索

        Args:
            query: 搜索查询
            limit: 返回数量

        Returns:
            List[Reference]: 文献列表
        """
        try:
            # P4: API 限流控制
            self._throttle()

            url = f"{SEMANTIC_SCHOLAR_API}/paper/search"
            params: Dict[str, Any] = {
                "query": query,
                "limit": min(limit, 100),
                "fields": "title,authors,year,venue,externalIds,url,abstract",
            }
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            self._reset_rate_limit()  # P4: 成功则重置限流计数
            data = resp.json()
            papers = data.get("data", [])
            refs: List[Reference] = []
            for paper in papers:
                title = paper.get("title", "Unknown Title")
                if not title or title == "Unknown Title":
                    continue

                # 提取作者
                authors_list = paper.get("authors", [])
                authors = [a.get("name", "") for a in authors_list if a.get("name")]

                year = paper.get("year", 2024) or 2024
                venue = paper.get("venue", "") or ""

                # 提取 DOI
                ext_ids = paper.get("externalIds", {}) or {}
                doi = ext_ids.get("DOI", None)

                # 生成引用 key
                key = self._generate_key(authors, year, title)

                # 生成 URL
                paper_url = paper.get("url", "")
                if doi:
                    paper_url = f"https://doi.org/{doi}"

                ref = Reference(
                    key=key,
                    title=title,
                    authors=authors,
                    year=year,
                    venue=venue,
                    doi=doi,
                    url=paper_url,
                    citation_text="",
                    abstract=paper.get("abstract", "") or "",  # P4: 保留摘要用于相关性过滤
                )
                ref.citation_text = ref.to_gb7714()
                refs.append(ref)

            # 按年份降序排列
            refs.sort(key=lambda r: r.year, reverse=True)
            return refs[:limit]

        except requests.exceptions.Timeout:
            logger.warning("Semantic Scholar 请求超时")
            return []
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                logger.warning(f"Semantic Scholar 429 限流，启用指数退避")
                self._mark_rate_limited()
            else:
                logger.warning(f"Semantic Scholar HTTP 错误: {e}")
            return []
        except requests.exceptions.RequestException as e:
            logger.warning(f"Semantic Scholar 请求失败: {e}")
            return []
        except Exception as e:
            logger.error(f"Semantic Scholar 解析失败: {e}")
            return []

    def _search_crossref(self, query: str, limit: int) -> List[Reference]:
        """通过 Crossref API 检索

        Args:
            query: 搜索查询
            limit: 返回数量

        Returns:
            List[Reference]: 文献列表
        """
        try:
            params: Dict[str, Any] = {
                "query": query,
                "rows": min(limit, 50),
                "sort": "relevance",
            }
            resp = requests.get(CROSSREF_API, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            items = data.get("message", {}).get("items", [])
            refs: List[Reference] = []

            for item in items:
                title_list = item.get("title", ["Unknown Title"])
                title = title_list[0] if title_list else "Unknown Title"
                if not title or title == "Unknown Title":
                    continue

                # 提取作者
                author_list = item.get("author", [])
                authors = []
                for a in author_list:
                    family = a.get("family", "")
                    given = a.get("given", "")
                    name = f"{given} {family}".strip() if given else family
                    if name:
                        authors.append(name)

                # 年份
                issued = item.get("issued", {})
                date_parts = issued.get("date-parts", [[2024]])
                year = date_parts[0][0] if date_parts and date_parts[0] else 2024

                # 期刊/会议
                container = item.get("container-title", [])
                venue = container[0] if container else ""

                # DOI
                doi = item.get("DOI", None)

                # 生成 key
                key = self._generate_key(authors, year, title)

                ref = Reference(
                    key=key,
                    title=title,
                    authors=authors,
                    year=year,
                    venue=venue,
                    doi=doi,
                    url=f"https://doi.org/{doi}" if doi else "",
                    citation_text="",
                )
                ref.citation_text = ref.to_gb7714()
                refs.append(ref)

            refs.sort(key=lambda r: r.year, reverse=True)
            return refs[:limit]

        except requests.exceptions.Timeout:
            logger.warning("Crossref 请求超时")
            return []
        except requests.exceptions.RequestException as e:
            logger.warning(f"Crossref 请求失败: {e}")
            return []
        except Exception as e:
            logger.error(f"Crossref 解析失败: {e}")
            return []

    @staticmethod
    def _generate_key(authors: List[str], year: int, title: str) -> str:
        """生成文献唯一键

        格式: FirstAuthorLastName + Year + FirstWordOfTitle

        Args:
            authors: 作者列表
            year: 年份
            title: 标题

        Returns:
            str: 引用键
        """
        # 提取第一作者姓氏
        if authors:
            first_author = authors[0]
            # 对英文名取最后一个词作为姓氏，中文直接取
            parts = first_author.split()
            surname = parts[-1] if parts else "Unknown"
        else:
            surname = "Unknown"

        # 提取标题首词（去除非字母数字）
        import re
        title_words = re.findall(r'[a-zA-Z0-9\u4e00-\u9fff]+', title)
        first_word = title_words[0] if title_words else "paper"

        return f"{surname}{year}{first_word}"
