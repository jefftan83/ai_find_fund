"""
LLM 客户端测试
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from anthropic import Anthropic

from src.utils.llm import ClaudeClient


class TestClaudeClient:
    """ClaudeClient 类测试"""

    def test_init_no_api_key(self):
        """LLM-001: 无 API Key 初始化"""
        # 注意：由于 config.yaml 中已配置 API Key，此测试需要在无配置环境下运行
        # 这里我们验证当传入空字符串且 config 也无配置时的行为
        # 实际测试中，由于全局 config 已有配置，此场景由集成测试覆盖
        # 本测试验证 API key 为空字符串时的处理
        from src.utils.config import Config
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

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
        with patch('src.utils.llm.Anthropic') as mock_anthropic:
            client = ClaudeClient(api_key='test-key')
            assert client.api_key == 'test-key'
            # config.yaml 中配置了 base_url，所以会传入 base_url
            mock_anthropic.assert_called_once()
            call_args = mock_anthropic.call_args
            assert call_args.kwargs['api_key'] == 'test-key'

    def test_init_with_custom_base_url(self):
        """LLM-003: 自定义 base_url"""
        with patch('src.utils.llm.Anthropic') as mock_anthropic:
            client = ClaudeClient(api_key='test-key')
            # 由于 config 中有 base_url，需要验证是否使用
            assert mock_anthropic.called

    def test_chat_success(self):
        """LLM-004: 简单聊天请求"""
        with patch('src.utils.llm.Anthropic') as mock_anthropic:
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
        with patch('src.utils.llm.Anthropic') as mock_anthropic:
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
        with patch('src.utils.llm.Anthropic') as mock_anthropic:
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
        with patch('src.utils.llm.Anthropic') as mock_anthropic:
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
        with patch('src.utils.llm.Anthropic') as mock_anthropic:
            # 模拟 API 错误
            mock_anthropic.return_value.messages.create.side_effect = Exception("API Error")

            client = ClaudeClient(api_key='test-key')
            with pytest.raises(Exception) as exc_info:
                client.chat([{"role": "user", "content": "Test"}])
            assert "API Error" in str(exc_info.value)

    def test_chat_with_tools(self):
        """LLM-009: 带工具的聊天"""
        with patch('src.utils.llm.Anthropic') as mock_anthropic:
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
        with patch('src.utils.llm.Anthropic') as mock_anthropic:
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
