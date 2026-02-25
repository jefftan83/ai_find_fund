"""Claude API 封装"""

from anthropic import Anthropic
from typing import List, Dict, Any, Optional
from src.utils.config import config


class ClaudeClient:
    """Claude API 客户端"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Claude 客户端

        Args:
            api_key: API Key，如果不传则从配置中获取
        """
        self.api_key = api_key or config.anthropic_api_key
        if not self.api_key:
            raise ValueError(
                "Anthropic API Key 未配置。\n"
                "请设置环境变量 ANTHROPIC_API_KEY 或在 config.yaml 中配置 anthropic_api_key"
            )

        # 支持自定义 base_url（兼容阿里云 API）
        base_url = config.anthropic_base_url
        if base_url:
            self.client = Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = Anthropic(api_key=self.api_key)

        self.model = config.claude_model

    def chat(
        self,
        messages: List[Dict[str, str]],
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> str:
        """
        发送聊天请求

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            system: 系统提示词
            max_tokens: 最大输出 token 数
            temperature: 温度参数

        Returns:
            AI 回复的内容
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages
        )

        # 提取回复内容（兼容不同响应格式）
        content_text = ""
        for block in response.content:
            if hasattr(block, 'type'):
                if block.type == "text":
                    content_text += block.text
                elif block.type == "thinking":
                    # 跳过 thinking 块
                    continue
                elif hasattr(block, 'text'):
                    content_text += block.text
            elif hasattr(block, 'text'):
                content_text += block.text

        return content_text

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        system: str = "",
        tools: List[Dict[str, Any]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        发送带工具的聊天请求

        Args:
            messages: 消息列表
            system: 系统提示词
            tools: 工具定义列表
            max_tokens: 最大输出 token 数
            temperature: 温度参数

        Returns:
            (回复内容，工具调用列表)
        """
        request_kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }

        if tools:
            request_kwargs["tools"] = tools

        response = self.client.messages.create(**request_kwargs)

        # 提取回复内容和工具调用
        content_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })

        return content_text, tool_calls
