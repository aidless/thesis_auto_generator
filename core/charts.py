"""
图表生成模块（P2-R14）

从结构化数据生成 matplotlib 图表，以图片形式嵌入 DOCX。
支持柱状图、折线图、饼图，使用中文字体配置。

依赖：matplotlib≥3.8, Pillow≥10.0
"""

import os
import io
import logging
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")  # 无 GUI 后端
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    logger.warning("matplotlib 未安装，图表功能不可用")


# 中文字体搜索路径
_CHINESE_FONT_CANDIDATES = [
    "SimHei", "Microsoft YaHei", "SimSun", "KaiTi",
    "WenQuanYi Micro Hei", "Noto Sans CJK SC", "AR PL UMing CN",
    "STSong", "FangSong", "Heiti SC",
]


class ChartGenerator:
    """图表生成器

    从数据列表生成 matplotlib 图表，输出 PNG bytes。
    """

    DPI: int = 150
    FIG_SIZE: Tuple[int, int] = (8, 5)

    def __init__(self):
        """初始化图表生成器，自动检测并配置中文字体"""
        if not HAS_MPL:
            raise ImportError("matplotlib 未安装，无法使用 ChartGenerator")

        self._font_name = self._detect_chinese_font()
        if self._font_name:
            plt.rcParams["font.family"] = self._font_name
            plt.rcParams["axes.unicode_minus"] = False
            logger.info(f"图表中文字体: {self._font_name}")
        else:
            logger.warning("未找到中文字体，图表中中文可能显示为方块")

    def generate_bar(
        self,
        labels: List[str],
        values: List[float],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        color: str = "#4472C4",
    ) -> io.BytesIO:
        """生成柱状图

        Args:
            labels: X 轴标签列表
            values: Y 轴数值列表
            title: 图表标题
            xlabel: X 轴标签
            ylabel: Y 轴标签
            color: 柱体颜色

        Returns:
            io.BytesIO: PNG 图片字节流
        """
        fig, ax = plt.subplots(figsize=self.FIG_SIZE, dpi=self.DPI)
        bars = ax.bar(labels, values, color=color, edgecolor="white", linewidth=0.5)

        # 数值标注
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )

        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="x", rotation=30 if max(len(str(l)) for l in labels) > 4 else 0)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=self.DPI, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def generate_line(
        self,
        x_labels: List[str],
        data_series: Dict[str, List[float]],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
    ) -> io.BytesIO:
        """生成折线图（支持多条折线）

        Args:
            x_labels: X 轴标签
            data_series: {"系列名": [数值]}  多条折线
            title: 标题
            xlabel: X 轴标签
            ylabel: Y 轴标签

        Returns:
            io.BytesIO: PNG 字节流
        """
        fig, ax = plt.subplots(figsize=self.FIG_SIZE, dpi=self.DPI)

        colors = ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5"]
        for i, (series_name, values) in enumerate(data_series.items()):
            ax.plot(x_labels, values, marker="o", linewidth=2,
                   color=colors[i % len(colors)], label=series_name, markersize=4)

        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(loc="best", frameon=False)
        ax.grid(axis="y", alpha=0.3)
        ax.tick_params(axis="x", rotation=30 if len(x_labels) > 6 else 0)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=self.DPI, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def generate_pie(
        self,
        labels: List[str],
        values: List[float],
        title: str = "",
    ) -> io.BytesIO:
        """生成饼图

        Args:
            labels: 类别标签
            values: 各类别数值
            title: 标题

        Returns:
            io.BytesIO: PNG 字节流
        """
        fig, ax = plt.subplots(figsize=(7, 7), dpi=self.DPI)
        colors = ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5", "#70AD47"]

        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct="%1.1f%%",
            colors=colors[:len(labels)],
            startangle=90,
            pctdistance=0.75,
        )
        for at in autotexts:
            at.set_fontsize(9)

        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=self.DPI, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def save_chart(self, buf: io.BytesIO, filepath: str) -> str:
        """将图表写入磁盘

        Args:
            buf: 图表字节流
            filepath: 输出路径

        Returns:
            str: 实际保存路径
        """
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(buf.getvalue())
        logger.info(f"图表已保存: {filepath}")
        return filepath

    def try_generate_from_data(
        self,
        data: Dict[str, Any],
        chart_type: str = "auto",
    ) -> Optional[Tuple[io.BytesIO, str]]:
        """从 DataImporter 数据自动生成图表

        Args:
            data: DataImporter.import_file 的返回值
            chart_type: "auto" | "bar" | "line" | "pie"

        Returns:
            Optional[Tuple]: (图片字节流, 图表标题) 或 None
        """
        if not HAS_MPL:
            return None

        rows = data.get("raw_data", [])
        cols = data.get("columns", [])
        if len(rows) < 2 or len(cols) < 2:
            return None

        # 尝试识别 X 轴（文本列）和 Y 轴（数值列）
        text_col_idx = 0
        num_col_indices = []

        for j, col_name in enumerate(cols):
            # 取前 10 行判断类型
            numeric = 0
            for row in rows[:10]:
                try:
                    float(str(row[j]).replace("%", "").replace(",", ""))
                    numeric += 1
                except (ValueError, IndexError):
                    pass
            if numeric >= len(rows[:10]) * 0.7:
                num_col_indices.append(j)
            else:
                text_col_idx = j

        if not num_col_indices:
            return None

        # 生成图表
        if chart_type == "auto":
            if len(num_col_indices) == 1:
                chart_type = "bar"
            elif len(num_col_indices) >= 2:
                chart_type = "line"
            else:
                chart_type = "bar"

        labels = [str(row[text_col_idx])[:12] for row in rows]

        if chart_type == "pie":
            values = [float(str(row[num_col_indices[0]]).replace("%", "").replace(",", ""))
                     for row in rows]
            buf = self.generate_pie(
                labels=labels,
                values=values,
                title=f"{cols[num_col_indices[0]]} 分布",
            )
            return buf, f"图: {cols[num_col_indices[0]]} 分布"

        elif chart_type == "line" and len(num_col_indices) >= 2:
            series = {}
            for j in num_col_indices[:4]:
                values = [float(str(row[j]).replace("%", "").replace(",", ""))
                         for row in rows]
                series[cols[j]] = values
            buf = self.generate_line(
                x_labels=labels,
                data_series=series,
                title="数据趋势对比",
                xlabel=cols[text_col_idx],
                ylabel="值",
            )
            return buf, "图: 数据趋势对比"

        else:
            # 默认柱状图
            values = [float(str(row[num_col_indices[0]]).replace("%", "").replace(",", ""))
                     for row in rows]
            buf = self.generate_bar(
                labels=labels,
                values=values,
                title=f"{cols[num_col_indices[0]]} 统计",
                xlabel=cols[text_col_idx],
                ylabel=cols[num_col_indices[0]],
            )
            return buf, f"图: {cols[num_col_indices[0]]} 统计"

    # ── 内部方法 ────────────────────────────────────────

    @staticmethod
    def _detect_chinese_font() -> Optional[str]:
        """检测可用的中文字体"""
        available = {f.name for f in fm.fontManager.ttflist}
        for font_name in _CHINESE_FONT_CANDIDATES:
            if font_name in available:
                return font_name
        # 尝试通过 glob 搜索
        for font_name in _CHINESE_FONT_CANDIDATES:
            matches = [f for f in fm.fontManager.ttflist if font_name.lower() in f.name.lower()]
            if matches:
                return matches[0].name
        return None
