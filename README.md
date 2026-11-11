# 论文自动生成系统 (Thesis Auto Generator)

> **English TL;DR**: A graduation-thesis writing engine that turns a topic and keywords into a DOCX manuscript with real-reference lookup, three-line tables, and a three-agent blind review. The committed `docs/system-report.md` records three historical end-to-end generations and a 189/189 test run; this U1 pass re-ran the test suite locally but did **not** re-run generation (it needs a DeepSeek API key and 3–4 minutes per thesis).

[![CI](https://github.com/aidless/thesis_auto_generator/actions/workflows/checks.yml/badge.svg)](https://github.com/aidless/thesis_auto_generator/actions/workflows/checks.yml)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **AI 学术写作引擎 v2.2** — 输入主题 + 关键词，自动生成毕业论文

## 功能

- 📋 **大纲生成**: LLM 自动生成完整论文章节结构
- ✍️ **逐章生成**: 上下文连贯的正文 + 强制表格呈现 + 论证句式优化
- 📚 **真实文献**: Semantic Scholar / Crossref API 检索 + LRU 缓存 + 关键词智能过滤
- 🎓 **多智能体盲审**: 创新性 / 方法 / 规范性三 Agent 并行评审 + 证据注入联动
- 🕸️ **知识图谱**: NetworkX PageRank + 社区检测 + 批判性综述
- 📊 **统计洞察**: StatsEngine 检验推荐 + APA 表述 + 可复现检查
- 🔍 **查重预检**: SimHash + 句向量 + 内部自比对
- 📄 **DOCX 输出**: 三线表 / 公式渲染 / 图表 / 多模板 / 水印 / 免责声明
- 🤖 **AI 参与度标记**: A/B/C 三层级段落标记

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env  # 填入 DEEPSEEK_API_KEY

# 图形界面
python app.py

# 命令行一键生成
python app.py --headless --topic "你的论文主题" --keywords "关键词" --review

# 环境体检
python app.py --check
```

## 测试

```bash
python -m pytest tests/ -v  # 189 tests
```

## Results（真实数字）

以下数字全部来自已提交的 `docs/system-report.md`（2026-06-08 实测，189/189 测试通过），
本 README 未重新跑生成链路（需 DeepSeek API key，单篇 3–4 分钟）。

**三次真实端到端生成**（同一主题「码头船只出行管理」）：

| 指标 | 第 1 次 (v2.0) | 第 2 次 (v2.0) | 第 3 次 (v2.1) |
|------|:---:|:---:|:---:|
| 总字数 | 17,056 | 17,486 | **18,809** |
| 总耗时 | 201s | 207s | **256s** |
| DOCX 表格数 | 0 | 1 | **6** |
| 含论证句式 | N/A | N/A | **3/6** |
| 空洞表达 | N/A | N/A | **0** |
| 参考文献 | 16 | 15 | 12* |
| 成本 | ¥0.06 | ¥0.05 | ¥0.06 |

*\*第 3 次 Semantic Scholar 连续 429 限流，非代码问题*

**多智能体盲审评分**（同一 v2.1 产物）：

| Agent | 评分 | 判定 | 关键意见 |
|-------|:---:|------|----------|
| 创新性 | 16/10 | reject | 「未提出新的科学问题或理论模型，是工程项目描述」 |
| 方法 | 32/10 | major_revision | 「缺乏对比实验，数据呈现 8/10（新维度生效）」 |
| 规范性 | 27/10 | major_revision | 「参考文献列表缺失，逻辑结构 8/10」 |

盲审 Agent 能诚实区分「工程报告」与「学术研究」，不输出模板化好评——这是本系统
刻意保留的行为（评分权重未向「好看」校准）。

**成本**：单篇 ≈ ¥0.05–0.06（~32k token：输入 ~8–10k，输出 ~22–24k；DeepSeek 输入 ¥1/百万、输出 ¥2/百万）。

## Limits（限制与适用边界）

- **严禁将生成内容直接作为学位论文提交**。本工具定位是论文初稿生成与学术质量自检，
  盲审结果（上表）本身就给出了 reject / major_revision 判定。
- LLM 可能编造实验数据；Prompt 已要求「引用真实数据」但无法完全杜绝，使用者必须逐条核实。
- Semantic Scholar 免费 API 限流（429）时依赖 Crossref 回退 + LRU 缓存；文献数可能因此减少。
- 图表中文显示依赖系统字体；sentence-transformers 首次下载约 500MB（轻量 SimHash 回退不依赖模型）。
- Python 3.13 需手动 patch pyaudioop，`check_env.py` 会给出修复命令。
- 生成产物不入库：`data/output/` 在 `.gitignore` 中，仓库内没有示例 docx。
- 完整限制表与改进方向见 `docs/system-report.md` §9。

## 成本

DeepSeek API: ~¥0.06 / 篇 (15,000字)

## U1 results table (recomputed 2026-11-11)

The values below are parsed live from the committed report, not from memory;
each row cites the exact source line. The historical generation numbers are
**not** re-measured in this pass.

| Metric | Values (runs 1 / 2 / 3) | Source (path:line) |
|---|---|---|
| 总字数 (3 次)  | 17,056 / 17,486 / 18,809 | `docs/system-report.md:196` |
| 总耗时 (s, 3 次) | 201 / 207 / 256 | `docs/system-report.md:197` |
| 含表格章节 (3 次) | 0/6 / 4/7 / 3/6 | `docs/system-report.md:198` |
| DOCX 表格数 (3 次) | 0 / 1 / 6 | `docs/system-report.md:199` |
| 参考文献数 (3 次) | 16 / 15 / 12 | `docs/system-report.md:202` |

Blind-review scores on the v2.1 output (same report):

| Dimension | Score | Verdict | Source (path:line) |
|---|---|---|---|
| 创新性 | 16/10 | `reject` | `docs/system-report.md:211` |
| 方法 | 32/10 | `major_revision` | `docs/system-report.md:212` |
| 规范性 | 27/10 | `major_revision` | `docs/system-report.md:213` |

| Live check | Value | Source |
|---|---|---|
| Unit tests, executed for this pass | **189 passed in 1.37s** | `python3 -m pytest tests/ -q` (exit 0) |
| Test files under `tests/` | 6 | live `glob test_*.py` |
| Report header test count | `189/189` | `docs/system-report.md:3` |

**Quickstart command actually executed for this pass**:

```bash
python3 -m pytest tests/ -q
# 189 passed in 1.37s
```

**NOT YET MEASURED in this pass**: an end-to-end thesis generation. It needs a
DeepSeek API key, costs about ¥0.05–0.06 and 3–4 minutes per thesis
(`docs/system-report.md:225`); the three runs above are historical records.
Reproduce with an API key:

```bash
python3 -m pip install -r requirements.txt
python3 check_env.py
python3 run_e2e_v3.py --topic "<topic>" --keywords "<kw>" --review
```

<!-- figure: pending real measurement -->
