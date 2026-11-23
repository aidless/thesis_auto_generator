# PREREG — thesis_auto_generator v2.2

> 状态：**未证实**。下面的端到端假设没有仓库内的日志、token 账本、盲审原文或输出 DOCX 可以复算。当前唯一离线结果是 README 里由 `make check` 复算的表。

## 当初想回答的问题

给定主题和关键词，这个程序能否产出一份可以提交的学位论文，并且文献、费用和盲审都站得住。

## 现在能说的

不能。程序会写出带水印的 DOCX 初稿。严禁将生成内容直接作为学位论文提交。本系统不能防止编造数据，也不能防止抄袭。

`docs/system-report.md` 仍保留三次历史运行的叙述。那些数字不是本文件的成功标准。缺什么证据，见 `FAILURE_MODES.md`。

## 离线判据

`make check` 退出码为 0。它重跑 `tests/`，并核对 README 表。它不调用 DeepSeek、Semantic Scholar 或 Crossref，也不需要 API key。
