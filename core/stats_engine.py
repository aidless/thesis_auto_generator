"""
实验数据深度洞察引擎（P4-T16）

从 DataImporter 的结构化数据出发，提供：
1. 实验设计前置检查（样本量/功效分析/变量匹配）
2. 统计检验推荐（t-test / ANOVA / chi² / Mann-Whitney）
3. 学术表述生成（数值 → APA/GB 标准表述）
4. 可复现性检查
5. 图表说明自动生成
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter

logger = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy 未安装，StatsEngine 部分功能不可用")

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger.warning("scipy 未安装，统计检验功能不可用")


class StatsEngine:
    """实验数据深度洞察引擎

    从结构化数据出发，提供统计建议、学术表述和可复现性检查。
    """

    # 小样本阈值
    SMALL_SAMPLE_THRESHOLD: int = 30
    # 样本量严重不足的警示阈值
    CRITICAL_SAMPLE_THRESHOLD: int = 10

    # ── 1. 实验设计前置检查 ──────────────────────────────

    def check_design(
        self,
        columns: List[str],
        sample_count: int,
        variable_types: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, str]]:
        """实验设计前置检查

        Args:
            columns: 列名列表
            sample_count: 样本量
            variable_types: 变量类型映射 {"col_name": "continuous"|"categorical"}

        Returns:
            List[Dict]: 警示列表 [{severity, message, suggestion}]
        """
        warnings = []

        # 样本量检查
        if sample_count < self.CRITICAL_SAMPLE_THRESHOLD:
            warnings.append({
                "severity": "critical",
                "message": f"样本量仅 {sample_count} 例，统计检验力严重不足",
                "suggestion": "建议报告效应量（Cohen's d/η²）而非 p 值；任何统计推断结论需明确标注「探索性分析」",
            })
        elif sample_count < self.SMALL_SAMPLE_THRESHOLD:
            warnings.append({
                "severity": "warning",
                "message": f"样本量 {sample_count} 例，处于小样本边缘",
                "suggestion": f"建议进行功效分析（功效≥0.8 所需最小样本量），同时报告效应量和置信区间",
            })

        # 多重比较警示
        if len(columns) >= 4:
            warnings.append({
                "severity": "info",
                "message": f"检测到 {len(columns)} 个变量，存在多重比较风险",
                "suggestion": "若需两两比较，建议使用 Bonferroni 校正（α'=α/n）或 Holm-Bonferroni 方法",
            })

        # 变量类型与检验方法匹配
        if variable_types:
            continuous_cols = [c for c, t in variable_types.items() if t == "continuous"]
            categorical_cols = [c for c, t in variable_types.items() if t == "categorical"]
            bin_cat = [c for c in categorical_cols
                      if isinstance(variable_types.get(c), str)]

            if len(continuous_cols) >= 2 and len(categorical_cols) >= 1:
                warnings.append({
                    "severity": "info",
                    "message": f"混合变量类型：{len(continuous_cols)} 连续 + {len(categorical_cols)} 分类",
                    "suggestion": f"连续变量间建议做 Pearson/Spearman 相关；分类-连续建议做 ANOVA（2组用t检验）",
                })

        return warnings

    # ── 2. 统计检验推荐 ──────────────────────────────────

    def recommend_tests(
        self,
        data: List[List],
        columns: List[str],
    ) -> List[Dict[str, Any]]:
        """根据数据结构推荐合适的统计检验方法

        Args:
            data: 二维数据列表
            columns: 列名列表

        Returns:
            List[Dict]: 推荐列表 [{test, reason, columns_involved, {result}}]
        """
        if len(columns) < 2:
            return [{"test": "描述性统计", "reason": "仅单变量，建议计算均值/标准差/中位数等描述性统计量", "columns": columns}]

        recommendations = []
        numeric_cols, categorical_cols = self._classify_columns(data, columns)

        # 两连续变量 → Pearson/Spearman 相关
        if len(numeric_cols) >= 2:
            r = {
                "test": "Pearson 相关系数",
                "reason": f"两个连续变量（{', '.join(numeric_cols[:2])}），"
                         "建议先做正态性检验，符合正态用 Pearson，否则用 Spearman",
                "columns": numeric_cols[:2],
                "alternative_test": "Spearman 秩相关系数",
            }
            recommendations.append(r)

        # 分类-连续 → t-test 或 ANOVA
        if categorical_cols and numeric_cols:
            cat_col = categorical_cols[0]
            categories = set()
            for row in data:
                idx = columns.index(cat_col) if cat_col in columns else -1
                if idx >= 0 and idx < len(row):
                    categories.add(str(row[idx]))

            if len(categories) == 2:
                recommendations.append({
                    "test": "独立样本 t 检验",
                    "reason": f"{cat_col} 为二分变量，建议比较两组在 {numeric_cols[0]} 上的差异",
                    "columns": [cat_col, numeric_cols[0]],
                })
            elif len(categories) >= 3:
                recommendations.append({
                    "test": "单因素方差分析 (One-way ANOVA)",
                    "reason": f"{cat_col} 含 {len(categories)} 个水平，建议 ANOVA 检验组间差异",
                    "columns": [cat_col, numeric_cols[0]],
                    "post_hoc": "若 ANOVA 显著，建议 Tukey HSD 或 Bonferroni 事后检验",
                })

        # 两分类变量 → chi²
        if len(categorical_cols) >= 2:
            recommendations.append({
                "test": "卡方检验 (χ²)",
                "reason": f"两个分类变量（{', '.join(categorical_cols[:2])}），建议用卡方检验或 Fisher 精确检验",
                "columns": categorical_cols[:2],
                "note": "若期望频数<5 的单元格超过 20%，建议使用 Fisher 精确检验",
            })

        if not recommendations:
            recommendations.append({
                "test": "描述性统计",
                "reason": "未识别出明确的假设检验场景",
                "columns": columns,
            })

        return recommendations

    def run_test(
        self,
        data: List[List],
        columns: List[str],
        test_type: str,
        col_a: str,
        col_b: Optional[str] = None,
    ) -> Dict[str, Any]:
        """运行指定的统计检验

        Args:
            data: 二维数据
            columns: 列名
            test_type: "ttest" | "anova" | "pearson" | "spearman" | "chi2"
            col_a, col_b: 列名

        Returns:
            Dict: {test, statistic, p_value, df, interpretation, apa_text}
        """
        if not HAS_SCIPY:
            return {"test": test_type, "error": "scipy 未安装"}

        try:
            vals_a = self._extract_column(data, columns, col_a, numeric=True)
            vals_b = self._extract_column(data, columns, col_b, numeric=(test_type != "chi2")) if col_b else None

            if test_type == "ttest" and vals_b:
                stat, p = scipy_stats.ttest_ind(vals_a, vals_b, nan_policy="omit")
                df = len(vals_a) + len(vals_b) - 2
                d = self._cohens_d(vals_a, vals_b)
                result = {"test": "独立样本 t 检验", "statistic": round(stat, 3), "p_value": round(p, 4),
                         "df": df, "cohens_d": round(d, 2),
                         "significant": p < 0.05}
                result["apa_text"] = (
                    f"独立样本 t 检验显示两{chr(39) if p < 0.05 else chr(39)}无显著"
                    f"{chr(39)}组间差异，t({df})={stat:.2f}, p={p:.3f}"
                    + (f", Cohen's d={d:.2f}" if d else "")
                )
                return result

            elif test_type == "pearson" and vals_b:
                stat, p = scipy_stats.pearsonr(vals_a, vals_b)
                return {"test": "Pearson 相关", "statistic": round(stat, 3), "p_value": round(p, 4),
                       "significant": p < 0.05, "n": len(vals_a),
                       "apa_text": f"Pearson 相关分析显示 r({len(vals_a)-2})={stat:.2f}, p={p:.3f}"}

            elif test_type == "spearman" and vals_b:
                stat, p = scipy_stats.spearmanr(vals_a, vals_b, nan_policy="omit")
                return {"test": "Spearman 相关", "statistic": round(stat, 3), "p_value": round(p, 4),
                       "significant": p < 0.05,
                       "apa_text": f"Spearman 秩相关显示 ρ={stat:.2f}, p={p:.3f}"}

            return {"test": test_type, "error": f"不支持的检验类型或参数不足"}
        except Exception as e:
            logger.error(f"统计检验失败 [{test_type}]: {e}")
            return {"test": test_type, "error": str(e)}

    # ── 3. 可复现性检查 ──────────────────────────────────

    def check_reproducibility(
        self,
        generation_prompt: str = "",
        code_snippets: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """检查研究流程中的可复现性问题

        Args:
            generation_prompt: 生成章节的 prompt
            code_snippets: 论文中的代码片段

        Returns:
            List[Dict]: 问题列表
        """
        issues = []

        # 随机种子检查
        seed_terms = ["random.seed", "np.random.seed", "torch.manual_seed",
                      "tf.random.set_seed", "random_state", "seed"]
        if code_snippets:
            all_code = "\n".join(code_snippets)
            has_seed = any(term in all_code.lower() for term in seed_terms)
            if "random" in all_code.lower() and not has_seed:
                issues.append({
                    "severity": "critical",
                    "aspect": "随机性控制",
                    "issue": "代码中包含随机操作但未固定随机种子",
                    "fix": "添加 random.seed(42)、np.random.seed(42) 等固定种子语句",
                })

        # 超参数完整性
        hyperparam_terms = ["learning_rate", "batch_size", "epochs", "hidden_size",
                           "dropout", "optimizer", "lr", "num_layers"]
        if code_snippets:
            all_code = "\n".join(code_snippets)
            found_params = [t for t in hyperparam_terms if t in all_code.lower()]
            if len(found_params) < 3 and any(t in all_code.lower() for t in ["train", "model"]):
                issues.append({
                    "severity": "warning",
                    "aspect": "超参数报告",
                    "issue": f"代码中仅报告了 {len(found_params)} 个关键超参数（需要≥3个）",
                    "fix": "补充 learning rate、batch size、epochs 等关键超参数的具体值",
                })

        # 数据预处理可追溯性
        preprocess_terms = ["normalize", "standardize", "impute", "augment",
                           "split", "shuffle", "balance"]
        if code_snippets:
            all_code = "\n".join(code_snippets)
            found_pp = [t for t in preprocess_terms if t in all_code.lower()]
            if not found_pp:
                issues.append({
                    "severity": "info",
                    "aspect": "数据预处理",
                    "issue": "未检测到明确的数据预处理步骤描述",
                    "fix": "建议在方法部分详细说明：数据划分策略、标准化方法、缺失值处理等",
                })

        return issues

    # ── 4. 图表说明生成 ──────────────────────────────────

    def generate_figure_caption(
        self,
        chart_type: str,
        data_summary: Dict[str, Any],
        figure_number: str = "",
    ) -> str:
        """为图表生成学术图注

        Args:
            chart_type: "bar" | "line" | "pie"
            data_summary: 来自 DataImporter 的数据摘要
            figure_number: 图表编号

        Returns:
            str: 学术风格的图注文本
        """
        fig_label = f"图{figure_number} " if figure_number else ""

        if chart_type == "bar":
            columns = data_summary.get("columns", [])
            caption = f"{fig_label}展示了各{columns[0] if columns else '类别'}在{columns[1] if len(columns) > 1 else '指标'}上的比较。"

        elif chart_type == "line":
            caption = f"{fig_label}展示了各指标随时间/类别的变化趋势。"

        elif chart_type == "pie":
            caption = f"{fig_label}展示了各组成部分的占比分布。"

        else:
            caption = f"{fig_label}数据可视化结果。"

        # 附加统计信息
        summary = data_summary.get("summary", "")
        if "均值" in summary:
            caption += f" {summary[:100]}"

        caption += " 误差线表示标准差（如适用）。"
        return caption

    # ── 内部工具方法 ──────────────────────────────────────

    @staticmethod
    def _classify_columns(
        data: List[List],
        columns: List[str],
    ) -> Tuple[List[str], List[str]]:
        """分类列：数值 vs 分类

        Returns:
            Tuple: (numeric_cols, categorical_cols)
        """
        numeric_cols = []
        categorical_cols = []
        for j, col_name in enumerate(columns):
            num_vals = 0
            unique_vals = set()
            for row in data[:50]:
                if j < len(row) and row[j] is not None:
                    try:
                        float(str(row[j]).replace("%", "").replace(",", ""))
                        num_vals += 1
                    except (ValueError, TypeError):
                        pass
                    unique_vals.add(str(row[j]))
            # >70% 可转数字 → 连续
            if num_vals >= min(len(data[:50]), 10) * 0.7:
                numeric_cols.append(col_name)
            else:
                categorical_cols.append(col_name)
        return numeric_cols, categorical_cols

    @staticmethod
    def _extract_column(
        data: List[List],
        columns: List[str],
        col_name: Optional[str],
        numeric: bool = True,
    ) -> List:
        """提取指定列的值"""
        if not col_name or col_name not in columns:
            return []
        idx = columns.index(col_name)
        values = []
        for row in data:
            if idx < len(row) and row[idx] is not None:
                v = str(row[idx]).replace("%", "").replace(",", "").strip()
                try:
                    values.append(float(v) if numeric else v)
                except ValueError:
                    if not numeric:
                        values.append(v)
        return values

    @staticmethod
    def _cohens_d(a: List[float], b: List[float]) -> float:
        """计算 Cohen's d 效应量"""
        if not HAS_SCIPY or len(a) < 2 or len(b) < 2:
            return 0.0
        try:
            import numpy as np
            na, nb = len(a), len(b)
            var_a = np.var(a, ddof=1)
            var_b = np.var(b, ddof=1)
            pooled_sd = np.sqrt(((na - 1) * var_a + (nb - 1) * var_b) / (na + nb - 2))
            if pooled_sd == 0:
                return 0.0
            return abs(np.mean(a) - np.mean(b)) / pooled_sd
        except Exception:
            return 0.0
