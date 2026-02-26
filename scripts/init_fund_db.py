#!/usr/bin/env python3
"""
基金数据库初始化工具

已迁移至 data_loader.py
此脚本保留用于向后兼容
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# 从新脚本导入功能
from scripts.data_loader import load_fund_basic, load_fund_ratings, load_fund_holdings, load_daily_nav


async def main():
    """主函数 - 已迁移到 data_loader.py"""
    print("=" * 60)
    print("基金数据库初始化工具")
    print("=" * 60)
    print("\n⚠️  此脚本已迁移至 data_loader.py")
    print("💡  请直接运行：python scripts/data_loader.py")
    print()

    print("请选择要执行的操作:")
    print("1. 初始化基金基本信息表（必选）")
    print("2. 初始化基金评级表")
    print("3. 初始化基金持仓表（耗时较长）")
    print("4. 初始化每日净值表（耗时很长，建议跳过）")
    print("5. 执行全部初始化")
    print("0. 退出")

    choice = input("\n请输入选项 (0-5): ").strip()

    if choice == '0':
        print("已退出")
        return
    elif choice == '1':
        await load_fund_basic()
    elif choice == '2':
        await load_fund_ratings()
    elif choice == '3':
        limit = input("请输入要处理的基金数量 (默认 100): ").strip()
        limit = int(limit) if limit else 100
        await load_fund_holdings(limit=limit)
    elif choice == '4':
        await load_daily_nav()
    elif choice == '5':
        print("\n开始执行全部初始化...")
        await load_fund_basic()
        await load_fund_ratings()
        print("\n⚠️  基金持仓表初始化耗时较长，是否继续？")
        response = input("继续？(y/N): ").strip()
        if response.lower() == 'y':
            await load_fund_holdings(limit=200)
    else:
        print("无效的选项")


if __name__ == "__main__":
    asyncio.run(main())
