"""
查重预检模块（P4-T17）

提供三级检查：
1. 句向量相似度比对（基于 sentence-transformers，可选）
2. 段落指纹 (SimHash) + 内部自比对
3. Fallback 纯文本模式（不依赖外部模型）

注意：
- sentence-transformers 首次加载会下载约 500MB 模型，建议首次使用时给提示
- 在离线环境下自动回退到 SimHash + 文本模式
"""

import re
import hashlib
import logging
from typing import Dict, List, Tuple, Optional, Any
from itertools import combinations

logger = logging.getLogger(__name__)

# 尝试加载 sentence-transformers
try:
    from sentence_transformers import SentenceTransformer, util as st_util
    HAS_ST = True
    logger.info("sentence-transformers 可用")
except ImportError:
    HAS_ST = False
    logger.warning("sentence-transformers 未安装，查重仅使用 SimHash + 文本模式")


class ParagraphFingerprint:
    """SimHash 段落指纹"""

    @staticmethod
    def simhash(text: str, bits: int = 64) -> int:
        """生成文本的 SimHash 指纹

        Args:
            text: 段落文本
            bits: 哈希位数

        Returns:
            int: SimHash 值
        """
        if not text.strip():
            return 0

        # 分词（简单按空格和标点）
        tokens = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text.lower())

        # 向量累加
        v = [0] * bits
        for token in tokens:
            # 用 token hash 作为权重
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            for i in range(bits):
                if (h >> i) & 1:
                    v[i] += 1
                else:
                    v[i] -= 1

        # 降维
        result = 0
        for i in range(bits):
            if v[i] > 0:
                result |= (1 << i)

        return result

    @staticmethod
    def hamming_distance(a: int, b: int, bits: int = 64) -> int:
        """计算两个 SimHash 的汉明距离

        Args:
            a, b: SimHash 值
            bits: 位数

        Returns:
            int: 汉明距离
        """
        xor = a ^ b
        return bin(xor).count('1')

    @staticmethod
    def similarity(a: int, b: int, bits: int = 64) -> float:
        """SimHash 相似度 [0, 1]

        Args:
            a, b: SimHash 值
            bits: 位数

        Returns:
            float: 相似度
        """
        dist = ParagraphFingerprint.hamming_distance(a, b, bits)
        return 1.0 - (dist / bits)


class PlagiarismChecker:
    """查重预检器

    支持：句向量相似度、段落指纹、内部自比对、纯文本回退模式
    """

    # 相似度阈值
    HIGH_SIM_THRESHOLD: float = 0.85  # 高重复风险
    MEDIUM_SIM_THRESHOLD: float = 0.60  # 中等风险
    # 最小段落长度（字符数），低于此长度不检查
    MIN_PARAGRAPH_LEN: int = 50

    def __init__(self, model_name: str = ""):
        """初始化查重器

        Args:
            model_name: sentence-transformers 模型名，空则用默认轻量模型
        """
        self.st_model = None
        self.use_st = HAS_ST

        if HAS_ST:
            self._model_name = model_name or "paraphrase-multilingual-MiniLM-L12-v2"
            self._init_model()

    def check_document(
        self,
        text: str,
        reference_texts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """检查文档的重复风险

        Args:
            text: 待检查文本
            reference_texts: 外部参考文本列表（可选，用于外部比对）

        Returns:
            Dict: 检查报告
        """
        paragraphs = self._split_paragraphs(text)
        if len(paragraphs) < 2:
            return {"risk_level": "low", "issues": [], "summary": "文本过短，无需查重"}

        issues = []

        # 1. 内部自比对（段落指纹）
        fp_issues = self._check_internal_similarity(paragraphs)
        issues.extend(fp_issues)

        # 2. 外部比对（如果有参考文本）
        if reference_texts:
            ext_issues = self._check_external(paragraphs, reference_texts)
            issues.extend(ext_issues)

        # 3. 句向量相似度（如果有 sentence-transformers）
        if self.use_st and self.st_model:
            st_issues = self._check_sentence_similarity(paragraphs)
            issues.extend(st_issues)

        # 汇总
        risk_level = self._assess_risk(issues, len(paragraphs))
        return {
            "risk_level": risk_level,
            "issues": issues,
            "summary": self._summarize(risk_level, len(issues), len(paragraphs)),
        }

    def check_two_texts(self, text_a: str, text_b: str) -> Dict[str, Any]:
        """对比两段文本的相似度

        Args:
            text_a, text_b: 两段文本

        Returns:
            Dict: {similarity, fingerprint_sim, sentence_sim, verdict}
        """
        result = {"fingerprint_sim": 0, "sentence_sim": 0}

        # SimHash
        fp_a = ParagraphFingerprint.simhash(text_a)
        fp_b = ParagraphFingerprint.simhash(text_b)
        result["fingerprint_sim"] = round(ParagraphFingerprint.similarity(fp_a, fp_b), 3)

        # 句子相似度
        if self.use_st and self.st_model:
            emb_a = self.st_model.encode([text_a])
            emb_b = self.st_model.encode([text_b])
            result["sentence_sim"] = round(
                float(st_util.cos_sim(emb_a, emb_b)[0][0]), 3
            )

        max_sim = max(result["fingerprint_sim"], result["sentence_sim"])
        if max_sim >= self.HIGH_SIM_THRESHOLD:
            result["verdict"] = "high"
        elif max_sim >= self.MEDIUM_SIM_THRESHOLD:
            result["verdict"] = "medium"
        else:
            result["verdict"] = "low"

        return result

    # ── 内部检查方法 ──────────────────────────────────────

    def _check_internal_similarity(
        self,
        paragraphs: List[str],
    ) -> List[Dict[str, Any]]:
        """内部自比对：检查同一文档内的段落重复

        Args:
            paragraphs: 段落列表

        Returns:
            List[Dict]: 重复问题列表
        """
        issues = []
        if len(paragraphs) < 2:
            return issues

        # 生成段落指纹
        fps = [ParagraphFingerprint.simhash(p) for p in paragraphs]

        # 两两比较
        for i, j in combinations(range(len(paragraphs)), 2):
            # 跳过过短段落
            if (len(paragraphs[i]) < self.MIN_PARAGRAPH_LEN or
                len(paragraphs[j]) < self.MIN_PARAGRAPH_LEN):
                continue

            sim = ParagraphFingerprint.similarity(fps[i], fps[j])
            if sim >= self.MEDIUM_SIM_THRESHOLD:
                issues.append({
                    "type": "internal_duplicate",
                    "severity": "high" if sim >= self.HIGH_SIM_THRESHOLD else "medium",
                    "paragraph_a": i + 1,
                    "paragraph_b": j + 1,
                    "similarity": round(sim, 3),
                    "preview_a": paragraphs[i][:80] + "...",
                    "preview_b": paragraphs[j][:80] + "...",
                    "message": f"段落 {i+1} 与段落 {j+1} 高度相似 (sim={sim:.2f})，建议合并或改写",
                })

        return issues

    def _check_external(
        self,
        paragraphs: List[str],
        reference_texts: List[str],
    ) -> List[Dict[str, Any]]:
        """外部比对：与参考文本库比对

        Args:
            paragraphs: 段落列表
            reference_texts: 参考文本

        Returns:
            List[Dict]: 匹配问题
        """
        issues = []
        ref_fps = [ParagraphFingerprint.simhash(r) for r in reference_texts]

        for i, para in enumerate(paragraphs):
            if len(para) < self.MIN_PARAGRAPH_LEN:
                continue
            fp = ParagraphFingerprint.simhash(para)
            for j, ref_fp in enumerate(ref_fps):
                sim = ParagraphFingerprint.similarity(fp, ref_fp)
                if sim >= self.HIGH_SIM_THRESHOLD:
                    issues.append({
                        "type": "external_match",
                        "severity": "high",
                        "paragraph": i + 1,
                        "reference_idx": j,
                        "similarity": round(sim, 3),
                        "message": f"段落 {i+1} 与参考文本 {j+1} 高度相似 (sim={sim:.2f})",
                    })
        return issues

    def _check_sentence_similarity(
        self,
        paragraphs: List[str],
    ) -> List[Dict[str, Any]]:
        """句向量相似度检查

        Args:
            paragraphs: 段落列表

        Returns:
            List[Dict]: 相似问题
        """
        if not self.st_model:
            return []

        issues = []
        valid = [(i, p) for i, p in enumerate(paragraphs)
                if len(p) >= self.MIN_PARAGRAPH_LEN]
        if len(valid) < 2:
            return issues

        texts = [p for _, p in valid]
        embeddings = self.st_model.encode(texts, show_progress_bar=False)

        for a_idx, (orig_a, _) in enumerate(valid):
            for b_idx, (orig_b, _) in enumerate(valid):
                if a_idx >= b_idx:
                    continue
                sim = float(st_util.cos_sim(
                    embeddings[a_idx:a_idx+1], embeddings[b_idx:b_idx+1]
                )[0][0])
                if sim >= self.MEDIUM_SIM_THRESHOLD:
                    issues.append({
                        "type": "sentence_sim",
                        "severity": "high" if sim >= self.HIGH_SIM_THRESHOLD else "medium",
                        "paragraph_a": orig_a + 1,
                        "paragraph_b": orig_b + 1,
                        "similarity": round(sim, 3),
                        "message": f"语义相似段落 {orig_a+1} ↔ {orig_b+1} (cos_sim={sim:.2f})",
                    })
        return issues

    def _check_text_similarity_fallback(
        self,
        text_a: str,
        text_b: str,
    ) -> float:
        """纯文本模式相似度（不依赖外部模型）

        基于 n-gram 重叠的 Jaccard 相似度。

        Args:
            text_a, text_b: 文本

        Returns:
            float: [0,1] 相似度
        """
        def ngrams(s, n=3):
            s = re.sub(r'[^\u4e00-\u9fff\w]', '', s)
            return set(s[k:k+n] for k in range(len(s) - n + 1))

        ng_a = ngrams(text_a)
        ng_b = ngrams(text_b)
        if not ng_a or not ng_b:
            return 0.0
        return len(ng_a & ng_b) / len(ng_a | ng_b)

    # ── 工具方法 ──────────────────────────────────────────

    @staticmethod
    def _split_paragraphs(text: str) -> List[str]:
        """按空行分割段落，过滤过短段落

        Args:
            text: 原始文本

        Returns:
            List[str]: 段落列表
        """
        paragraphs = re.split(r'\n\s*\n', text.strip())
        return [p.strip() for p in paragraphs if p.strip()]

    @staticmethod
    def _assess_risk(issues: List[Dict], total_paragraphs: int) -> str:
        """评估总体风险等级

        Returns:
            str: "high" | "medium" | "low"
        """
        high_count = sum(1 for i in issues if i.get("severity") == "high")
        med_count = sum(1 for i in issues if i.get("severity") == "medium")
        if high_count >= 2:
            return "high"
        if high_count >= 1 or med_count >= 3:
            return "medium"
        return "low"

    @staticmethod
    def _summarize(risk_level: str, issue_count: int, para_count: int) -> str:
        """生成检查摘要"""
        labels = {"high": "🔴 高风险", "medium": "🟡 中等风险", "low": "✅ 低风险"}
        return (
            f"{labels.get(risk_level, risk_level)}：共检查 {para_count} 个段落，"
            f"发现 {issue_count} 处疑似重复。"
            + ("\n建议重点修改高相似度段落。" if risk_level != "low" else "")
        )

    def _init_model(self) -> None:
        """初始化 sentence-transformers 模型"""
        if not self.use_st:
            return
        try:
            logger.info(f"正在加载 sentence-transformers 模型: {self._model_name} （首次加载约需 30-60 秒）")
            self.st_model = SentenceTransformer(self._model_name)
            logger.info("模型加载完成")
        except Exception as e:
            logger.warning(f"模型加载失败，回退到 SimHash 模式: {e}")
            self.use_st = False
            self.st_model = None
