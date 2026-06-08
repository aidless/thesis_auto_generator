"""
LLM 客户端抽象层

定义所有 LLM 客户端必须实现的 BaseLLMClient 抽象类，
以及根据 provider 名称创建对应客户端的工厂函数。

设计模式：策略模式（Strategy Pattern）
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Iterator, Optional

# 使用 TYPE_CHECKING 避免循环导入
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from config import GenerationConfig


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类

    所有 LLM 适配器（DeepSeek/OpenAI）必须实现此接口。
    使用 OpenAI SDK 兼容协议。

    Attributes:
        model: 模型名称
        api_key: API 密钥
        api_base: API 基础 URL
        temperature: 温度参数（控制生成随机性）
        max_tokens: 单次调用最大 token 数
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        api_base: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """初始化 LLM 客户端

        Args:
            model: 模型名称（如 "deepseek-chat", "gpt-4o"）
            api_key: API 密钥
            api_base: API 基础 URL
            temperature: 温度参数
            max_tokens: 最大生成 token 数
        """
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送对话请求并获取完整回复

        Args:
            messages: 消息列表，格式 [{"role": "system"|"user"|"assistant", "content": "..."}]
            **kwargs: 其他参数（temperature, max_tokens 等）

        Returns:
            str: LLM 生成的文本回复
        """
        ...

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Iterator[str]:
        """发送对话请求并获取流式回复

        Args:
            messages: 消息列表
            **kwargs: 其他参数

        Yields:
            str: 逐 chunk 的文本回复
        """
        ...

    def _get_chat_kwargs(self, **overrides) -> Dict:
        """构建聊天请求的默认参数，支持覆盖

        Args:
            **overrides: 需要覆盖的参数

        Returns:
            Dict: 合并后的参数字典
        """
        kwargs = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        kwargs.update(overrides)
        return kwargs


def create_llm_client(provider: str, config: "GenerationConfig") -> BaseLLMClient:
    """工厂函数：根据 provider 创建对应的 LLM 客户端

    Args:
        provider: LLM 提供商名称（"deepseek" 或 "openai"）
        config: 全局 GenerationConfig 实例

    Returns:
        BaseLLMClient: 配置好的 LLM 客户端实例

    Raises:
        ValueError: 当 provider 不受支持时
    """
    from llm.deepseek_client import DeepSeekClient
    from llm.openai_client import OpenAIClient

    # 根据 provider 确定 API Key 和 Base URL
    if provider == "deepseek":
        api_key = config.llm_api_key or _env_or_default("DEEPSEEK_API_KEY", "")
        api_base = config.llm_api_base or "https://api.deepseek.com"
        model = config.llm_model or "deepseek-chat"
        return DeepSeekClient(
            model=model,
            api_key=api_key,
            api_base=api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens_per_chapter,
        )
    elif provider == "openai":
        api_key = config.llm_api_key or _env_or_default("OPENAI_API_KEY", "")
        api_base = config.llm_api_base or "https://api.openai.com/v1"
        model = config.llm_model or "gpt-4o"
        return OpenAIClient(
            model=model,
            api_key=api_key,
            api_base=api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens_per_chapter,
        )
    else:
        raise ValueError(
            f"不支持的 LLM 提供商: {provider}。"
            f"当前支持: deepseek, openai"
        )


def _env_or_default(key: str, default: str) -> str:
    """从环境变量获取值，不存在则返回默认值

    Args:
        key: 环境变量名
        default: 默认值

    Returns:
        str: 环境变量值或默认值
    """
    import os
    return os.getenv(key, default)
