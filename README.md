# 论文自动生成系统 (Thesis Auto Generator)

> **English TL;DR**: A graduation-thesis writing engine that turns a topic and keywords into a DOCX manuscript with real-reference lookup, three-line tables, and a three-agent blind review. The committed `docs/system-report.md` records three historical end-to-end generations and a 189/189 test run; this U1 pass re-ran the test suite locally but did **not** re-run generation (it needs a DeepSeek API key and 3–4 minutes per thesis).

[![CI](https://github.com/aidless/thesis_auto_generator/actions/workflows/checks.yml/badge.svg)](https://github.com/aidless/thesis_auto_generator/actions/workflows/checks.yml)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **AI 学术写作引擎 v2.2** — 输入主题 + 关键词，自动生成毕业论文初稿

---

## 这个项目解决什么问题

写一篇毕业论文章节多、文献杂、格式严、还有重复率与统计表述要求。人工起稿
要数天到数周；而市面上「论文生成器」大多只是让 LLM 吐字，产出的东西既没有
真实文献支撑，也没有学术格式，更不会做质量自检。

本项目把「起稿 → 找文献 → 写正文 → 排格式 → 盲审 → 统计表述 → 查重预检」
整条链路做成一台可复跑的引擎：**输入主题 + 关键词，自动产出带真实文献、
三线表、公式、图表、盲审报告和统计建议的 .docx 初稿**，单篇成本约 ¥0.06。

## 为什么重要

它把「AI 写作」从「生成文本」推进到「生成一份**有结构、有来源、有自检**
的学术初稿」：

- **真实文献**：Semantic Scholar / Crossref 检索 + LRU 缓存 + 关键词过滤，
  不靠 LLM 编造引用。
- **多智能体盲审**：创新性 / 方法 / 规范性三 Agent 并行评审 + 证据注入联动，
  能诚实地区分「工程报告」和「学术研究」（实测盲审给「工程项目描述」打
  reject，不给模板化废话）。
- **统计洞察**：StatsEngine 做检验推荐 + APA 表述 + 可复现检查。
- **格式合规**：三线表 / 公式渲染 / 图表 / 多模板 / 水印 / 免责声明。
- **AI 参与度标记**：A/B/C 三层级段落标记，让生成痕迹可追踪。

## 我用了什么方法

- **大纲生成**：LLM 生成论文章节结构，再逐章生成上下文连贯正文，强制表格呈现
  与论证句式。
- **检索管线**：Semantic Scholar（带 429 指数退避）→ Crossref 回退 → LRU 缓存，
  关键词智能过滤。
- **知识图谱**：NetworkX PageRank + 社区检测 + 批判性综述。
- **查重预检**：SimHash + 句向量 + 内部自比对（含轻量 SimHash 回退，不依赖
  sentence-transformers 模型）。
- **异步模式**：Celery + Redis 后台生成，前端轮询进度（P1 新增）。

## 结果如何

`docs/system-report.md` 记录了三次真实端到端实测（v2.0→v2.1），关键数字：

| 指标 | 第 1 次 (v2.0) | 第 2 次 (v2.0) | 第 3 次 (v2.1) |
|------|:---:|:---:|:---:|
| 总字数 | 17,056 | 17,486 | **18,809** |
| 总耗时 | 201s | 207s | **256s** |
| DOCX 表格数 | 0 | 1 | **6** |
| 参考文献 | 16 | 15 | 12* |
| 成本 | ¥0.06 | ¥0.05 | ¥0.06 |

*\*第 3 次 Semantic Scholar 连续 429 限流，非代码问题*

盲审实测：创新性 **16/10 reject**（"未提出新的科学问题或理论模型，是工程项目
描述"）、方法 **32/10 major_revision**、规范性 **27/10 major_revision** ——
盲审 Agent 诚实且具体。

测试套件：**189/189 通过**（`python -m pytest tests/ -q`）。

## 边界（证明什么 / 不证明什么）

**证明什么：**
- 引擎能在给定主题 + 关键词下，端到端产出**结构完整、含真实文献与格式合规**
  的 .docx 初稿（三次实测 + 189 项单测佐证）。
- 盲审 Agent 能区分「工程报告」与「学术研究」，且不给模板化废话。

**不证明什么：**
- 不证明生成内容达到**学位论文提交质量**——系统明确声明「严禁将生成内容直接
  作为学位论文提交」，它只是**初稿生成与质量自检工具**（见 `SECURITY.md` 与
  `docs/system-report.md` 伦理声明）。
- 不保证 LLM **不编造实验数据**：Prompt 已要求"引用真实数据"，但无法完全杜绝
  （见 `docs/system-report.md` §9 已知限制）。
- 三次实测是**单一主题**（码头船只出行管理）的样本，不代表任意学科/任意长度
  的普适性能。
- 统计检验推荐与 APA 表述是**辅助**，最终统计结论须由研究者自行核实。

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

> **依赖坑**：`gradio` 4.44 依赖 `huggingface_hub` 的 `HfFolder`，该符号在
> `hub>=1.0` 被移除。若 `check_env.py` 报「gradio 未安装」而 pip 显示已装，
> 执行 `pip install 'huggingface_hub<1.0'`（CI 的 `mutation-control` job 验证了
> 这一点）。

## 测试与可复算

```bash
python -m pytest tests/ -q           # 189 项单测，全部通过
python check_env.py                  # 环境自检（含 gradio 依赖坑检测）
```

- 上述 189 项来自 `tests/` 下 6 个测试文件，纯离线、无需 API key。
- `docs/system-report.md` §5 的三次实测数字来自 `run_e2e_v3.py` 的端到端跑批
  （需真实 DeepSeek key 才能复现，成本约 ¥0.06/篇）；该脚本在仓库内可直接
  运行：`python run_e2e_v3.py`。

## 目录结构

```
app.py                    # Gradio GUI / CLI 入口（--headless / --check）
check_env.py              # 环境自检（依赖完整性 / 文件 / API key）
config.py                 # 配置加载（.env + 默认值）
core/
  outline_generator.py    # 大纲生成
  chapter_generator.py    # 逐章正文生成（表格 / 论证句式）
  reference_fetcher.py    # Semantic Scholar / Crossref 检索 + 缓存
  review_engine.py        # 三 Agent 并行盲审
  knowledge_graph.py      # NetworkX PageRank + 社区检测
  stats_engine.py         # 统计检验推荐 + APA 表述 + 可复现检查
  docx_formatter.py       # 三线表 / 公式 / 图表 / 水印 / 免责声明
  template_parser.py      # .docx 模板解析
  models.py               # GenerationConfig / Thesis 数据类
llm/                      # DeepSeek / OpenAI 客户端抽象
prompts/                  # 大纲 / 章节 / 文献 / 盲审 prompt
ui/                       # Gradio 组件 / tabs / 回调
tests/                    # 189 项单测（离线）
data/templates/           # 内置 .docx 模板
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

DeepSeek API: ~¥0.06 / 篇 (15,000字)，总 Token 约 32,000–34,000
（详见 `docs/system-report.md` §5.3）。

## 参考

- `docs/system-report.md`：完整使用报告与系统说明（含实测性能、架构、已知限制）
- `CHANGELOG.md` / `SECURITY.md`：版本与安全声明

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

## 验收题库与复算

`eval/cases.jsonl` 是 20 条可执行验收题：15 条 `expr` + 3 条 `raises`（共 18 条**真调本仓库 API**）
加 2 条 `doc`（真读仓内文件）。覆盖的口径：字数与章节拆分、GB/T 7714 与 BibTeX 引用格式、
章节状态机与进度、统计设计检查与 t 检验、模板预设与损坏模板回退、知识图谱统计、检索技术词过滤、
Markdown 三线表解析、字数分配、`tests/` 套件规模（ast 计数）、LLM 提供商校验、数据文件格式校验、
端到端报告数字与依赖钉版。期望值都是跑出来的，不是抄文档——改一行实现就可能变红。

```bash
python3 eval/run_cases.py            # 20/20 cases passed，退出码 0
python3 eval/run_cases.py --save     # 顺带把结果写进 eval/run-report.json
python3 eval/run_cases.py --selftest # 篡改一条期望值，必须变红（19/20，证明这套题会失败）
```

**数字如何复算**：`eval/run-report.json` 里每条 case 带 `id` / `axis` / `detail`，把 `detail`
与 `cases.jsonl` 的 `verify` 代码对着看，就能从源码复现该数字——例如 `STA-03` 的
`3.674|10|2.12` 就是 `StatsEngine.run_test` 在固定样本上的 `statistic|df|cohens_d`；
`--save` 重跑一次即可重建整份报告，不需要手工抄数。

**失败归因**：`run_cases.py` 不只报通过率，失败时按 `axis` 汇总（例如
`text/字数统计: 1 条 —— TXT-01`），直接指出是哪个模块的哪个口径坏了。新增题目沿用同一规则：
一个 axis 最多 3 条，`source` 必须指向真实存在的实现或数据文件。
