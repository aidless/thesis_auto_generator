# 论文自动生成系统 (Thesis Auto Generator)

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

## 成本

DeepSeek API: ~¥0.06 / 篇 (15,000字)，总 Token 约 32,000–34,000
（详见 `docs/system-report.md` §5.3）。

## 参考

- `docs/system-report.md`：完整使用报告与系统说明（含实测性能、架构、已知限制）
- `CHANGELOG.md` / `SECURITY.md`：版本与安全声明
