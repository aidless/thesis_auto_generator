"""
数据导入模块（P1-R13）

解析用户上传的 .xlsx / .csv 文件，输出结构化文本供 LLM prompt 注入。

支持格式：.xlsx（openpyxl）、.csv（csv 标准库）
"""

import csv
import io
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


class DataImporter:
    """Excel/CSV 数据导入器

    将用户上传的数据文件解析为 LLM 可理解的文本描述，
    注入到章节生成的 prompt 中。
    """

    # 预览最大行数
    MAX_PREVIEW_ROWS: int = 5
    # prompt 文本最大字符数
    MAX_PROMPT_CHARS: int = 2000

    def import_file(self, file_path: str) -> Dict[str, Any]:
        """导入数据文件

        根据扩展名自动选择解析方式。

        Args:
            file_path: 文件路径（.xlsx 或 .csv）

        Returns:
            Dict 包含:
            - raw_data: 原始二维列表
            - summary: 数据摘要文本
            - columns: 列名列表
            - preview: 前 N 行预览
            - file_name: 文件名

        Raises:
            ValueError: 不支持的格式或文件损坏
            FileNotFoundError: 文件不存在
        """
        if file_path.lower().endswith('.csv'):
            return self._import_csv(file_path)
        elif file_path.lower().endswith('.xlsx'):
            return self._import_xlsx(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_path}，仅支持 .xlsx 和 .csv")

    def to_prompt_text(self, data: Dict[str, Any], max_chars: int = 2000) -> str:
        """将导入数据转为 LLM prompt 可用的文本块

        Args:
            data: import_file 的返回值
            max_chars: 最大字符数，超出截断

        Returns:
            str: 格式化的数据描述文本
        """
        rows = data.get("raw_data", [])
        columns = data.get("columns", [])
        file_name = data.get("file_name", "data")

        if not rows or not columns:
            return "（未提供有效数据）"

        lines = [
            f"【用户上传数据：{file_name}】",
            f"数据规模：{len(rows)} 行 × {len(columns)} 列",
            f"列名：{', '.join(columns)}",
            "",
            "数据前 {preview} 行预览：".format(preview=min(self.MAX_PREVIEW_ROWS, len(rows))),
        ]

        # 表头
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("|" + "|".join(["---"] * len(columns)) + "|")

        # 预览行
        for row in rows[:self.MAX_PREVIEW_ROWS]:
            cells = [str(cell) if cell is not None else "" for cell in row]
            lines.append("| " + " | ".join(cells) + " |")

        # 统计摘要
        if data.get("summary"):
            lines.append("")
            lines.append(data["summary"])

        result = "\n".join(lines)
        if len(result) > max_chars:
            result = result[:max_chars - 100] + "\n\n...（数据过长，已截断）"
        return result

    def detect_chart_suggestion(self, data: Dict[str, Any]) -> Optional[str]:
        """根据数据特征建议图表类型（P2 时启用）

        Args:
            data: import_file 的返回值

        Returns:
            Optional[str]: 建议的图表类型描述
        """
        rows = data.get("raw_data", [])
        columns = data.get("columns", [])

        if len(rows) < 2 or len(columns) < 2:
            return None

        # 简单启发式：两列且第一列是文本 → 柱状图；全数字多列 → 折线图
        has_text_col = False
        numeric_cols = 0
        for row in rows[:10]:
            for j, val in enumerate(row):
                try:
                    float(str(val).replace('%', '').replace(',', ''))
                except (ValueError, TypeError):
                    if j < len(columns):
                        has_text_col = True

        if has_text_col and len(columns) >= 2:
            return "柱状图（建议 X 轴为文本列，Y 轴为数值列）"
        elif len(columns) >= 3:
            return "折线图或散点图（多组数值数据建议使用折线图对比趋势）"

        return None

    # ── 内部方法 ────────────────────────────────────────

    def _import_csv(self, file_path: str) -> Dict[str, Any]:
        """导入 CSV 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                rows = list(reader)
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='gbk') as f:
                reader = csv.reader(f)
                rows = list(reader)

        if not rows:
            return self._empty_result(file_path)

        columns = rows[0]
        data_rows = rows[1:]
        return self._build_result(file_path, columns, data_rows)

    def _import_xlsx(self, file_path: str) -> Dict[str, Any]:
        """导入 Excel 文件"""
        if not HAS_OPENPYXL:
            raise ImportError("openpyxl 未安装，无法解析 .xlsx 文件。请运行: pip install openpyxl")

        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active

            rows = []
            for row in ws.iter_rows(values_only=True):
                rows.append(list(row))
            wb.close()

            if not rows:
                return self._empty_result(file_path)

            columns = [str(c) if c is not None else f"列{j+1}" for j, c in enumerate(rows[0])]
            data_rows = rows[1:]
            return self._build_result(file_path, columns, data_rows)

        except Exception as e:
            logger.error(f"Excel 解析失败: {e}")
            raise ValueError(f"Excel 文件解析失败: {e}") from e

    def _build_result(
        self, file_path: str, columns: List[str], data_rows: List[List]
    ) -> Dict[str, Any]:
        """构建统一返回结构"""
        import os

        file_name = os.path.basename(file_path)
        summary = f"共 {len(data_rows)} 条记录，{len(columns)} 个字段。"

        # 尝试计算数值列的统计
        numeric_stats = []
        for j, col_name in enumerate(columns):
            try:
                values = [float(row[j]) for row in data_rows
                         if j < len(row) and row[j] is not None]
                if values:
                    avg = sum(values) / len(values)
                    numeric_stats.append(
                        f"  {col_name}: 均值={avg:.2f}, 范围=[{min(values):.2f}, {max(values):.2f}]"
                    )
            except (ValueError, TypeError, IndexError):
                pass

        if numeric_stats:
            summary += "\n\n数值字段统计：\n" + "\n".join(numeric_stats[:5])

        return {
            "raw_data": data_rows,
            "summary": summary,
            "columns": columns,
            "preview": data_rows[:self.MAX_PREVIEW_ROWS],
            "file_name": file_name,
        }

    @staticmethod
    def _empty_result(file_path: str) -> Dict[str, Any]:
        """空文件结果"""
        import os
        return {
            "raw_data": [],
            "summary": "文件为空或格式不正确",
            "columns": [],
            "preview": [],
            "file_name": os.path.basename(file_path),
        }
