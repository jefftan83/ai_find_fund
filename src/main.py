"""基金推荐助手 - CLI 主入口"""

import asyncio
import typer
import readline  # 支持退格键和历史记录
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

from src.utils.config import config
from src.utils.llm import create_llm_client
from src.agents.manager import GroupChatManager

app = typer.Typer(
    name="fund-advisor",
    help="多 Agent 基金推荐助手 - 通过对话为您推荐合适的基金组合",
    add_completion=False
)

console = Console()


def _get_user_input() -> str:
    """
    获取用户输入，支持退格键删除

    Returns:
        用户输入的文本
    """
    # 使用 Python 原生 input()，配合 readline 模块支持退格键
    # 提示符 "您：" 由 input() 自己显示，不会被退格键删除
    # 使用 ANSI 转义序列让提示符显示为绿色
    try:
        user_input = input("\033[32m 您：\033[0m")
        return user_input.strip()
    except (EOFError, KeyboardInterrupt):
        return ""


@app.command()
def start(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示详细日志"),
):
    """
    启动基金推荐助手

    通过多轮对话了解您的投资需求和风险承受能力，
    然后为您推荐合适的基金组合。
    """
    console.print()
    console.print(Panel.fit(
        "[bold blue]🏦 基金推荐助手[/bold blue]\n\n"
        "通过专业的多 Agent 系统，为您推荐合适的基金组合",
        border_style="blue"
    ))
    console.print()

    # 检查 API Key 配置
    provider = config.llm_provider
    if provider == "anthropic" and not config.anthropic_api_key:
        console.print("[bold red]❌ 错误：[/bold red] 未配置 Anthropic API Key")
        console.print()
        console.print("请通过以下方式之一配置：")
        console.print("  1. 设置环境变量：export ANTHROPIC_API_KEY=your_api_key")
        console.print("  2. 复制配置文件：cp config.yaml.example config.yaml")
        console.print("     然后编辑 config.yaml，填入 anthropic_api_key")
        console.print()
        raise typer.Exit(code=1)
    elif provider == "openai" and not config.openai_api_key:
        console.print("[bold red]❌ 错误：[/bold red] 未配置 OpenAI API Key")
        console.print()
        console.print("请通过以下方式之一配置：")
        console.print("  1. 设置环境变量：export OPENAI_API_KEY=your_api_key")
        console.print("  2. 在 config.yaml 中配置 openai_api_key")
        console.print()
        raise typer.Exit(code=1)
    elif provider == "ollama":
        # Ollama 无需 API Key，检查服务是否可访问
        import httpx
        try:
            base_url = config.ollama_base_url or "http://localhost:11434/v1"
            # 移除 /v1 后缀进行检查
            check_url = base_url.replace("/v1", "")
            httpx.get(f"{check_url}/api/tags", timeout=5.0)
        except Exception as e:
            console.print("[bold red]❌ 错误：[/bold red] 无法连接到 Ollama 服务")
            console.print()
            console.print(f"详情：{str(e)}")
            console.print()
            console.print("请确保：")
            console.print("  1. Ollama 已安装")
            console.print("  2. 运行命令启动服务：ollama serve")
            console.print(f"  3. 模型已下载：ollama pull {config.ollama_model}")
            console.print()
            raise typer.Exit(code=1)

    # 初始化 LLM 客户端（使用工厂函数）
    try:
        llm_client = create_llm_client()
        console.print(f"[bold green]✅ 已加载 LLM 提供商：[/bold green] {provider}")
        if provider == "ollama":
            console.print(f"[dim] 模型：{config.ollama_model}[/dim]")
        elif provider == "openai":
            console.print(f"[dim] 模型：{config.openai_model}[/dim]")
        else:
            console.print(f"[dim] 模型：{config.claude_model}[/dim]")
        console.print()
    except ValueError as e:
        console.print(f"[bold red]❌ 错误：[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    # 初始化群聊管理器
    manager = GroupChatManager(llm_client)

    # 开始对话
    console.print("[bold green]🤖 助手：[/bold green] 您好！我是您的基金投资顾问。")
    console.print()
    console.print("我会通过几个问题了解您的投资需求，然后为您推荐合适的基金组合。")
    console.print("让我们开始吧！")
    console.print()

    # 显示加载动画
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description="正在初始化...", total=None)

        # 初始问候
        initial_response = asyncio.run(manager.process("你好，我想了解基金投资"))

    # 显示初始回复
    _display_response(initial_response)

    # 主对话循环
    while True:
        try:
            # 获取用户输入（使用支持退格键的方式）
            user_input = _get_user_input()

            # 跳过空输入
            if not user_input:
                continue

            # 检查退出命令
            if user_input.lower() in ["exit", "quit", "退出", "再见"]:
                console.print()
                console.print("[bold blue]🤖 助手：[/bold blue] 感谢您的使用！祝您投资顺利！")
                console.print()
                break

            # 检查重置命令
            if user_input.lower() in ["reset", "重新开始", "再来一次"]:
                manager.reset()
                console.print()
                console.print("[bold blue]🤖 助手：[/bold blue] 好的，我们重新开始。")
                console.print()
                initial_response = asyncio.run(manager.process("你好，我想了解基金投资"))
                _display_response(initial_response)
                continue

            # 处理用户输入
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="正在思考...", total=None)
                response = asyncio.run(manager.process(user_input))

            # 显示回复
            _display_response(response)

            # 检查是否完成推荐
            if manager.get_current_stage() == GroupChatManager.STAGE_RECOMMENDATION:
                # 推荐完成后，询问用户是否有其他问题
                console.print()
                console.print("[dim]💡 提示：您可以继续提问，或输入'退出'结束对话[/dim]")

        except KeyboardInterrupt:
            console.print()
            console.print("[bold blue]🤖 助手：[/bold blue] 对话已中断。")
            break

    console.print()


@app.command()
def version():
    """显示版本信息"""
    console.print("[bold blue]基金推荐助手[/bold blue] v0.1.0")
    console.print()
    console.print(f"当前 LLM 提供商：{config.llm_provider}")
    console.print()
    console.print("技术栈：")
    console.print("  - Python 3.10+")
    console.print("  - AutoGen (多 Agent 框架)")
    console.print("  - LLM: Anthropic/OpenAI/Ollama")
    console.print("  - AKShare (基金数据)")
    console.print()


@app.command()
def config_status():
    """显示配置状态"""
    console.print("[bold]当前配置状态[/bold]\n")

    # LLM 配置
    console.print(f"LLM 提供商：{config.llm_provider}")
    console.print(f"当前模型：{config.current_model}")
    console.print()

    # API Key 配置
    if config.llm_provider == "anthropic":
        api_key_status = "✅ 已配置" if config.anthropic_api_key else "❌ 未配置"
        console.print(f"Anthropic API Key: {api_key_status}")
    elif config.llm_provider == "openai":
        api_key_status = "✅ 已配置" if config.openai_api_key else "❌ 未配置"
        console.print(f"OpenAI API Key: {api_key_status}")
    else:
        console.print(f"Ollama Base URL: {config.ollama_base_url or 'http://localhost:11434/v1'}")

    # 数据源配置
    tushare_status = "✅ 已配置" if config.tushare_token else "⚠️  未配置（可选）"
    console.print(f"Tushare Token: {tushare_status}")

    jq_status = "✅ 已配置" if config.jq_username else "⚠️  未配置（可选）"
    console.print(f"聚宽账号：{jq_status}")

    # 缓存配置
    console.print(f"\n数据库路径：{config.db_path}")
    console.print(f"数据更新间隔：{config.data_update_interval} 小时")


def _display_response(response: str):
    """
    格式化显示回复

    Args:
        response: AI 回复内容
    """
    console.print()

    # 检查是否有特殊标记
    if "【需求收集完成】" in response:
        console.print(Panel(
            Markdown(response.replace("【需求收集完成】", "")),
            title="[bold green]✅ 需求收集完成[/bold green]",
            border_style="green"
        ))
    elif "【风险评估完成】" in response:
        # 提取风险等级
        import re
        match = re.search(r"风险等级：(\w+ 型)", response)
        risk_level = match.group(1) if match else "未知"
        console.print(Panel(
            Markdown(response.replace("【风险评估完成】", "")),
            title=f"[bold blue]📊 风险评估完成：{risk_level}[/bold blue]",
            border_style="blue"
        ))
    elif "【系统" in response:
        console.print(f"[yellow]{response}[/yellow]")
    else:
        console.print(Markdown(response))

    console.print()


if __name__ == "__main__":
    app()
