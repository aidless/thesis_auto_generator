"""
测试配置管理 (test_config.py)

覆盖：
- load_config() 默认值
- 环境变量覆盖
- get_api_key() 按提供商获取
- 常量值验证
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import GenerationConfig

# 注意：config 模块在导入时会自动调用 load_dotenv()，
# 且依赖 core.models，我们分别测试其函数
import config


class TestLoadConfig(unittest.TestCase):
    """测试 load_config()"""

    def test_returns_generation_config(self):
        """测试返回 GenerationConfig 类型"""
        cfg = config.load_config()
        self.assertIsInstance(cfg, GenerationConfig)

    def test_default_provider(self):
        """测试默认 LLM 提供商"""
        cfg = config.load_config()
        self.assertEqual(cfg.llm_provider, "deepseek")

    def test_default_model(self):
        """测试默认模型"""
        cfg = config.load_config()
        self.assertEqual(cfg.llm_model, "deepseek-chat")

    def test_default_word_count(self):
        """测试默认字数"""
        cfg = config.load_config()
        self.assertEqual(cfg.target_word_count, 15000)

    def test_default_discipline(self):
        """测试默认学科"""
        cfg = config.load_config()
        self.assertEqual(cfg.discipline, "软件工程")

    def test_default_temperature(self):
        """测试默认温度"""
        cfg = config.load_config()
        self.assertEqual(cfg.temperature, 0.7)

    def test_default_max_tokens(self):
        """测试默认最大 token"""
        cfg = config.load_config()
        self.assertEqual(cfg.max_tokens_per_chapter, 4096)

    def test_env_override_word_count(self):
        """测试环境变量覆盖字数"""
        os.environ["DEFAULT_WORD_COUNT"] = "20000"
        try:
            cfg = config.load_config()
            self.assertEqual(cfg.target_word_count, 20000)
        finally:
            del os.environ["DEFAULT_WORD_COUNT"]

    def test_env_override_discipline(self):
        """测试环境变量覆盖学科"""
        os.environ["DEFAULT_DISCIPLINE"] = "人工智能"
        try:
            cfg = config.load_config()
            self.assertEqual(cfg.discipline, "人工智能")
        finally:
            del os.environ["DEFAULT_DISCIPLINE"]

    def test_env_override_temperature(self):
        """测试环境变量覆盖温度"""
        os.environ["DEFAULT_TEMPERATURE"] = "0.3"
        try:
            cfg = config.load_config()
            self.assertEqual(cfg.temperature, 0.3)
        finally:
            del os.environ["DEFAULT_TEMPERATURE"]

    def test_env_override_max_tokens(self):
        """测试环境变量覆盖最大 token"""
        os.environ["MAX_TOKENS_PER_CHAPTER"] = "8192"
        try:
            cfg = config.load_config()
            self.assertEqual(cfg.max_tokens_per_chapter, 8192)
        finally:
            del os.environ["MAX_TOKENS_PER_CHAPTER"]

    def test_env_api_key_passed_through(self):
        """测试 API Key 通过环境变量传递"""
        os.environ["DEEPSEEK_API_KEY"] = "sk-test-deepseek"
        os.environ["LLM_PROVIDER"] = "deepseek"
        try:
            cfg = config.load_config()
            self.assertEqual(cfg.llm_api_key, "sk-test-deepseek")
        finally:
            del os.environ["DEEPSEEK_API_KEY"]
            del os.environ["LLM_PROVIDER"]

    def test_env_openai_key(self):
        """测试 OpenAI provider 时获取 OpenAI Key"""
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-test-openai"
        try:
            cfg = config.load_config()
            self.assertEqual(cfg.llm_api_key, "sk-test-openai")
        finally:
            del os.environ["LLM_PROVIDER"]
            del os.environ["OPENAI_API_KEY"]


class TestGetApiKey(unittest.TestCase):
    """测试 get_api_key()"""

    def test_deepseek_key(self):
        """测试获取 DeepSeek Key"""
        os.environ["DEEPSEEK_API_KEY"] = "my-deepseek-key"
        try:
            key = config.get_api_key("deepseek")
            self.assertEqual(key, "my-deepseek-key")
        finally:
            del os.environ["DEEPSEEK_API_KEY"]

    def test_openai_key(self):
        """测试获取 OpenAI Key"""
        os.environ["OPENAI_API_KEY"] = "my-openai-key"
        try:
            key = config.get_api_key("openai")
            self.assertEqual(key, "my-openai-key")
        finally:
            del os.environ["OPENAI_API_KEY"]

    def test_deepseek_key_not_set(self):
        """测试 DeepSeek Key 未设置"""
        if "DEEPSEEK_API_KEY" in os.environ:
            del os.environ["DEEPSEEK_API_KEY"]
        key = config.get_api_key("deepseek")
        self.assertEqual(key, "")

    def test_openai_key_not_set(self):
        """测试 OpenAI Key 未设置"""
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        key = config.get_api_key("openai")
        self.assertEqual(key, "")

    def test_unknown_provider(self):
        """测试未知提供商返回空"""
        key = config.get_api_key("unknown_provider")
        self.assertEqual(key, "")


class TestConstants(unittest.TestCase):
    """测试常量值"""

    def test_default_word_count(self):
        """测试默认字数常量"""
        self.assertEqual(config.DEFAULT_WORD_COUNT, 15000)

    def test_default_discipline(self):
        """测试默认学科常量"""
        self.assertEqual(config.DEFAULT_DISCIPLINE, "软件工程")

    def test_default_temperature(self):
        """测试默认温度常量"""
        self.assertEqual(config.DEFAULT_TEMPERATURE, 0.7)

    def test_default_max_tokens(self):
        """测试默认最大 token 常量"""
        self.assertEqual(config.DEFAULT_MAX_TOKENS_PER_CHAPTER, 4096)

    def test_default_provider_const(self):
        """测试默认提供商常量"""
        self.assertEqual(config.DEFAULT_LLM_PROVIDER, "deepseek")

    def test_default_model_const(self):
        """测试默认模型常量"""
        self.assertEqual(config.DEFAULT_LLM_MODEL, "deepseek-chat")

    def test_output_dir_exists(self):
        """测试 OUTPUT_DIR 常量"""
        self.assertIsInstance(config.OUTPUT_DIR, str)

    def test_template_dir_exists(self):
        """测试 TEMPLATE_DIR 常量"""
        self.assertIsInstance(config.TEMPLATE_DIR, str)


if __name__ == "__main__":
    unittest.main()
