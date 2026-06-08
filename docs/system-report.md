# 论文自动生成系统 — 使用报告与系统说明

> **版本**：v2.2 | **日期**：2026-06-08 | **测试**：189/189 | **仓库**：[github.com/aidless/thesis_auto_generator](https://github.com/aidless/thesis_auto_generator)

---

## 目录

1. [系统概述](#1-系统概述)
2. [快速开始](#2-快速开始)
3. [三种运行模式](#3-三种运行模式)
4. [功能清单](#4-功能清单)
5. [实测性能数据](#5-实测性能数据)
6. [架构概览](#6-架构概览)
7. [盲审系统说明](#7-盲审系统说明)
8. [命令行参考](#8-命令行参考)
9. [已知限制与改进方向](#9-已知限制与改进方向)

---

## 1. 系统概述

**论文自动生成系统**是一台 AI 驱动的学术写作引擎。用户输入论文主题和关键词，系统调用 DeepSeek 大语言模型自动生成完整的毕业论文，包括大纲、分章节正文、真实参考文献、三线表、图表、公式等学术论文全部要素。

本系统面向 **2026 届软件工程专业毕业生**（专升本层次），可作为论文初稿生成和学术质量自检工具。严禁将生成内容直接作为学位论文提交。

### 核心能力一句话总结

```
输入主题 → 自动生成大纲 → 逐章撰写正文（带表格+论证）→ 检索真实文献 → 输出格式化的 .docx
→ 三位 AI Agent 并行盲审 → 输出修改建议 → 6 分钱/篇
```

---

## 2. 快速开始

### 2.1 环境要求

| 项 | 要求 |
|----|------|
| Python | 3.10 - 3.13 |
| 操作系统 | Windows / macOS / Linux |
| 网络 | 需要访问 api.deepseek.com |
| 磁盘 | ~2GB（含 sentence-transformers 模型） |

### 2.2 安装

```bash
# 1. 克隆仓库
git clone https://github.com/aidless/thesis_auto_generator.git
cd thesis_auto_generator

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key（从 platform.deepseek.com 获取）
# DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx

# 4. 环境体检（确认一切就绪）
python app.py --check
```

体检通过后输出：
```
🎉 体检通过！环境正常，核心链路完整。
启动命令: python app.py
```

### 2.3 获取 DeepSeek API Key

1. 访问 [platform.deepseek.com](https://platform.deepseek.com)
2. 注册账号 → API Keys → 创建新 Key
3. 新用户赠送免费额度（足够生成几十篇论文）
4. 将 Key 填入 `.env` 的 `DEEPSEEK_API_KEY=` 后面

---

## 3. 三种运行模式

### 模式 A：Gradio 图形界面（交互式编辑）

```bash
python app.py
```

浏览器打开 `http://localhost:7860`，6 个 Tab 页面：

| Tab | 功能 |
|-----|------|
| 🚀 开始生成 | 输入主题、关键词、选择模板、上传数据、开启异步模式 |
| 📋 大纲预览 | 查看/编辑 AI 生成的大纲，输入反馈重新生成 |
| ✍️ 章节编辑 | **双栏**：左侧 Markdown 编辑，右侧实时 Word 预览，逐章确认 |
| 📥 下载成果 | 下载完整 .docx / 大纲 .md / 参考文献 .bib / 格式检查 |
| 📊 历史管理 | SQLite 持久化的生成历史，支持重新下载 |
| 🎓 模拟盲审 | 三 Agent 并行评审 + 统计洞察 + 查重预检 |

### 模式 B：命令行一键生成（`--headless`）

不需要打开浏览器，一条命令从主题到论文初稿：

```bash
# 仅生成论文
python app.py --headless \
  --topic "基于Spring Boot的码头船只出行管理系统设计与实现" \
  --keywords "Spring Boot,码头管理,船只调度,Java"

# 生成论文 + 盲审报告
python app.py --headless \
  --topic "基于深度学习的图像分类研究" \
  --keywords "深度学习,CNN,图像分类,ResNet" \
  --words 15000 \
  --review
```

输出示例：
```
📋 生成大纲... ✅ 6 章 (16s)
✍️  逐章生成... ✅ 18,809 字
📚 检索参考文献... ✅ 12 篇
📄 生成 DOCX... ✅ 72,936 bytes
🎓 执行盲审...
  创新性: 16/10 (reject)
  方法: 32/10 (major_revision)
  规范性: 27/10 (major_revision)

============================================================
  🎉 生成完成!
  论文: data/output/thesis_headless.docx
  盲审: data/output/thesis_headless_review.md
  字数: 18,809 | 耗时: 256s
  表格: 4 | 论证: 3 | 空洞: 0
============================================================
```

### 模式 C：体检模式（`--check`）

不启动服务，仅运行诊断：

```bash
python app.py --check
```

检查项：Python 版本 → 依赖完整性 → 关键文件存在性 → API Key 配置 → Mock 端到端测试（6 项，10 秒内完成）

---

## 4. 功能清单

### 按版本迭代的功能矩阵

| 功能 | v1.0 MVP | v1.1 P1 | v1.2 P2 | v1.3 P3 | v2.0 P4 | v2.2 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 大纲生成 | ✅ | | | | | ✅ |
| 逐章生成 | ✅ | | | | | ✅ |
| MD→DOCX 转换 | ✅ | | | | | ✅ |
| 模板解析 | ✅ | | | | | ✅ |
| Gradio GUI | ✅ | | | | | ✅ |
| 伦理护栏（水印+声明） | ✅ | | | | | ✅ |
| 参考文献检索 | | ✅ | | | | ✅ |
| 逐章编辑器（双栏） | | ✅ | | | | ✅ |
| 三线表 | | ✅ | | | | ✅ |
| 目录自动更新 | | ✅ | | | | ✅ |
| 异步任务（Celery） | | ✅ | | | | ✅ |
| 用户上传 Excel/CSV | | ✅ | | | | ✅ |
| 图表生成（matplotlib） | | | ✅ | | | ✅ |
| LaTeX 公式渲染 | | | ✅ | | | ✅ |
| 多模板（3套预设） | | | ✅ | | | ✅ |
| SQLite 历史管理 | | | ✅ | | | ✅ |
| 格式对比报告 | | | ✅ | | | ✅ |
| 多智能体盲审 | | | | ✅ | | ✅ |
| 文献知识图谱 | | | | ✅ | | ✅ |
| 批判性综述 | | | | ✅ | | ✅ |
| 统计洞察（StatsEngine） | | | | | ✅ | ✅ |
| 查重预检 | | | | | ✅ | ✅ |
| AI 参与度标记 | | | | | ✅ | ✅ |
| 证据注入联动 | | | | | ✅ | ✅ |
| 论证句式优化 | | | | | | ✅ |
| 空洞表达过滤 | | | | | | ✅ |
| 文献相关性过滤 | | | | | | ✅ |
| 盲审表格检查维度 | | | | | | ✅ |
| `--headless` 模式 | | | | | | ✅ |
| `--check` 体检模式 | | | | | | ✅ |

---

## 5. 实测性能数据

### 5.1 三次真实端到端测试对比

| 指标 | 第 1 次 (v2.0) | 第 2 次 (v2.0) | 第 3 次 (v2.1) |
|------|:---:|:---:|:---:|
| 主题 | 码头船只出行管理 | 码头船只出行管理 | 码头船只出行管理 |
| 总字数 | 17,056 | 17,486 | **18,809** |
| 总耗时 | 201s | 207s | **256s** |
| 含表格章节 | 0/6 | 4/7 | **3/6** |
| DOCX 表格数 | 0 | 1 | **6** |
| 含论证句式 | N/A | N/A | **3/6** |
| 空洞表达 | N/A | N/A | **0** |
| 参考文献 | 16 | 15 | 12* |
| 成本 | ¥0.06 | ¥0.05 | ¥0.06 |

*\*第 3 次 Semantic Scholar 连续 429 限流，非代码问题*

### 5.2 盲审评分

| Agent | 评分 | 判定 | 关键意见 |
|-------|:---:|------|----------|
| 创新性 | 16/10 | reject | "未提出新的科学问题或理论模型，是工程项目描述" |
| 方法 | 32/10 | major_revision | "缺乏对比实验，数据呈现 8/10（新维度生效）" |
| 规范性 | 27/10 | major_revision | "参考文献列表缺失，逻辑结构 8/10" |

**结论**：盲审 Agent 诚实且具体，能区分"工程报告"和"学术研究"，不输出模板化废话。

### 5.3 成本分析

```
总 Token ≈ 32,000-34,000 / 篇
输入 Token ≈ 8,000-10,000
输出 Token ≈ 22,000-24,000

DeepSeek 定价：输入 ¥1/百万 token，输出 ¥2/百万 token
单篇成本 ≈ ¥0.05-0.06
```

| 对比 | DeepSeek | GPT-4o（预估） |
|------|---------|---------------|
| 单篇成本 | ¥0.06 | ¥1.50 |
| 生成速度 | 3-4 分钟 | 2-3 分钟 |
| 中文质量 | 优秀 | 优秀 |
| API 稳定性 | 偶尔 429 | 稳定 |

---

## 6. 架构概览

### 6.1 项目结构

```
thesis_auto_generator/          64 files, 12,862 lines
│
├── app.py                      入口：Gradio GUI + --headless + --check
├── check_env.py                 环境自检脚本（彩色中文诊断）
├── config.py                    集中配置（环境变量 + 默认值）
├── tasks.py                     异步任务引擎（双模式）
├── requirements.txt             18 个依赖包
│
├── core/                        核心业务逻辑层（15 files）
│   ├── models.py                    所有数据类（Thesis/Outline/Chapter/Reference/...）
│   ├── outline_generator.py         大纲生成（LLM → Outline 树）
│   ├── chapter_generator.py         章节生成（上下文传递 + 字数分配）
│   ├── reference_fetcher.py         文献检索（Semantic Scholar/Crossref + LRU缓存 + 指数退避）
│   ├── template_parser.py           模板解析 + 3套预设模板
│   ├── docx_formatter.py            MD→DOCX 转换（三线表/公式/图表/目录）
│   ├── charts.py                    matplotlib 图表生成（柱状/折线/饼图）
│   ├── formula_renderer.py          LaTeX → PNG 公式渲染
│   ├── data_importer.py             Excel/CSV 数据导入
│   ├── review_engine.py             3 Agent 并行盲审 + 证据注入
│   ├── knowledge_graph.py           NetworkX 文献知识图谱
│   ├── critical_reviewer.py         批判性综述生成
│   ├── stats_engine.py              统计洞察（检验推荐+APA表述+可复现检查）
│   ├── history_store.py             SQLite 历史持久化
│   └── __init__.py
│
├── llm/                         LLM 适配器层（3 files）
│   ├── base.py                     BaseLLMClient 抽象
│   ├── deepseek_client.py          DeepSeek 适配器
│   └── openai_client.py            OpenAI 适配器
│
├── prompts/                     Prompt 模板层（4 files）
│   ├── chapter_prompts.py          章节生成 Prompt（含表格强制/论证深度/空洞禁用）
│   ├── outline_prompts.py          大纲生成 Prompt
│   ├── reference_prompts.py        文献引用 Prompt 模板
│   └── reviewer_prompts.py         3 种盲审角色 System Prompt
│
├── ui/                          Gradio UI 层（3 files）
│   ├── tabs.py                     6 个 Tab 页面定义
│   ├── callbacks.py                事件回调 + 工作流编排（820+ lines）
│   └── components.py               可复用 UI 组件
│
├── utils/                       工具层（5 files）
│   ├── watermark.py                水印 + 免责声明 + AI 参与度标记
│   ├── plagiarism_checker.py       SimHash + 句向量 + 内部自比对
│   ├── format_checker.py           格式差异对比
│   ├── text_utils.py               文本工具
│   └── file_utils.py               文件工具
│
├── tests/                       测试层（6 files, 189 tests）
│   ├── test_e2e_mock.py            Mock 端到端测试（6 tests, 核心链路）
│   ├── test_models.py
│   ├── test_config.py
│   ├── test_file_utils.py
│   ├── test_text_utils.py
│   └── test_template_parser.py
│
└── data/
    ├── templates/                  DOCX 模板文件
    └── output/                     生成产物（被 .gitignore 排除）
```

### 6.2 核心数据流

```
用户输入(topic, keywords)
  │
  ▼
OutlineGenerator ──LLM──→ Outline (大纲树)
  │
  ▼
ChapterGenerator ──LLM(+上下文)──→ Chapter[] (Markdown章节)
  │
  ▼
ReferenceFetcher ──API──→ Reference[] (真实文献)
  │
  ▼
DocxFormatter ──python-docx──→ .docx (三线表/公式/图表/目录/水印)
  │
  ▼ (可选)
ReviewEngine ──3×LLM Agent──→ blind_review.md
```

---

## 7. 盲审系统说明

### 7.1 三个评审 Agent

| Agent | 角色 | Model Temp | 评分维度 |
|-------|------|:---:|------|
| 创新性 | 评估研究新颖性和学术贡献 | 0.3 | 新颖性 / 明确性 / 差异度 / 价值 |
| 方法 | 评估实验设计和方法严谨性 | 0.2 | 实验设计 / 数据代表 / 指标规范 / 可复现 / **数据呈现** |
| 规范性 | 评估写作规范性和可读性 | 0.1 | 引用完整 / 逻辑连贯 / 术语一致 / 结构合理 |

- 三个 Agent **并行**运行，总耗时约 10-15 秒
- 每个 Agent 输出结构化 JSON（含评分、优缺点、严重问题、修改建议、判定）
- 引擎汇总生成 Markdown 格式盲审报告

### 7.2 证据注入联动

系统支持在评审前自动注入检测结果作为评审参考：

```python
engine.add_evidence("StatsEngine", "本文含 6 张三线表，20 处表格引用", "method")
engine.add_evidence("PlagiarismChecker", "内部 SimHash 自检未发现高度相似段落", "norm")
```

证据只提供事实，不做结论。Agent 独立判断是否采纳。

### 7.3 盲审报告输出路径

- GUI 模式：Tab6 显示，可复制
- `--headless --review`：`data/output/<论文名>_review.md`
- 报告包含：总分表、分项详情、关键问题汇总、修改优先级表、检查清单

---

## 8. 命令行参考

### app.py 完整参数

```
python app.py [选项]

模式选择（三选一）：
  (默认)              启动 Gradio Web 界面
  --headless           命令行一键生成模式
  --check              离线体检测试模式

--headless 模式参数：
  --topic TEXT         论文主题（必填）
  --keywords TEXT      关键词，逗号分隔
  --discipline TEXT    学科方向（默认：软件工程）
  --words INT          目标字数（默认：15000）
  --output PATH        输出文件路径（默认：data/output/thesis_headless.docx）
  --review             生成后自动运行盲审

其他：
  --async              启用异步生成模式（仅 GUI 模式）
```

### 常用命令示例

```bash
# 体检
python app.py --check

# GUI 模式
python app.py

# 快速出初稿（5000字，约2分钟）
python app.py --headless --topic "基于Vue的在线考试系统" --words 5000

# 标准论文（15000字，约4分钟） + 盲审
python app.py --headless \
  --topic "基于Spring Boot的码头船只出行管理系统设计与实现" \
  --keywords "Spring Boot,码头管理,Java,MySQL" \
  --review

# 学科定制
python app.py --headless \
  --topic "电商平台用户行为分析与推荐算法研究" \
  --keywords "推荐算法,协同过滤,用户行为,数据挖掘" \
  --discipline "数据科学" \
  --words 20000
```

---

## 9. 已知限制与改进方向

### 当前限制

| 限制 | 影响 | 缓解方案 |
|------|------|----------|
| Semantic Scholar 免费 API 限流 | 高频使用时返回 429 | 内置指数退避 + Crossref 回退 + LRU 缓存 |
| LLM 可能编造实验数据 | 生成内容可信度 | Prompt 已要求"引用真实数据"，但无法完全杜绝 |
| 中文字体依赖系统安装 | 图表中文可能显示方块 | 启动时自动检测字体，无合适字体时给出警告 |
| sentence-transformers 首次下载 500MB | 首次使用查重功能需等待 | 轻量回退模式（SimHash）不依赖模型 |
| Python 3.13 兼容性 | 需手动 patch pyaudioop | `check_env.py` 自动检测并给出修复命令 |

### 短期改进方向

- 增加 `--headless` 批量生成模式（一次生成多篇不同主题的论文）
- 文献知识图谱输出可视化 HTML
- 盲审评分权重可配置（贴近学校评审标准）

---

> **伦理声明**：本工具仅供学习和研究参考。严禁将生成内容直接作为学位论文提交。使用者应自行核实所有内容的准确性和原创性。
