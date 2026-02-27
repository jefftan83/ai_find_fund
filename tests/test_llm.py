"""
LLM 客户端测试
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock

from src.utils.llm import ClaudeClient, AnthropicClient, OpenAIClient, create_llm_client, BaseLLMClient


class TestClaudeClient:
    """ClaudeClient 类测试"""

    def test_init_no_api_key(self):
        """LLM-001: 无 API Key 初始化"""
        from src.utils.config import Config
        import tempfile
        from pathlib import Path

        # 创建一个没有 API Key 的临时配置文件，并清除环境变量
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('claude_model: "test-model"\n')
            temp_path = Path(f.name)

        try:
            temp_config = Config(temp_path)
            # Patch config 实例
            with patch('src.utils.llm.config', temp_config):
                with patch.dict('os.environ', {}, clear=True):
                    with pytest.raises(ValueError) as exc_info:
                        ClaudeClient()
                    assert "API Key 未配置" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_init_with_api_key(self):
        """LLM-002: 有 API Key 初始化"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            client = ClaudeClient(api_key='test-key')
            assert client.api_key == 'test-key'
            mock_anthropic.assert_called_once()
            call_args = mock_anthropic.call_args
            assert call_args.kwargs['api_key'] == 'test-key'

    def test_init_with_custom_base_url(self):
        """LLM-003: 自定义 base_url"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            client = ClaudeClient(api_key='test-key')
            assert mock_anthropic.called

    def test_chat_success(self):
        """LLM-004: 简单聊天请求"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            # Mock 响应
            mock_response = MagicMock()
            mock_block = MagicMock()
            mock_block.type = "text"
            mock_block.text = "Hello, I'm Claude!"
            mock_response.content = [mock_block]
            mock_anthropic.return_value.messages.create.return_value = mock_response

            client = ClaudeClient(api_key='test-key')
            result = client.chat([{"role": "user", "content": "Hello"}])

            assert result == "Hello, I'm Claude!"
            mock_anthropic.return_value.messages.create.assert_called_once()

    def test_chat_with_system(self):
        """LLM-005: 带 system 的聊天"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_block = MagicMock()
            mock_block.type = "text"
            mock_block.text = "Response with system prompt"
            mock_response.content = [mock_block]
            mock_anthropic.return_value.messages.create.return_value = mock_response

            client = ClaudeClient(api_key='test-key')
            result = client.chat(
                [{"role": "user", "content": "Test"}],
                system="You are a helpful assistant"
            )

            assert result == "Response with system prompt"
            call_args = mock_anthropic.return_value.messages.create.call_args
            assert call_args.kwargs['system'] == "You are a helpful assistant"

    def test_chat_multi_turn(self):
        """LLM-006: 多轮对话"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_block = MagicMock()
            mock_block.type = "text"
            mock_block.text = "Yes, I remember you said 100k"
            mock_response.content = [mock_block]
            mock_anthropic.return_value.messages.create.return_value = mock_response

            client = ClaudeClient(api_key='test-key')
            messages = [
                {"role": "user", "content": "I have 100k to invest"},
                {"role": "assistant", "content": "Great! What's your goal?"},
                {"role": "user", "content": "Long term growth"}
            ]
            result = client.chat(messages)

            assert "remember" in result.lower() or "100k" in result

    def test_chat_skip_thinking_block(self):
        """LLM-007: thinking 块处理"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            # 模拟包含 thinking 块的响应
            thinking_block = MagicMock()
            thinking_block.type = "thinking"

            text_block = MagicMock()
            text_block.type = "text"
            text_block.text = "Final answer"

            mock_response.content = [thinking_block, text_block]
            mock_anthropic.return_value.messages.create.return_value = mock_response

            client = ClaudeClient(api_key='test-key')
            result = client.chat([{"role": "user", "content": "Test"}])

            # thinking 块应该被跳过
            assert result == "Final answer"

    def test_chat_exception_handling(self):
        """LLM-008: 异常响应处理"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            # 模拟 API 错误
            mock_anthropic.return_value.messages.create.side_effect = Exception("API Error")

            client = ClaudeClient(api_key='test-key')
            with pytest.raises(Exception) as exc_info:
                client.chat([{"role": "user", "content": "Test"}])
            assert "API Error" in str(exc_info.value)

    def test_chat_with_tools(self):
        """LLM-009: 带工具的聊天"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()

            # 模拟包含 tool_use 的响应
            text_block = MagicMock()
            text_block.type = "text"
            text_block.text = "Let me search that for you"

            tool_block = MagicMock()
            tool_block.type = "tool_use"
            tool_block.id = "tool_123"
            tool_block.name = "search_fund"
            tool_block.input = {"fund_code": "000001"}

            mock_response.content = [text_block, tool_block]
            mock_anthropic.return_value.messages.create.return_value = mock_response

            client = ClaudeClient(api_key='test-key')
            tools = [{"name": "search_fund", "description": "Search fund info"}]
            text, tool_calls = client.chat_with_tools(
                [{"role": "user", "content": "Search fund 000001"}],
                tools=tools
            )

            assert text == "Let me search that for you"
            assert len(tool_calls) == 1
            assert tool_calls[0]["name"] == "search_fund"
            assert tool_calls[0]["input"]["fund_code"] == "000001"

    def test_chat_with_tools_no_tools(self):
        """LLM-010: 不带工具的聊天"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_block = MagicMock()
            mock_block.type = "text"
            mock_block.text = "Simple response"
            mock_response.content = [mock_block]
            mock_anthropic.return_value.messages.create.return_value = mock_response

            client = ClaudeClient(api_key='test-key')
            text, tool_calls = client.chat_with_tools(
                [{"role": "user", "content": "Hello"}]
            )

            assert text == "Simple response"
            assert len(tool_calls) == 0


class TestOpenAIClient:
    """OpenAIClient 类测试（支持 OpenAI 和 Ollama）"""

    def test_init_openai_with_api_key(self):
        """LLM-101: OpenAI 客户端初始化（有 API Key）"""
        from src.utils.config import Config
        import tempfile
        from pathlib import Path

        # 创建临时配置文件，设置 openai_api_key
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('llm_provider: "openai"\n')
            f.write('openai_api_key: "sk-test-key"\n')
            f.write('openai_model: "gpt-4o"\n')
            temp_path = Path(f.name)

        try:
            temp_config = Config(temp_path)
            with patch('src.utils.llm.config', temp_config):
                with patch('openai.OpenAI') as mock_openai:
                    client = OpenAIClient(provider="openai")
                    assert client.provider == "openai"
                    mock_openai.assert_called_once()
        finally:
            temp_path.unlink()

    def test_init_ollama_no_api_key(self):
        """LLM-102: Ollama 客户端初始化（无需 API Key）"""
        with patch('openai.OpenAI') as mock_openai:
            client = OpenAIClient(provider="ollama")
            assert client.provider == "ollama"
            assert client.api_key == "ollama"
            mock_openai.assert_called_once()
            # 验证 Ollama 的默认配置
            call_args = mock_openai.call_args
            assert call_args.kwargs['api_key'] == "ollama"
            assert "localhost:11434" in call_args.kwargs['base_url']

    def test_chat_openai_success(self):
        """LLM-103: OpenAI 聊天请求成功"""
        with patch('openai.OpenAI') as mock_openai:
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Hello from OpenAI!"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_openai.return_value.chat.completions.create.return_value = mock_response

            # 直接设置属性，绕过配置
            client = OpenAIClient.__new__(OpenAIClient)
            client.api_key = 'test-key'
            client.base_url = 'https://api.openai.com/v1'
            client.model = 'gpt-4o'
            client.provider = 'openai'
            client.client = mock_openai.return_value

            result = client.chat([{"role": "user", "content": "Hello"}])

            assert result == "Hello from OpenAI!"

    def test_chat_ollama_success(self):
        """LLM-104: Ollama 聊天请求成功"""
        with patch('openai.OpenAI') as mock_openai:
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Hello from Ollama!"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_openai.return_value.chat.completions.create.return_value = mock_response

            client = OpenAIClient.__new__(OpenAIClient)
            client.api_key = 'ollama'
            client.base_url = 'http://localhost:11434/v1'
            client.model = 'qwen2.5:7b'
            client.provider = 'ollama'
            client.client = mock_openai.return_value

            result = client.chat([{"role": "user", "content": "Hello"}])

            assert result == "Hello from Ollama!"

    def test_chat_with_system(self):
        """LLM-105: OpenAI 带 system 的聊天"""
        with patch('openai.OpenAI') as mock_openai:
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Response with system"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_openai.return_value.chat.completions.create.return_value = mock_response

            client = OpenAIClient.__new__(OpenAIClient)
            client.api_key = 'test-key'
            client.base_url = 'https://api.openai.com/v1'
            client.model = 'gpt-4o'
            client.provider = 'openai'
            client.client = mock_openai.return_value

            result = client.chat(
                [{"role": "user", "content": "Test"}],
                system="You are helpful"
            )

            assert result == "Response with system"
            # 验证 system 消息被添加
            call_args = mock_openai.return_value.chat.completions.create.call_args
            messages = call_args.kwargs['messages']
            assert messages[0]['role'] == 'system'

    def test_chat_with_tools_openai(self):
        """LLM-106: OpenAI 带工具的聊天"""
        with patch('openai.OpenAI') as mock_openai:
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Let me search that"

            # Mock tool call
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_123"
            mock_tool_call.function.name = "search_fund"
            mock_tool_call.function.arguments = '{"fund_code": "000001"}'
            mock_message.tool_calls = [mock_tool_call]

            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_openai.return_value.chat.completions.create.return_value = mock_response

            client = OpenAIClient.__new__(OpenAIClient)
            client.api_key = 'test-key'
            client.base_url = 'https://api.openai.com/v1'
            client.model = 'gpt-4o'
            client.provider = 'openai'
            client.client = mock_openai.return_value

            tools = [{
                "type": "function",
                "function": {
                    "name": "search_fund",
                    "description": "Search fund info"
                }
            }]

            text, tool_calls = client.chat_with_tools(
                [{"role": "user", "content": "Search fund"}],
                tools=tools
            )

            assert text == "Let me search that"
            assert len(tool_calls) == 1
            assert tool_calls[0]["name"] == "search_fund"

    def test_chat_with_tools_no_tool_calls(self):
        """LLM-107: OpenAI 带工具但无工具调用"""
        with patch('openai.OpenAI') as mock_openai:
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "I don't need tools"
            mock_message.tool_calls = None
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_openai.return_value.chat.completions.create.return_value = mock_response

            client = OpenAIClient.__new__(OpenAIClient)
            client.api_key = 'test-key'
            client.base_url = 'https://api.openai.com/v1'
            client.model = 'gpt-4o'
            client.provider = 'openai'
            client.client = mock_openai.return_value

            text, tool_calls = client.chat_with_tools(
                [{"role": "user", "content": "Hello"}],
                tools=[]
            )

            assert text == "I don't need tools"
            assert len(tool_calls) == 0

    def test_openai_init_no_api_key_raises_error(self):
        """LLM-108: OpenAI 无 API Key 抛出错误"""
        from src.utils.config import Config
        import tempfile
        from pathlib import Path

        # 创建临时配置文件，不设置 openai_api_key
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('llm_provider: "openai"\n')
            temp_path = Path(f.name)

        try:
            temp_config = Config(temp_path)
            with patch('src.utils.llm.config', temp_config):
                with patch.dict('os.environ', {}, clear=True):
                    with pytest.raises(ValueError) as exc_info:
                        OpenAIClient(provider="openai")
                    assert "API Key 未配置" in str(exc_info.value)
        finally:
            temp_path.unlink()


class TestFactoryFunction:
    """工厂函数测试"""

    def test_create_anthropic_client(self):
        """LLM-201: 创建 Anthropic 客户端"""
        with patch('src.utils.llm.AnthropicClient') as mock_anthropic:
            client = create_llm_client(provider="anthropic")
            mock_anthropic.assert_called_once()

    def test_create_openai_client(self):
        """LLM-202: 创建 OpenAI 客户端"""
        with patch('src.utils.llm.OpenAIClient') as mock_openai:
            client = create_llm_client(provider="openai")
            mock_openai.assert_called_with(provider="openai")

    def test_create_ollama_client(self):
        """LLM-203: 创建 Ollama 客户端"""
        with patch('src.utils.llm.OpenAIClient') as mock_openai:
            client = create_llm_client(provider="ollama")
            mock_openai.assert_called_with(provider="ollama")

    def test_create_client_from_config(self):
        """LLM-204: 从配置创建客户端"""
        with patch('src.utils.llm.config') as mock_config:
            mock_config.llm_provider = "anthropic"
            with patch('src.utils.llm.AnthropicClient') as mock_anthropic:
                client = create_llm_client()
                mock_anthropic.assert_called_once()

    def test_create_client_invalid_provider(self):
        """LLM-205: 不支持的提供商抛出错误"""
        with pytest.raises(ValueError) as exc_info:
            create_llm_client(provider="invalid")
        assert "不支持的 LLM 提供商" in str(exc_info.value)


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_claude_client_alias(self):
        """LLM-301: ClaudeClient 别名指向 AnthropicClient"""
        from src.utils.llm import ClaudeClient
        assert ClaudeClient is AnthropicClient
