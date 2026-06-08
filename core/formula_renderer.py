"""
公式渲染模块（P2-R15）

将 Markdown 中的 LaTeX 公式（$...$ 和 $$...$$）渲染为：
- 模式 A（默认）：Matplotlib 渲染为 PNG 图片，嵌入 DOCX
- 模式 B（可选）：转为 MathML（需 latexml 工具）

注意：公式渲染依赖 matplotlib 的 mathtext 引擎，
仅支持 LaTeX 数学模式的子集，复杂公式建议模式 B。
"""

import io
import re
import logging
import os
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


class FormulaRenderer:
    """公式渲染器

    识别 Markdown 中的 LaTeX 公式，转为可嵌入 DOCX 的图片。
    """

    # LaTeX 公式匹配：行内 $...$ 和独立 $$...$$
    INLINE_FORMULA_PATTERN = re.compile(r'(?<!\$)\$(.+?)\$(?!\$)')
    DISPLAY_FORMULA_PATTERN = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)

    DPI: int = 150
    FONT_SIZE: int = 12

    def __init__(self):
        """初始化公式渲染器"""
        if not HAS_MPL:
            raise ImportError("matplotlib 未安装，公式渲染不可用")

    def render_inline(self, formula: str, font_size: int = 12) -> io.BytesIO:
        """渲染行内公式为 PNG

        Args:
            formula: LaTeX 公式（不含 $ 符号）
            font_size: 字号

        Returns:
            io.BytesIO: PNG 图片字节流
        """
        fig, ax = plt.subplots(figsize=(0.01, 0.01), dpi=self.DPI)
        ax.axis("off")

        text = ax.text(0, 0, f"${formula}$", fontsize=font_size,
                       ha="left", va="center",
                       transform=ax.transAxes)

        # 计算边界框
        fig.canvas.draw()
        bbox = text.get_window_extent(renderer=fig.canvas.get_renderer())
        bbox = bbox.transformed(fig.dpi_scale_trans.inverted())
        width, height = bbox.width, bbox.height

        plt.close(fig)

        # 重新创建精确尺寸的图
        fig, ax = plt.subplots(
            figsize=(width + 0.2, height + 0.15),
            dpi=self.DPI,
        )
        ax.axis("off")
        ax.text(0.05, 0.5, f"${formula}$", fontsize=font_size,
                ha="left", va="center",
                transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=self.DPI, bbox_inches="tight",
                    pad_inches=0.05, transparent=True)
        plt.close(fig)
        buf.seek(0)
        return buf

    def render_display(self, formula: str, font_size: int = 14) -> io.BytesIO:
        """渲染独占行公式为 PNG

        Args:
            formula: LaTeX 公式（不含 $$ 符号）
            font_size: 字号

        Returns:
            io.BytesIO: PNG 图片字节流
        """
        fig, ax = plt.subplots(figsize=(5, 0.8), dpi=self.DPI)
        ax.axis("off")

        ax.text(0.5, 0.5, f"${formula}$", fontsize=font_size,
                ha="center", va="center",
                transform=ax.transAxes)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=self.DPI, bbox_inches="tight",
                    pad_inches=0.1, transparent=True)
        plt.close(fig)
        buf.seek(0)
        return buf

    def extract_formulas(self, markdown_text: str) -> List[Tuple[str, str, str]]:
        """提取 Markdown 中的所有公式

        Args:
            markdown_text: Markdown 文本

        Returns:
            List[Tuple]: [(类型, 原始标记, 公式内容), ...]
                        类型: "inline" | "display"
        """
        formulas = []

        # 先提取 display 公式（避免与 inline 重叠）
        for match in self.DISPLAY_FORMULA_PATTERN.finditer(markdown_text):
            formulas.append(("display", match.group(0), match.group(1).strip()))

        for match in self.INLINE_FORMULA_PATTERN.finditer(markdown_text):
            formulas.append(("inline", match.group(0), match.group(1).strip()))

        return formulas

    def render_all(self, markdown_text: str, output_dir: str) -> List[Tuple[str, str]]:
        """渲染文档中所有公式，返回 (原始标记, 图片路径) 列表

        Args:
            markdown_text: 包含公式的 Markdown 文本
            output_dir: 图片输出目录

        Returns:
            List[Tuple[str,str]]: 用于替换的 (原始公式文本, 图片路径) 对
        """
        os.makedirs(output_dir, exist_ok=True)
        formulas = self.extract_formulas(markdown_text)
        replacements = []

        for i, (ftype, raw, formula) in enumerate(formulas):
            try:
                if ftype == "inline":
                    buf = self.render_inline(formula)
                else:
                    buf = self.render_display(formula)

                filename = f"formula_{i:04d}.png"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(buf.getvalue())

                replacements.append((raw, filepath))
                logger.debug(f"公式渲染: {formula[:30]}... → {filename}")

            except Exception as e:
                logger.warning(f"公式渲染失败 [{formula[:30]}...]: {e}")
                continue

        return replacements

    def to_mathml(self, formula: str) -> Optional[str]:
        """尝试将 LaTeX 公式转为 MathML（需外部工具）

        当前为存根实现，P2+ 可集成 latexml / MathJax-node。

        Args:
            formula: LaTeX 公式

        Returns:
            Optional[str]: MathML 字符串，暂返回 None
        """
        logger.warning("MathML 转换未实现（需外部 latexml / MathJax-node）")
        return None
