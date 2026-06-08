"""
多智能体评审引擎（P3）

使用 3 个 LLM Agent 并行评审论文的三个方面：
- Reviewer-Innovation：创新性与学术贡献
- Reviewer-Method：实验设计与方法严谨性
- Reviewer-Norm：规范性与可读性

评审结果汇总为结构化盲审报告。
"""

import json
import re
import logging
import threading
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from llm.base import BaseLLMClient
from core.models import Thesis
from prompts.reviewer_prompts import (
    INNOVATION_SYSTEM_PROMPT,
    METHOD_SYSTEM_PROMPT,
    NORM_SYSTEM_PROMPT,
    REPORT_TEMPLATE,
)

logger = logging.getLogger(__name__)


class ReviewAgent:
    """单个评审 Agent

    Attributes:
        name: Agent 名称
        role: 评审角色
        system_prompt: 系统提示
        temperature: LLM 温度
    """

    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str,
        temperature: float = 0.3,
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.result: Optional[Dict] = None
        self.error: Optional[str] = None


class ReviewEngine:
    """多智能体评审编排器

    并行调度 3 个 ReviewAgent，收集评审结果并生成汇总报告。

    Attributes:
        llm: LLM 客户端
    """

    def __init__(self, llm: BaseLLMClient):
        """初始化评审引擎

        Args:
            llm: LLM 客户端实例
        """
        self.llm = llm
        self._evidence: List[str] = []  # P4 新增：证据注入
        self.agents: Dict[str, ReviewAgent] = {
            "innovation": ReviewAgent(
                name="创新性评审",
                role="innovation",
                system_prompt=INNOVATION_SYSTEM_PROMPT,
                temperature=0.3,
            ),
            "method": ReviewAgent(
                name="方法评审",
                role="method",
                system_prompt=METHOD_SYSTEM_PROMPT,
                temperature=0.2,
            ),
            "norm": ReviewAgent(
                name="规范性评审",
                role="norm",
                system_prompt=NORM_SYSTEM_PROMPT,
                temperature=0.1,
            ),
        }

    def review(self, thesis: Thesis) -> Dict[str, Any]:
        """对论文执行完整评审

        Args:
            thesis: 论文状态对象

        Returns:
            Dict: 包含三个 Agent 评审结果和汇总报告的完整数据
        """
        # 构建论文全文文本
        paper_text = self._build_paper_text(thesis)
        if not paper_text:
            return {"error": "论文内容为空，无法评审"}

        # 并行评审
        threads = []
        for agent_id, agent in self.agents.items():
            t = threading.Thread(
                target=self._run_agent,
                args=(agent, paper_text),
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 收集结果
        results = {}
        errors = []
        for agent_id, agent in self.agents.items():
            if agent.result:
                results[agent_id] = agent.result
            elif agent.error:
                errors.append(f"{agent.name}: {agent.error}")

        if not results:
            return {"error": f"所有评审 Agent 均失败: {'; '.join(errors)}"}

        # 生成汇总报告
        report_md = self._generate_report(thesis, results, errors)

        return {
            "results": results,
            "report_md": report_md,
            "errors": errors,
            "timestamp": datetime.now().isoformat(),
        }

    def add_evidence(self, source: str, evidence_text: str, target_role: str = "method") -> None:
        """P4: 注入外部证据到评审流程

        例如 StatsEngine 发现统计方法问题、PlagiarismChecker 发现重复片段，
        这些信息可以作为评审 Agent 的输入材料。

        Args:
            source: 证据来源，如 "StatsEngine"、"PlagiarismChecker"
            target_role: 目标评审角色 "innovation"|"method"|"norm"
            evidence_text: 证据文本
        """
        self._evidence.append(
            f"[{source}] → [{target_role}]: {evidence_text}"
        )
        logger.info(f"评审证据已注入: [{source}] → [{target_role}]")

    def clear_evidence(self) -> None:
        """清空所有已注入证据"""
        self._evidence.clear()

    def review_chapter(self, thesis: Thesis, chapter_index: int) -> Dict[str, Any]:
        """对单个章节执行评审

        Args:
            thesis: 论文状态
            chapter_index: 章节索引

        Returns:
            Dict: 单章评审结果
        """
        chapter = thesis.get_chapter_by_index(chapter_index)
        if not chapter:
            return {"error": f"章节 {chapter_index} 不存在"}

        paper_text = (
            f"# 论文主题：{thesis.topic}\n\n"
            f"## {chapter.node.title}\n\n"
            f"{chapter.content_markdown}"
        )
        if not chapter.content_markdown:
            return {"error": "章节内容为空"}

        # 只用规范性 Agent 做单章评审
        agent = ReviewAgent(
            name="单章评审",
            role="norm",
            system_prompt=NORM_SYSTEM_PROMPT,
            temperature=0.1,
        )
        self._run_agent(agent, paper_text)

        if agent.result:
            agent.result["chapter_title"] = chapter.node.title
            agent.result["chapter_index"] = chapter_index
            return agent.result

        return {"error": agent.error or "评审失败"}

    # ── 内部方法 ────────────────────────────────────────

    def _run_agent(self, agent: ReviewAgent, paper_text: str) -> None:
        """运行单个评审 Agent

        Args:
            agent: 评审 Agent
            paper_text: 论文全文
        """
        try:
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": (
                    f"请评审以下论文的{agent.role}方面：\n\n"
                    f"{paper_text}\n\n"
                    f"{self._build_evidence_text(agent.role)}"
                    f"请严格按照 JSON 格式输出评审结果。"
                    f"必须输出有效的 JSON，不要添加额外说明。"
                )},
            ]

            response = self.llm.chat(
                messages=messages,
                temperature=agent.temperature,
                max_tokens=3072,
            )

            agent.result = self._parse_json_response(response)
            logger.info(f"{agent.name} 评审完成: 总分 {agent.result.get('total', 'N/A')}")

        except Exception as e:
            agent.error = str(e)
            logger.error(f"{agent.name} 评审失败: {e}")

    @staticmethod
    def _parse_json_response(response: str) -> Dict:
        """从 LLM 响应中提取 JSON

        Args:
            response: LLM 原始响应

        Returns:
            Dict: 解析后的 JSON 字典
        """
        # 尝试匹配 ```json ... ``` 块
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # 尝试匹配 { ... }
        brace_match = re.search(r'\{.*\}', response, re.DOTALL)
        if brace_match:
            return json.loads(brace_match.group(0))

        # 兜底
        return {
            "scores": {},
            "total": 0,
            "strengths": [],
            "weaknesses": ["无法解析评审结果"],
            "verdict": "unknown",
            "summary": response[:300],
        }

    def _build_evidence_text(self, role: str) -> str:
        """构建证据注入文本（P4 新增）

        Args:
            role: 评审角色

        Returns:
            str: 格式化的证据文本
        """
        role_evidences = [e for e in self._evidence if f"[{role}]" in e]
        if not role_evidences:
            return ""
        return (
            "\n\n---\n**以下为系统自动检测到的补充证据，请纳入评审考量：**\n" +
            "\n".join(f"- {e}" for e in role_evidences) +
            "\n---\n\n"
        )

    @staticmethod
    def _build_paper_text(thesis: Thesis) -> str:
        """构建论文全文文本供评审

        Args:
            thesis: 论文状态

        Returns:
            str: 格式化的论文全文
        """
        if not thesis.chapters:
            return ""

        parts = [
            f"# 论文题目：{thesis.topic}",
            f"关键词：{', '.join(thesis.keywords)}",
            f"目标字数：{thesis.target_word_count}",
            "",
        ]

        for i, chapter in enumerate(thesis.chapters):
            if chapter.content_markdown:
                parts.append(f"## 第{i+1}章 {chapter.node.title}")
                parts.append(chapter.content_markdown)
                parts.append("")
            else:
                parts.append(f"## 第{i+1}章 {chapter.node.title}")
                parts.append("（本章内容缺失）")
                parts.append("")

        if thesis.references:
            parts.append("## 参考文献")
            for i, ref in enumerate(thesis.references, 1):
                parts.append(f"[{i}] {ref.to_gb7714()}")

        return "\n".join(parts)

    def _generate_report(
        self,
        thesis: Thesis,
        results: Dict[str, Dict],
        errors: List[str],
    ) -> str:
        """生成汇总评审报告

        Args:
            thesis: 论文状态
            results: 各 Agent 评审结果
            errors: 失败的 Agent 错误

        Returns:
            str: Markdown 格式的评审报告
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        word_count = thesis.get_total_words()

        # 提取分项结果
        innovation = results.get("innovation", {})
        method = results.get("method", {})
        norm = results.get("norm", {})

        # 分数表
        score_rows = []
        for key, label in [("innovation", "创新性"), ("method", "方法"), ("norm", "规范性")]:
            r = results.get(key, {})
            total = r.get("total", "N/A")
            verdict_map = {
                "accept": "✅ 通过",
                "minor_revision": "🟡 小修",
                "major_revision": "🟠 大修",
                "reject": "🔴 不通过",
            }
            verdict = verdict_map.get(r.get("verdict", ""), "❓")
            score_rows.append(f"| {label} | {total}/10 | {self.agents[key].name} | {verdict} |")

        score_table = "\n".join(score_rows)

        # 加权总分
        weight_map = {"innovation": 0.35, "method": 0.35, "norm": 0.30}
        weighted = 0
        count = 0
        for key, w in weight_map.items():
            r = results.get(key, {})
            if isinstance(r.get("total"), (int, float)):
                weighted += r["total"] * w
                count += w
        weighted_total = round(weighted / max(count, 0.01), 1)

        # 最终判定
        if weighted_total >= 8:
            final_verdict = "✅ **小修后通过** — 论文质量良好，仅需少量修改"
        elif weighted_total >= 6:
            final_verdict = "🟡 **建议大修** — 存在若干重要问题需系统性改进"
        elif weighted_total >= 4:
            final_verdict = "🟠 **需要重大修改** — 多个维度存在严重不足"
        else:
            final_verdict = "🔴 **不建议通过** — 论文质量未达基本标准"

        # 关键问题汇总
        critical_all = []
        for key in ["innovation", "method", "norm"]:
            r = results.get(key, {})
            for issue in r.get("critical_issues", []):
                critical_all.append(f"- [{self.agents[key].name}] {issue}")

        critical_summary = "\n".join(critical_all) if critical_all else "🎉 无严重问题"

        # 修改优先级表
        priority_rows = []
        severities = {
            "innovation": results.get("innovation", {}).get("critical_issues", []),
            "method": results.get("method", {}).get("critical_issues", []),
            "norm": results.get("norm", {}).get("critical_issues", []),
        }
        for area, issues in severities.items():
            for issue in issues:
                priority_rows.append(
                    f"| 🔴 严重 | {issue[:60]} | 修改对应章节，补充论证 |"
                )

        for key in ["innovation", "method", "norm"]:
            r = results.get(key, {})
            for w in r.get("weaknesses", [])[:2]:
                if w not in [i[:60] for i in severities.get(key, [])]:
                    priority_rows.append(
                        f"| 🟡 建议 | {w[:60]} | 参考下方评审建议 |"
                    )

        if not priority_rows:
            priority_rows.append("| — | 无 | — |")

        priority_table = "\n".join(priority_rows)

        # 检查清单
        all_suggestions = []
        for key in ["innovation", "method", "norm"]:
            r = results.get(key, {})
            for s in r.get("suggestions", []):
                all_suggestions.append(f"- [ ] {s}")
        checklist = "\n".join(all_suggestions[:10]) if all_suggestions else "- [ ] （无具体建议）"

        # 填充模板
        report = REPORT_TEMPLATE.format(
            timestamp=now,
            topic=thesis.topic,
            word_count=word_count,
            chapter_count=len(thesis.chapters),
            ref_count=len(thesis.references),
            score_table=score_table,
            weighted_total=weighted_total,
            final_verdict=final_verdict,
            innovation_report=self._format_agent_report(innovation, "创新性"),
            method_report=self._format_agent_report(method, "方法"),
            norm_report=self._format_agent_report(norm, "规范性"),
            critical_summary=critical_summary,
            priority_table=priority_table,
            checklist=checklist,
        )

        if errors:
            report += f"\n\n---\n⚠️ **评审异常**：以下 Agent 未能完成评审：\n"
            for e in errors:
                report += f"- {e}\n"

        return report

    @staticmethod
    def _format_agent_report(result: Dict, dimension: str) -> str:
        """格式化单个 Agent 的评审详情

        Args:
            result: 评审结果字典
            dimension: 维度名称

        Returns:
            str: 格式化文本
        """
        if not result:
            return f"*{dimension}评审不可用*"

        parts = []

        # 子项得分
        scores = result.get("scores", {})
        if scores:
            parts.append("| 子项 | 得分 |")
            parts.append("|------|------|")
            for k, v in scores.items():
                parts.append(f"| {k} | {v}/10 |")
            parts.append(f"| **总分** | **{result.get('total', 'N/A')}/10** |")
            parts.append("")

        # 优点
        strengths = result.get("strengths", [])
        if strengths:
            parts.append("**优点**：")
            for s in strengths:
                parts.append(f"- ✅ {s}")
            parts.append("")

        # 不足
        weaknesses = result.get("weaknesses", [])
        if weaknesses:
            parts.append("**不足**：")
            for w in weaknesses:
                parts.append(f"- ⚠️ {w}")
            parts.append("")

        # 建议
        suggestions = result.get("suggestions", [])
        if suggestions:
            parts.append("**改进建议**：")
            for s in suggestions:
                parts.append(f"- 💡 {s}")
            parts.append("")

        # 摘要
        summary = result.get("summary", "")
        if summary:
            parts.append(f"**评审意见**：{summary}")
            parts.append("")

        return "\n".join(parts)
