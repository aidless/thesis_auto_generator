"""
论文自动生成系统 - Gradio 入口

本文件是系统的 GUI 入口点，负责：
1. 加载配置
2. 构建 Gradio UI
3. 启动 Web 服务

工作流：
Tab1(输入) → Tab2(大纲) → Tab3(章节) → Tab4(下载)

支持模式：
- 同步模式（默认）：浏览器保持连接，实时生成
- 异步模式（--async）：后台 worker 生成，前端轮询进度
- 检查模式（--check）：环境自检 + Mock 链路测试，完成后退出
- 无头模式（--headless）：命令行一键生成论文 + 盲审报告，不启动 Web 服务
"""

import sys
import os
import time
import argparse

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import gradio as gr

from config import load_config
from ui.tabs import build_ui


def create_app(use_async: bool = False) -> gr.Blocks:
    """创建完整的 Gradio 应用

    Args:
        use_async: 是否启用异步生成模式（P1 新增）

    Returns:
        gr.Blocks: 配置好的 Gradio 应用实例
    """
    config = load_config()
    if use_async:
        config.async_mode = True
    app = build_ui(config)
    return app


def run_headless_mode(args) -> int:
    """命令行一键生成模式

    不启动 Gradio，直接走完整生成 + 盲审流程。
    实时输出进度到终端。

    Returns:
        int: 0 成功, 1 失败
    """
    import re
    from config import load_config
    from llm.base import create_llm_client
    from core.outline_generator import OutlineGenerator
    from core.chapter_generator import ChapterGenerator
    from core.reference_fetcher import ReferenceFetcher
    from core.docx_formatter import DocxFormatter
    from core.models import Thesis, TemplateStyles
    from core.review_engine import ReviewEngine
    from utils.watermark import add_watermark_and_disclaimer
    from utils.text_utils import estimate_word_count

    topic = args.topic
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    discipline = args.discipline
    target_words = args.words
    output_path = args.output or "data/output/thesis_headless.docx"
    enable_review = args.review

    config = load_config()
    config.target_word_count = target_words
    config.discipline = discipline

    os.makedirs(os.path.dirname(output_path) or "data/output", exist_ok=True)

    total_start = time.time()
    stats = {"tables": 0, "reasoning": 0, "empty_phrases": 0, "words": 0}

    def progress(msg: str, current: int = -1, total: int = -1):
        if current >= 0 and total >= 0:
            bar = "█" * int(current / max(total, 1) * 20)
            print(f"\r  [{bar:<20}] {msg}", end="", flush=True)
        else:
            print(f"\n  {msg}")

    # Phase 1: Outline
    print("\n📋 生成大纲...", flush=True)
    t0 = time.time()
    llm = create_llm_client(config.llm_provider, config)
    og = OutlineGenerator(llm)
    outline = og.generate(topic, keywords, discipline, target_words)
    chapter_nodes = outline.get_chapters()
    print(f" ✅ {len(chapter_nodes)} 章 ({time.time()-t0:.0f}s)")
    for i, ch in enumerate(chapter_nodes):
        print(f"   {i+1}. {ch.title}")

    # Phase 2: Chapters
    print("\n✍️  逐章生成...", flush=True)
    cg = ChapterGenerator(llm)
    all_chapters = []
    for i, node in enumerate(chapter_nodes):
        progress(f"第 {i+1}/{len(chapter_nodes)} 章: {node.title[:25]}...", i, len(chapter_nodes))
        ch = cg.generate_chapter(outline, node, all_chapters)
        all_chapters.append(ch)
        stats["words"] += ch.word_count
        content = ch.content_markdown
        if "|" in content and "---" in content:
            stats["tables"] += 1
        if re.search(r"(因为|原因在于|选择.*理由|之所以)", content):
            stats["reasoning"] += 1
        if re.search(r"(具有重要意义|取得了良好效果|得到了广泛应用)", content):
            stats["empty_phrases"] += 1
    progress(f"全部 {len(chapter_nodes)} 章完成", -1, -1)
    total_words = stats["words"]
    print(f" ✅ {total_words:,} 字")

    # Phase 3: References
    print("\n📚 检索参考文献...", end=" ", flush=True)
    rf = ReferenceFetcher()
    refs = rf.fetch_by_keywords(keywords, limit=15, topic=topic)
    print(f"✅ {len(refs)} 篇")

    # Phase 4: DOCX
    print("📄 生成 DOCX...", end=" ", flush=True)
    thesis = Thesis(topic=topic, keywords=keywords,
        target_word_count=target_words, outline=outline,
        chapters=all_chapters, references=refs, template_styles=TemplateStyles())
    formatter = DocxFormatter()
    raw_path = output_path.replace(".docx", "_raw.docx")
    formatter.create_document(thesis, raw_path)
    add_watermark_and_disclaimer(raw_path, output_path)
    file_size = os.path.getsize(output_path)
    print(f"✅ {file_size:,} bytes")

    # Phase 5: Review (optional)
    review_path = ""
    if enable_review:
        print("\n🎓 执行盲审...", flush=True)
        engine = ReviewEngine(llm)
        engine.add_evidence("StatsEngine",
            f"本文含 {stats['tables']} 张三线表, 论证句式密度正常", "method")
        engine.add_evidence("StatsEngine",
            f"空洞表达: {stats['empty_phrases']} 处, 论证句式: {stats['reasoning']} 处", "innovation")
        result = engine.review(thesis)
        if "report_md" in result:
            review_path = output_path.replace(".docx", "_review.md")
            with open(review_path, "w", encoding="utf-8") as f:
                f.write(result["report_md"])
            # Print quick summary
            for agent_id, agent_name in [("innovation","创新性"),("method","方法"),("norm","规范性")]:
                r = result.get("results",{}).get(agent_id,{})
                verdict = r.get("verdict","N/A")
                total = r.get("total","N/A")
                print(f"  {agent_name}: {total}/10 ({verdict})")
            print(f"  ✅ 盲审报告: {review_path}")

    # Summary
    total_time = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  🎉 生成完成!")
    print(f"  {'='*60}")
    print(f"  论文: {os.path.abspath(output_path)}")
    if review_path:
        print(f"  盲审: {os.path.abspath(review_path)}")
    print(f"  字数: {total_words:,} | 耗时: {total_time:.0f}s")
    print(f"  表格: {stats['tables']} | 论证: {stats['reasoning']} | 空洞: {stats['empty_phrases']}")
    print(f"  文献: {len(refs)} 篇")
    print(f"  {'='*60}")

    return 0


def run_check_mode() -> bool:
    """运行离线体检模式

    顺序执行：
    1. check_env.py 环境自检
    2. tests/test_e2e_mock.py Mock 端到端测试

    Returns:
        bool: 全部通过返回 True
    """
    import subprocess

    print("=" * 60)
    print("  论文自动生成系统 v2.0 — 离线体检模式")
    print("  (不启动 Web 服务，仅运行诊断和测试)")
    print("=" * 60)
    print()

    # Step 1: 环境自检
    print(">>> Step 1/2: 环境自检")
    try:
        from check_env import EnvironmentChecker
        checker = EnvironmentChecker()
        env_ok = checker.run_all()
    except ImportError:
        # 回退到子进程
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "check_env.py")],
            capture_output=False,
        )
        env_ok = result.returncode == 0

    if not env_ok:
        print("\n⚠️  环境自检未通过，但继续运行 Mock 链路测试...\n")

    # Step 2: Mock 端到端测试
    print("\n>>> Step 2/2: Mock 端到端链路测试")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_e2e_mock.py", "-v", "--tb=short"],
        cwd=PROJECT_ROOT,
        capture_output=False,
    )
    e2e_ok = result.returncode == 0

    # 总结
    print()
    print("=" * 60)
    if env_ok and e2e_ok:
        print("  🎉 体检通过！环境正常，核心链路完整。")
        print("  启动命令: python app.py")
        print("=" * 60)
        return True
    else:
        status = []
        if not env_ok:
            status.append("环境检查未通过")
        if not e2e_ok:
            status.append("Mock 链路测试失败")
        print(f"  ❌ 体检未通过: {', '.join(status)}")
        print("  请根据上方错误信息修复后再启动。")
        print("=" * 60)
        return False


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(description="论文自动生成系统 v2.1")
    parser.add_argument("--async", dest="async_mode", action="store_true", help="启用异步生成模式")
    parser.add_argument("--check", dest="check_mode", action="store_true", help="离线体检模式")
    # --headless 参数
    parser.add_argument("--headless", dest="headless", action="store_true", help="命令行一键生成模式")
    parser.add_argument("--topic", type=str, default="", help="论文主题（headless 必填）")
    parser.add_argument("--keywords", type=str, default="", help="关键词，逗号分隔")
    parser.add_argument("--discipline", type=str, default="软件工程", help="学科方向")
    parser.add_argument("--words", type=int, default=15000, help="目标字数")
    parser.add_argument("--output", type=str, default="", help="输出文件路径")
    parser.add_argument("--review", action="store_true", help="生成后自动运行盲审")
    args = parser.parse_args()

    # --headless
    if args.headless:
        if not args.topic:
            print("❌ --headless 模式需要提供 --topic 参数")
            print("示例: python app.py --headless --topic \"基于Spring Boot的码头管理系统\" --review")
            sys.exit(1)
        code = run_headless_mode(args)
        sys.exit(code)

    # --check
    if args.check_mode:
        ok = run_check_mode()
        sys.exit(0 if ok else 1)

    # 正常启动模式
    config = load_config()
    if args.async_mode:
        config.async_mode = True

    print("=" * 60)
    print("  论文自动生成系统 v2.0 (P4)")
    print("  Thesis Auto Generator")
    print("=" * 60)
    print(f"  LLM 提供商: {config.llm_provider}")
    print(f"  模型: {config.llm_model}")
    print(f"  异步模式: {'✅ 开启' if config.async_mode else '❌ 关闭（同步）'}")
    print(f"  默认学科: {config.discipline}")
    print(f"  默认字数: {config.target_word_count:,}")
    print("=" * 60)
    print()
    print("  ⚠️ 伦理声明：本工具仅供学习和研究参考，")
    print("    严禁将生成内容直接作为学位论文提交。")
    print()

    app = create_app(use_async=config.async_mode)

    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
