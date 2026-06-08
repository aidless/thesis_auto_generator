# 论文自动生成系统 (Thesis Auto Generator)

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

## 成本

DeepSeek API: ~¥0.06 / 篇 (15,000字)
