"""
DeepSeek API 适配器

基于 OpenAI SDK 兼容协议，通过设置 base_url 指向 DeepSeek API。
DeepSeek 完全兼容 OpenAI chat/completions 接口。
"""

from typing import Dict, List, Iterator, Optional
import logging

from llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


class DeepSeekClient(BaseLLMClient):
    """DeepSeek API 客户端

    使用 OpenAI Python SDK，base_url 设为 https://api.deepseek.com。
    支持同步 chat 和流式 chat_stream 两种调用方式。
    """

    def __init__(
        self,
        model: str = "deepseek-chat",
        api_key: str = "",
        api_base: str = "https://api.deepseek.com",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """初始化 DeepSeek 客户端

        Args:
            model: 模型名称（deepseek-chat 或 deepseek-reasoner）
            api_key: DeepSeek API Key
            api_base: API 基础 URL
            temperature: 生成温度（0.0~2.0）
            max_tokens: 最大生成 token 数
        """
        super().__init__(
            model=model,
            api_key=api_key,
            api_base=api_base,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self._client = None  # 延迟初始化

    def _get_client(self):
        """获取或创建 OpenAI 客户端实例（延迟初始化）

        Returns:
            OpenAI: 配置好的客户端
        """
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.api_base,
                )
            except ImportError:
                raise ImportError(
                    "openai 包未安装，请执行: pip install openai>=1.0"
                )
            except Exception as e:
                raise RuntimeError(f"初始化 DeepSeek 客户端失败: {e}")
        return self._client

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送同步对话请求

        Args:
            messages: 消息列表
            **kwargs: 覆盖默认参数（temperature, max_tokens 等）

        Returns:
            str: 生成的文本回复

        Raises:
            RuntimeError: API 调用失败时，包装为中文错误信息
        """
        client = self._get_client()
        chat_kwargs = self._get_chat_kwargs(**kwargs)

        try:
            response = client.chat.completions.create(
                messages=messages,  # type: ignore[arg-type]
                **chat_kwargs,
            )
            content = response.choices[0].message.content
            if content is None:
                logger.warning("DeepSeek 返回空内容")
                return ""
            return content

        except Exception as e:
            error_msg = str(e)
            logger.error(f"DeepSeek API 调用失败: {error_msg}")

            # 提供更友好的中文错误信息
            if "Invalid API Key" in error_msg or "invalid api_key" in error_msg.lower():
                raise RuntimeError(
                    "❌ DeepSeek API Key 无效，请检查设置 → 填入正确的 API Key"
                ) from e
            elif "rate_limit" in error_msg.lower() or "429" in error_msg:
                raise RuntimeError(
                    "⏳ DeepSeek API 请求频率超限，请稍后重试"
                ) from e
            elif "insufficient_quota" in error_msg.lower():
                raise RuntimeError(
                    "💰 DeepSeek API 额度不足，请检查账户余额"
                ) from e
            elif "timeout" in error_msg.lower():
                raise RuntimeError(
                    "⏰ DeepSeek API 请求超时，请检查网络连接后重试"
                ) from e
            else:
                raise RuntimeError(
                    f"❌ DeepSeek API 调用失败: {error_msg[:200]}"
                ) from e

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Iterator[str]:
        """发送流式对话请求

        Args:
            messages: 消息列表
            **kwargs: 覆盖默认参数

        Yields:
            str: 逐 chunk 的文本回复

        Raises:
            RuntimeError: API 调用失败时
        """
        client = self._get_client()
        chat_kwargs = self._get_chat_kwargs(**kwargs)
        chat_kwargs["stream"] = True

        try:
            stream = client.chat.completions.create(
                messages=messages,  # type: ignore[arg-type]
                **chat_kwargs,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

        except Exception as e:
            error_msg = str(e)
            logger.error(f"DeepSeek 流式调用失败: {error_msg}")

            if "Invalid API Key" in error_msg or "invalid api_key" in error_msg.lower():
                raise RuntimeError(
                    "❌ DeepSeek API Key 无效"
                ) from e
            else:
                raise RuntimeError(
                    f"❌ DeepSeek 流式调用失败: {error_msg[:200]}"
                ) from e
