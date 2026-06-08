"""
环境自检脚本 (check_env.py)

在启动系统前全面诊断运行环境，输出彩色中文报告。
支持独立运行或作为模块导入（`--check` 模式调用）。

检查项：
- Python 版本 (3.10-3.13)
- 所有依赖包是否已安装
- 关键文件完整性
- API Key 配置状态
- 数据目录和临时目录可写性
"""

import os
import sys
import importlib
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict

# ── 颜色输出 ──────────────────────────────────────────────

class Color:
    """终端颜色转义码"""
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def ok(cls, text: str) -> str:
        return f"{cls.GREEN}✓{cls.RESET} {text}"

    @classmethod
    def warn(cls, text: str) -> str:
        return f"{cls.YELLOW}⚠{cls.RESET} {text}"

    @classmethod
    def err(cls, text: str) -> str:
        return f"{cls.RED}✗{cls.RESET} {text}"

    @classmethod
    def title(cls, text: str) -> str:
        return f"\n{cls.BOLD}{cls.CYAN}{'='*60}{cls.RESET}\n{cls.BOLD}{cls.CYAN}  {text}{cls.RESET}\n{cls.BOLD}{cls.CYAN}{'='*60}{cls.RESET}"


# ── 项目根目录 ────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent


class EnvironmentChecker:
    """环境诊断器"""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.oks: List[str] = []
        self.fix_commands: List[str] = []

    def run_all(self) -> bool:
        """运行所有检查项

        Returns:
            bool: 是否所有关键检查通过
        """
        print(Color.title("论文自动生成系统 — 环境自检"))

        self._check_python()
        self._check_dependencies()
        self._check_key_files()
        self._check_api_key()
        self._check_dirs()
        self._check_quick_imports()

        self._print_summary()
        return len(self.errors) == 0

    # ── 单项检查 ──────────────────────────────────────────

    def _check_python(self) -> None:
        """检查 Python 版本"""
        ver = sys.version_info
        ver_str = f"Python {ver.major}.{ver.minor}.{ver.micro}"
        print(f"\n📌 检测到 {ver_str}")

        if (3, 10) <= (ver.major, ver.minor) <= (3, 13):
            self.oks.append(ver_str)
            print(Color.ok(f"{ver_str} — 兼容"))
        else:
            self.errors.append(f"Python 版本不兼容: {ver_str}，需要 3.10-3.13")
            self.fix_commands.append("安装 Python 3.10-3.13: https://python.org/downloads")
            print(Color.err(f"{ver_str} — 不兼容，需要 3.10-3.13"))

        # Python 3.13 特殊警告
        if (ver.major, ver.minor) == (3, 13):
            try:
                import audioop
                self.oks.append("Python 3.13 audioop 兼容补丁已应用")
            except ImportError:
                self.warnings.append("Python 3.13 缺少 audioop（pyaudioop shim 未安装）")
                self.fix_commands.append(
                    "pip install audioop-lts && python -c \"import audioop; print('OK')\""
                )

    def _check_dependencies(self) -> None:
        """检查 requirements.txt 中的依赖"""
        print(f"\n📦 检查依赖包...")
        req_path = PROJECT_ROOT / "requirements.txt"

        if not req_path.exists():
            self.errors.append("requirements.txt 不存在")
            print(Color.err("requirements.txt 不存在"))
            return

        with open(req_path) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

        deps: Dict[str, str] = {}
        for line in lines:
            # 解析包名
            pkg = line.split(">=")[0].split("<")[0].split("==")[0].strip()
            deps[pkg] = line

        ok_count = 0
        fail_count = 0
        for pkg_name, req_line in sorted(deps.items()):
            # 映射包名到 import 名
            import_map = {
                "gradio": "gradio",
                "openai": "openai",
                "python-docx": "docx",
                "docxtpl": "docxtpl",
                "requests": "requests",
                "crossref-commons": "crossref_commons",
                "python-dotenv": "dotenv",
                "markdown": "markdown",
                "openpyxl": "openpyxl",
                "Pillow": "PIL",
                "celery": "celery",
                "redis": "redis",
                "matplotlib": "matplotlib",
                "networkx": "networkx",
                "scipy": "scipy",
                "sentence-transformers": "sentence_transformers",
                "numpy": "numpy",
            }
            import_name = import_map.get(pkg_name, pkg_name.replace("-", "_"))

            try:
                importlib.import_module(import_name)
                ok_count += 1
            except ImportError:
                fail_count += 1
                print(Color.err(f"{pkg_name} ({req_line}) — 未安装"))
                if pkg_name in ("celery", "redis", "sentence-transformers"):
                    self.warnings.append(f"{pkg_name} 未安装（可选依赖，核心功能不受影响）")
                else:
                    self.errors.append(f"{pkg_name} 未安装")

        if fail_count == 0:
            print(Color.ok(f"全部 {ok_count} 个依赖已安装"))
        elif fail_count > 0 and len(self.errors) == 0:
            print(Color.warn(f"{ok_count} 个已安装，{fail_count} 个可选依赖缺失（不影响核心功能）"))
        else:
            print(Color.err(f"{ok_count} 个已安装，{fail_count} 个缺失"))
            self.fix_commands.append("pip install -r requirements.txt")

    def _check_key_files(self) -> None:
        """检查关键文件完整性"""
        print(f"\n📁 检查关键文件...")
        key_files = [
            "app.py",
            "config.py",
            "requirements.txt",
            ".env.example",
            "core/models.py",
            "core/outline_generator.py",
            "core/chapter_generator.py",
            "core/template_parser.py",
            "core/docx_formatter.py",
            "core/reference_fetcher.py",
            "core/data_importer.py",
            "core/charts.py",
            "core/stats_engine.py",
            "core/review_engine.py",
            "core/knowledge_graph.py",
            "core/critical_reviewer.py",
            "core/formula_renderer.py",
            "core/history_store.py",
            "llm/base.py",
            "llm/deepseek_client.py",
            "llm/openai_client.py",
            "ui/tabs.py",
            "ui/callbacks.py",
            "ui/components.py",
            "prompts/outline_prompts.py",
            "prompts/chapter_prompts.py",
            "prompts/reference_prompts.py",
            "prompts/reviewer_prompts.py",
            "utils/file_utils.py",
            "utils/text_utils.py",
            "utils/watermark.py",
            "utils/format_checker.py",
            "utils/plagiarism_checker.py",
        ]

        ok = 0
        missing = 0
        for f in key_files:
            path = PROJECT_ROOT / f
            if path.exists():
                ok += 1
            else:
                missing += 1
                self.errors.append(f"关键文件缺失: {f}")
                print(Color.err(f"缺失: {f}"))

        if missing == 0:
            print(Color.ok(f"全部 {ok} 个关键文件就绪"))
        else:
            self.fix_commands.append("检查项目完整性: git status 或重新克隆项目")

    def _check_api_key(self) -> None:
        """检查 API Key 配置"""
        print(f"\n🔑 检查 API Key 配置...")
        env_path = PROJECT_ROOT / ".env"

        if not env_path.exists():
            print(Color.warn(".env 文件不存在 — 从 .env.example 创建"))
            example = PROJECT_ROOT / ".env.example"
            if example.exists():
                import shutil
                shutil.copy(example, env_path)
                print(Color.ok("已从 .env.example 创建 .env，请编辑填入 API Key"))
            else:
                self.warnings.append(".env 和 .env.example 均不存在")
            return

        # 解析 .env 文件
        with open(env_path) as f:
            content = f.read()

        has_deepseek = "DEEPSEEK_API_KEY" in content and "sk-" in content
        has_openai = "OPENAI_API_KEY" in content and "sk-" in content

        if has_deepseek:
            print(Color.ok("DeepSeek API Key 已配置"))
        elif "DEEPSEEK_API_KEY" in content:
            print(Color.warn("DeepSeek API Key 存在但可能无效（需包含 sk-）"))
            self.warnings.append("DeepSeek API Key 格式可能无效")
        else:
            print(Color.warn("DeepSeek API Key 未配置"))
            self.warnings.append("DEEPSEEK_API_KEY 未设置")
            self.fix_commands.append("编辑 .env: DEEPSEEK_API_KEY=sk-你的密钥")

        if has_openai:
            print(Color.ok("OpenAI API Key 已配置"))

    def _check_dirs(self) -> None:
        """检查数据目录可写性"""
        print(f"\n📂 检查数据目录...")
        dirs = [
            PROJECT_ROOT / "data" / "templates",
            PROJECT_ROOT / "data" / "output",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            try:
                test_file = d / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
                print(Color.ok(f"{d} — 可写"))
            except Exception as e:
                self.errors.append(f"目录不可写: {d} ({e})")
                print(Color.err(f"{d} — 不可写"))

    def _check_quick_imports(self) -> None:
        """快速导入测试关键模块"""
        quick_imports = [
            ("core.models", "Thesis"),
            ("config", "load_config"),
            ("core.docx_formatter", "DocxFormatter"),
            ("core.reference_fetcher", "ReferenceFetcher"),
            ("tasks", "AsyncTaskManager"),
        ]
        for module_name, attr in quick_imports:
            try:
                mod = importlib.import_module(module_name)
                getattr(mod, attr)
            except Exception as e:
                self.errors.append(f"模块导入失败: {module_name} ({e})")
                print(Color.err(f"导入失败: {module_name}.{attr} — {e}"))
        else:
            print(Color.ok(f"关键模块导入正常"))

    # ── 输出 ──────────────────────────────────────────────

    def _print_summary(self) -> None:
        """输出诊断摘要"""
        print(Color.title("诊断结果"))

        error_count = len(self.errors)
        warn_count = len(self.warnings)
        ok_count = len(self.oks)

        print(f"\n   ✅ 通过: {ok_count}")
        print(f"   ⚠️  警告: {warn_count}")
        print(f"   ❌ 错误: {error_count}")

        if self.warnings:
            print(f"\n{Color.BOLD}⚠️  警告详情:{Color.RESET}")
            for w in self.warnings:
                print(f"   {Color.warn(w)}")

        if self.errors:
            print(f"\n{Color.BOLD}❌ 错误详情:{Color.RESET}")
            for e in self.errors:
                print(f"   {Color.err(e)}")

        if self.fix_commands:
            print(f"\n{Color.BOLD}🔧 修复命令:{Color.RESET}")
            for i, cmd in enumerate(self.fix_commands, 1):
                print(f"   {i}. {cmd}")

        # 最终判定
        if error_count == 0 and warn_count == 0:
            print(f"\n{Color.GREEN}{Color.BOLD}🎉 环境完美，可以直接启动！{Color.RESET}")
            print(f"   启动命令: python app.py")
        elif error_count == 0:
            print(f"\n{Color.YELLOW}{Color.BOLD}⚠️  环境基本就绪，存在 {warn_count} 个警告，建议修复后再启动。{Color.RESET}")
        else:
            print(f"\n{Color.RED}{Color.BOLD}❌ 环境存在 {error_count} 个严重问题，请先修复再启动。{Color.RESET}")


# ── 入口 ──────────────────────────────────────────────────

def main():
    """独立运行入口"""
    checker = EnvironmentChecker()
    passed = checker.run_all()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
