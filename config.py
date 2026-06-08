"""
集中配置管理模块

职责：
- 从环境变量（.env）加载 API Key / Base URL
- 提供常量默认值
- 导出统一的 load_config() 函数

GenerationConfig 数据类定义在 core/models.py 中。

命名规范：
- 常量：UPPER_SNAKE_CASE
- 函数：snake_case
"""

import os

from dotenv import load_dotenv

# 延迟导入避免循环依赖
from core.models import GenerationConfig

# 加载 .env 文件（若存在）
load_dotenv()

# ── 默认常量 ──────────────────────────────────────────────
DEFAULT_WORD_COUNT: int = 15000
DEFAULT_DISCIPLINE: str = "软件工程"
DEFAULT_TEMPERATURE: float = 0.7
DEFAULT_MAX_TOKENS_PER_CHAPTER: int = 4096
DEFAULT_LLM_PROVIDER: str = "deepseek"
DEFAULT_LLM_MODEL: str = "deepseek-chat"
DEFAULT_LLM_API_BASE: str = "https://api.deepseek.com"

# 异步任务（P1 新增）
DEFAULT_ASYNC_MODE: bool = False
DEFAULT_REDIS_URL: str = ""
DEFAULT_CELERY_BROKER_URL: str = ""
DEFAULT_SEMANTIC_SCHOLAR_API_KEY: str = ""

# 引用配置（P1 新增）
MAX_REFS_PER_CHAPTER: int = 10
REF_CACHE_SIZE: int = 200

# 输出目录
OUTPUT_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "output")
TEMPLATE_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "templates")


def load_config() -> GenerationConfig:
    """从环境变量加载配置，返回 GenerationConfig 实例

    优先级：环境变量 > 默认值

    Returns:
        GenerationConfig: 填充好所有字段的配置对象
    """
    config = GenerationConfig(
        llm_provider=os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER),
        llm_model=os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
        llm_api_key=os.getenv(
            "DEEPSEEK_API_KEY" if os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER) == "deepseek"
            else "OPENAI_API_KEY",
            ""
        ),
        llm_api_base=os.getenv(
            "DEEPSEEK_API_BASE" if os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER) == "deepseek"
            else "OPENAI_API_BASE",
            DEFAULT_LLM_API_BASE,
        ),
        target_word_count=int(os.getenv("DEFAULT_WORD_COUNT", DEFAULT_WORD_COUNT)),
        discipline=os.getenv("DEFAULT_DISCIPLINE", DEFAULT_DISCIPLINE),
        temperature=float(os.getenv("DEFAULT_TEMPERATURE", DEFAULT_TEMPERATURE)),
        max_tokens_per_chapter=int(
            os.getenv("MAX_TOKENS_PER_CHAPTER", DEFAULT_MAX_TOKENS_PER_CHAPTER)
        ),
        # P1 新增
        async_mode=os.getenv("ASYNC_MODE", str(DEFAULT_ASYNC_MODE)).lower() in ("true", "1", "yes"),
        redis_url=os.getenv("REDIS_URL", DEFAULT_REDIS_URL),
        celery_broker_url=os.getenv("CELERY_BROKER_URL", DEFAULT_CELERY_BROKER_URL),
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY", DEFAULT_SEMANTIC_SCHOLAR_API_KEY),
    )
    return config


def get_api_key(provider: str) -> str:
    """根据提供商名称获取对应的 API Key

    Args:
        provider: "deepseek" 或 "openai"

    Returns:
        str: API Key 字符串，未设置则返回空字符串
    """
    key_map = {
        "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", ""),
    }
    return key_map.get(provider, "")
