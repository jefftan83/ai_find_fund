#!/usr/bin/env python3
"""
批量加载基金净值数据

已迁移至 data_loader.py
此脚本保留用于向后兼容
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_loader import load_daily_nav, load_single_fund_history


async def main():
    """主函数 - 已迁移到 data_loader.py"""
    print("=" * 60)
    print("批量加载基金净值工具")
    print("=" * 60)
    print("\n⚠️  此脚本已迁移至 data_loader.py")
    print("💡  请直接运行：python scripts/data_loader.py")
    print()

    print("\n请选择要执行的操作:")
    print("1. 加载当日净值（全部基金）")
    print("2. 加载单只基金历史净值")
    print("0. 退出")

    choice = input("\n请输入选项 (0-2): ").strip()

    if choice == '0':
        print("已退出")
        return
    elif choice == '1':
        await load_daily_nav()
    elif choice == '2':
        fund_code = input("请输入基金代码：").strip()
        if fund_code:
            await load_single_fund_history(fund_code)
    else:
        print("无效的选项")


if __name__ == "__main__":
    asyncio.run(main())
