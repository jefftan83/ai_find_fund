"""Unified LLM client with factory pattern for multiple providers"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.utils.config import config


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> str:
        """Send a chat message and return the response"""
        pass

    @abstractmethod
    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        system: str = "",
        tools: List[Dict[str, Any]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Send a chat message with tools and return response + tool calls"""
        pass


class AnthropicClient(BaseLLMClient):
    """Anthropic API client (保留原有逻辑)"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Anthropic 客户端

        Args:
            api_key: API Key，如果不传则从配置中获取
        """
        from anthropic import Anthropic

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


class OpenAIClient(BaseLLMClient):
    """OpenAI API client (同时支持 Ollama，通过 base_url 区分)"""

    def __init__(self, provider: str = "openai"):
        """
        初始化 OpenAI 客户端

        Args:
            provider: "openai" 或 "ollama"
        """
        from openai import OpenAI

        self.provider = provider

        if provider == "ollama":
            # Ollama 配置
            self.base_url = config.ollama_base_url or "http://localhost:11434/v1"
            self.api_key = "ollama"  # Ollama 不需要真实的 API Key
            self.model = config.ollama_model
        else:
            # OpenAI 配置
            self.api_key = config.openai_api_key
            if not self.api_key:
                raise ValueError(
                    "OpenAI API Key 未配置。\n"
                    "请设置环境变量 OPENAI_API_KEY 或在 config.yaml 中配置 openai_api_key"
                )
            self.base_url = config.openai_base_url or "https://api.openai.com/v1"
            self.model = config.openai_model

        # 初始化 OpenAI 客户端（Ollama 兼容 OpenAI 接口）
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

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
        # 构建请求消息（OpenAI 格式）
        if system:
            api_messages = [{"role": "system", "content": system}] + messages
        else:
            api_messages = messages

        # Ollama 兼容性处理：不使用 max_tokens（某些版本有问题）
        request_kwargs = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature
        }

        if self.provider != "ollama":
            request_kwargs["max_tokens"] = max_tokens

        response = self.client.chat.completions.create(**request_kwargs)

        return response.choices[0].message.content

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
            tools: 工具定义列表（OpenAI 格式）
            max_tokens: 最大输出 token 数
            temperature: 温度参数

        Returns:
            (回复内容，工具调用列表)
        """
        # 构建请求消息
        if system:
            api_messages = [{"role": "system", "content": system}] + messages
        else:
            api_messages = messages

        # Ollama 兼容性处理：不使用 max_tokens
        request_kwargs = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature
        }

        if self.provider != "ollama":
            request_kwargs["max_tokens"] = max_tokens

        if tools:
            # OpenAI 格式的工具定义
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**request_kwargs)

        choice = response.choices[0]
        message = choice.message

        # 提取回复内容
        content_text = message.content or ""

        # 提取工具调用
        tool_calls = []
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": tc.function.arguments
                })

        return content_text, tool_calls


def create_llm_client(provider: Optional[str] = None) -> BaseLLMClient:
    """
    工厂函数：根据配置创建对应的 LLM 客户端

    Args:
        provider: 指定提供商，如果不传则从配置中读取

    Returns:
        LLM 客户端实例
    """
    if provider is None:
        provider = config.llm_provider

    if provider == "anthropic":
        return AnthropicClient()
    elif provider == "openai":
        return OpenAIClient(provider="openai")
    elif provider == "ollama":
        return OpenAIClient(provider="ollama")
    else:
        raise ValueError(f"不支持的 LLM 提供商：{provider}，支持的选项：anthropic, openai, ollama")


# 保留向后兼容的别名
ClaudeClient = AnthropicClient
