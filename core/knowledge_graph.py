"""
文献知识图谱模块（P3）

使用 NetworkX 构建引用网络，支持：
- 节点（论文）和边（引用关系 + 语义相似度）构建
- 社区检测（研究子领域自动发现）
- 关键路径识别（经典→发展→前沿）
- 图谱统计和摘要生成
"""

import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from collections import Counter

from core.models import Reference

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("networkx 未安装，知识图谱功能不可用")


class KnowledgeGraph:
    """文献知识图谱

    以 NetworkX 有向图存储引用网络。

    Attributes:
        graph: NetworkX DiGraph
        papers: {ref_key: Reference}
    """

    def __init__(self):
        if not HAS_NETWORKX:
            raise ImportError("networkx 未安装，无法使用 KnowledgeGraph")

        self.graph = nx.DiGraph()
        self.papers: Dict[str, Reference] = {}

    def build(self, references: List[Reference]) -> None:
        """从参考文献列表构建图谱

        节点 = 每篇文献，边 = 引用方向 + 语义相似度。

        Args:
            references: 参考文献列表
        """
        if not references:
            logger.warning("参考文献列表为空，跳过图谱构建")
            return

        # 添加节点
        for ref in references:
            self.graph.add_node(
                ref.key,
                title=ref.title,
                authors=", ".join(ref.authors[:3]),
                year=ref.year,
                venue=ref.venue,
                label=f"{ref.authors[0].split()[-1] if ref.authors else 'Unknown'} ({ref.year})",
            )
            self.papers[ref.key] = ref

        # 构建边：语义相似度（关键词重叠）
        for i, ref_a in enumerate(references):
            kw_a = self._extract_keywords(ref_a.title)
            for j, ref_b in enumerate(references):
                if i >= j:
                    continue
                kw_b = self._extract_keywords(ref_b.title)
                similarity = self._jaccard_similarity(kw_a, kw_b)
                if similarity > 0.1:
                    self.graph.add_edge(
                        ref_a.key, ref_b.key,
                        weight=round(similarity, 3),
                        type="semantic",
                    )
                    self.graph.add_edge(
                        ref_b.key, ref_a.key,
                        weight=round(similarity, 3),
                        type="semantic",
                    )
                    logger.debug(
                        f"语义边: {ref_a.key} ↔ {ref_b.key} (sim={similarity:.2f})"
                    )

        logger.info(
            f"知识图谱已构建: {self.graph.number_of_nodes()} 节点, "
            f"{self.graph.number_of_edges()} 边"
        )

    def get_statistics(self) -> Dict[str, Any]:
        """获取图谱统计信息

        Returns:
            Dict: 包含节点数、边数、密度、中心性等
        """
        if self.graph.number_of_nodes() == 0:
            return {"nodes": 0, "edges": 0}

        stats = {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "density": round(nx.density(self.graph), 4),
        }

        # 度数中心性 Top 5
        try:
            degree_cent = nx.degree_centrality(self.graph)
            top_nodes = sorted(degree_cent.items(), key=lambda x: x[1], reverse=True)[:5]
            stats["top_influential"] = [
                {"key": k, "label": self.graph.nodes[k].get("label", k), "score": round(v, 3)}
                for k, v in top_nodes
            ]
        except Exception:
            stats["top_influential"] = []

        # 连通分量数
        try:
            if self.graph.is_directed():
                components = list(nx.weakly_connected_components(self.graph))
            else:
                components = list(nx.connected_components(self.graph))
            stats["components"] = len(components)
            stats["largest_component_size"] = max(len(c) for c in components) if components else 0
        except Exception:
            stats["components"] = 1
            stats["largest_component_size"] = stats["nodes"]

        # 年份分布
        years = [self.graph.nodes[n].get("year", 0) for n in self.graph.nodes]
        if years:
            stats["year_range"] = f"{min(years)}-{max(years)}"
            stats["median_year"] = sorted(years)[len(years) // 2]

        return stats

    def detect_communities(self) -> List[List[str]]:
        """社区检测：发现研究子领域

        Returns:
            List[List[str]]: 每个社区的文献 key 列表
        """
        if self.graph.number_of_nodes() < 3:
            return [[n] for n in self.graph.nodes]

        try:
            # 转为无向图进行社区检测
            ug = self.graph.to_undirected()
            communities = list(nx.community.greedy_modularity_communities(ug))
            return [list(c) for c in communities]
        except Exception as e:
            logger.debug(f"社区检测失败: {e}")
            return [[n] for n in self.graph.nodes]

    def get_critical_path(self) -> List[str]:
        """识别关键路径：从经典文献到前沿研究的演进脉络

        使用 PageRank 排序，结合年份加权。

        Returns:
            List[str]: 按重要性排序的文献 key 列表
        """
        if self.graph.number_of_nodes() == 0:
            return []

        try:
            pr = nx.pagerank(self.graph, weight="weight")
            # 年份加权：更新近的权重略高
            max_year = max(
                (self.graph.nodes[n].get("year", 2024) for n in self.graph.nodes),
                default=2024,
            )
            for node in pr:
                year = self.graph.nodes[node].get("year", 2024)
                recency_factor = 1 + (year - 2000) / (max_year - 2000 + 1) * 0.3
                pr[node] *= recency_factor

            sorted_nodes = sorted(pr.items(), key=lambda x: x[1], reverse=True)
            logger.info(f"关键路径 Top 3: {[(k, round(v, 3)) for k, v in sorted_nodes[:3]]}")
            return [k for k, _ in sorted_nodes]
        except Exception as e:
            logger.debug(f"PageRank 计算失败: {e}")
            return list(self.graph.nodes)

    def to_json_summary(self) -> Dict:
        """生成 JSON 格式的图谱摘要，供 LLM 批判性综述使用

        Returns:
            Dict: 图谱摘要
        """
        stats = self.get_statistics()
        communities = self.detect_communities()
        critical_path = self.get_critical_path()

        return {
            "statistics": stats,
            "communities": [
                {
                    "id": i + 1,
                    "size": len(c),
                    "papers": [
                        {
                            "key": k,
                            "title": self.papers[k].title if k in self.papers else k,
                            "year": self.graph.nodes[k].get("year", 0),
                            "authors": self.graph.nodes[k].get("authors", ""),
                        }
                        for k in c[:5]
                    ],
                }
                for i, c in enumerate(communities)
            ],
            "critical_path": [
                {
                    "key": k,
                    "title": self.papers[k].title if k in self.papers else k,
                    "year": self.graph.nodes[k].get("year", 0),
                    "label": self.graph.nodes[k].get("label", k),
                }
                for k in critical_path[:10]
            ],
        }

    # ── 内部方法 ────────────────────────────────────────

    @staticmethod
    def _extract_keywords(title: str) -> Set[str]:
        """从标题提取关键词

        Args:
            title: 论文标题

        Returns:
            Set[str]: 关键词集合
        """
        import re
        # 简单分词：英文按空格，中文按 2-4 字
        words = set()
        title_lower = title.lower()
        # 英文词
        eng_words = re.findall(r'[a-z]{3,}', title_lower)
        words.update(eng_words)
        # 中文词（2-4字）
        cn_words = re.findall(r'[\u4e00-\u9fff]{2,4}', title)
        words.update(cn_words)
        return words

    @staticmethod
    def _jaccard_similarity(set_a: Set, set_b: Set) -> float:
        """Jaccard 相似度

        Args:
            set_a, set_b: 两个集合

        Returns:
            float: [0, 1] 相似度
        """
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union
