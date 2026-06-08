"""
格式对比模块（P2-R18）

对比生成的 DOCX 与模板的格式差异，输出 Markdown 格式对比报告。

检查项：
- 页边距
- 各级标题样式（字体、大小、加粗、对齐）
- 正文样式
- 页眉页脚
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from core.models import TemplateStyles, StyleDef

logger = logging.getLogger(__name__)


class FormatChecker:
    """文档格式对比检查器

    对比模板样式与生成文档的实际样式，输出差异报告。
    """

    def compare(
        self,
        template: TemplateStyles,
        generated_styles: TemplateStyles,
    ) -> str:
        """对比模板与生成文档的格式差异

        Args:
            template: 模板样式（标准）
            generated_styles: 生成文档的样式

        Returns:
            str: Markdown 格式的对比报告
        """
        issues: List[str] = []
        ok_count = 0

        # 1. 页边距对比
        issues.append("## 1. 页边距对比\n")
        margin_match, margin_details = self._compare_margins(
            template.page_margins, generated_styles.page_margins
        )
        if margin_match:
            ok_count += 1
        issues.append(margin_details)

        # 2. 标题样式对比
        issues.append("\n## 2. 标题样式对比\n")
        for level in [1, 2, 3]:
            t_style = template.heading_styles.get(level)
            g_style = generated_styles.heading_styles.get(level)
            sub_title = ["", "章标题", "节标题", "子节标题"][level]
            if t_style and g_style:
                match, details = self._compare_style(
                    f"2.{level} {sub_title}", t_style, g_style
                )
                if match:
                    ok_count += 1
                issues.append(details)
            elif t_style:
                issues.append(
                    f"### {sub_title}\n"
                    f"- ⚠️ **缺失**：模板定义了 {sub_title} 样式，但生成文档中未找到\n"
                )

        # 3. 正文样式对比
        issues.append("\n## 3. 正文样式对比\n")
        if template.body_style and generated_styles.body_style:
            match, details = self._compare_style(
                "3 正文", template.body_style, generated_styles.body_style
            )
            if match:
                ok_count += 1
            issues.append(details)

        # 4. 页眉页脚对比
        if template.header_footer or generated_styles.header_footer:
            issues.append("\n## 4. 页眉页脚对比\n")
            t_hf = template.header_footer or {}
            g_hf = generated_styles.header_footer or {}
            if t_hf == g_hf:
                issues.append("✅ 页眉页脚一致\n")
                ok_count += 1
            else:
                issues.append(f"- ⚠️ 模板页眉：`{t_hf.get('header', '无')[:50]}`\n")
                issues.append(f"- ⚠️ 生成页眉：`{g_hf.get('header', '无')[:50]}`\n")

        # 汇总
        total_checks = 5  # 页边距 + 3 标题 + 正文
        if template.header_footer:
            total_checks += 1

        summary = (
            f"\n---\n"
            f"### 📊 对比结果：{ok_count}/{total_checks} 项一致\n\n"
        )
        if ok_count == total_checks:
            summary += "✅ **格式完全匹配模板** — 无需调整。\n"
        elif ok_count >= total_checks * 0.7:
            summary += "⚠️ **大部分格式匹配** — 存在少量差异，建议检查上述标记项。\n"
        else:
            summary += "❌ **存在较多格式差异** — 建议对比上述差异并调整模板或生成参数。\n"

        return "".join(issues) + summary

    def compare_by_path(self, template_path: str, generated_path: str) -> str:
        """直接从文件路径对比两个 DOCX 文件

        Args:
            template_path: 模板文件路径
            generated_path: 生成文件路径

        Returns:
            str: 对比报告
        """
        try:
            from core.template_parser import TemplateParser
            parser = TemplateParser()
            t_styles = parser.parse(template_path)
            g_styles = parser.parse(generated_path)
            return self.compare(t_styles, g_styles)
        except Exception as e:
            return f"❌ 格式对比失败: {e}"

    # ── 内部方法 ────────────────────────────────────────

    @staticmethod
    def _compare_margins(
        t_margins: Dict[str, float],
        g_margins: Dict[str, float],
    ) -> Tuple[bool, str]:
        """对比页边距

        Returns:
            Tuple[bool, str]: (是否一致, 详情文本)
        """
        lines = []
        all_match = True
        for edge in ["top", "bottom", "left", "right"]:
            t_val = t_margins.get(edge, 0)
            g_val = g_margins.get(edge, 0)
            diff = abs(t_val - g_val)
            if diff < 0.5:
                lines.append(f"- ✅ {edge}: {t_val}mm (一致)")
            else:
                all_match = False
                lines.append(
                    f"- ⚠️ **{edge}**: 模板 `{t_val}mm` → 生成 `{g_val}mm` "
                    f"(偏差 `{diff:.1f}mm`)"
                )
        return all_match, "\n".join(lines) + "\n"

    @staticmethod
    def _compare_style(
        label: str,
        t_style: StyleDef,
        g_style: StyleDef,
    ) -> Tuple[bool, str]:
        """对比单个样式定义

        Returns:
            Tuple[bool, str]: (是否一致, 详情文本)
        """
        lines = [f"### {label}\n"]
        all_match = True

        # 字体名
        if t_style.font_name == g_style.font_name:
            lines.append(f"- ✅ 字体: {t_style.font_name}")
        else:
            all_match = False
            lines.append(f"- ⚠️ 字体: 模板 `{t_style.font_name}` → 生成 `{g_style.font_name}`")

        # 字号
        if t_style.font_size == g_style.font_size:
            lines.append(f"- ✅ 字号: {t_style.font_size}pt")
        else:
            all_match = False
            lines.append(f"- ⚠️ 字号: 模板 `{t_style.font_size}pt` → 生成 `{g_style.font_size}pt`")

        # 加粗
        if t_style.bold == g_style.bold:
            lines.append(f"- ✅ 加粗: {'是' if t_style.bold else '否'}")
        else:
            all_match = False
            lines.append(
                f"- ⚠️ 加粗: 模板 `{'是' if t_style.bold else '否'}` "
                f"→ 生成 `{'是' if g_style.bold else '否'}`"
            )

        # 对齐
        align_map = {0: "左对齐", 1: "居中", 2: "右对齐", 3: "两端对齐"}
        if t_style.alignment == g_style.alignment:
            lines.append(f"- ✅ 对齐: {align_map.get(t_style.alignment, '未知')}")
        else:
            all_match = False
            lines.append(
                f"- ⚠️ 对齐: 模板 `{align_map.get(t_style.alignment, '?')}` "
                f"→ 生成 `{align_map.get(g_style.alignment, '?')}`"
            )

        lines.append("")
        return all_match, "\n".join(lines) + "\n"
