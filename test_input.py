#!/usr/bin/env python3
"""测试退格键输入"""

import readline
from rich.console import Console
from rich.prompt import Prompt

console = Console()

console.print("[bold green]=== 退格键输入测试 ===[/bold green]")
console.print()
console.print("[dim]请输入一些文字，然后按退格键测试是否可以删除。[/dim]")
console.print("[dim]输入 'quit' 退出测试。[/dim]")
console.print()

while True:
    try:
        user_input = Prompt.ask("\n[bold cyan]您[/bold cyan]", console=console)

        if user_input.lower() in ['quit', 'exit', 'q']:
            console.print("[green]测试结束！[/green]")
            break

        console.print(f"[yellow]您输入了：{user_input}[/yellow]")

    except (EOFError, KeyboardInterrupt):
        console.print("\n[red]测试中断[/red]")
        break
