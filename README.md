# 论文自动生成系统 v2.2

毕业论文章节多、格式严，用大模型直接续写很容易交出一份看起来像论文、却不能提交的稿子。
本仓库是本地初稿工具：主题和关键词进去，出来一份带水印的 DOCX。
严禁将生成内容直接作为学位论文提交。本系统不能防止编造数据，也不能防止抄袭。

离线 `make check` 复算下表，不调用 DeepSeek、Semantic Scholar 或 Crossref，也不需要 API key。限度：表内只有单元测试、版本，以及 git 是否跟踪了生成日志；它不测量成稿质量，不证明文献真实，也不证明费用或盲审分数。

<!-- CHECK:BEGIN -->
| key | value |
| --- | --- |
| unittest_passed | 189 |
| unittest_failed | 0 |
| unittest_errors | 0 |
| unittest_skipped | 0 |
| test_files | 6 |
| test_functions | 189 |
| tracked_output_files | 0 |
| tracked_e2e_logs | 0 |
| tracked_review_files | 0 |
| ethics_clauses | 3 |
| app_version | 2.2 |
<!-- CHECK:END -->

[![CI](https://github.com/aidless/thesis_auto_generator/actions/workflows/checks.yml/badge.svg)](https://github.com/aidless/thesis_auto_generator/actions/workflows/checks.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 复算

```bash
make check
```

第一次运行若缺少文档库或 dotenv，Makefile 会按 `requirements-check.txt` 安装。在线生成脚本和环境诊断都不是这个结果，说明见 `FAILURE_MODES.md`。

## 撤回

历史生成的字数、耗时、表格数、文献数、费用和盲审分数已从本页撤回。原因、缺哪些文件、以及 `docs/system-report.md` 里留下的叙述，写在 `FAILURE_MODES.md`。

## 代码在哪

- `config.py` 的 `APP_VERSION` 是唯一版本字符串
- `utils/watermark.py` 把水印和免责声明写进 DOCX
- `tests/` 是上表的单元测试，使用预制响应，不访问模型 API
- `core/reference_fetcher.py` 是文献客户端，本检查不调用它
