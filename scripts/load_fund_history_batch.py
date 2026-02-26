#!/usr/bin/env python3
"""
批量加载基金历史净值数据

已迁移至 data_loader.py
此脚本保留用于向后兼容
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_loader import load_fund_history_batch, load_top_n_history, load_history_by_type


async def main():
    """主函数 - 已迁移到 data_loader.py"""
    print("=" * 60)
    print("批量加载基金历史净值工具")
    print("=" * 60)
    print("\n⚠️  此脚本已迁移至 data_loader.py")
    print("💡  请直接运行：python scripts/data_loader.py")
    print()

    print("\n请选择加载模式:")
    print("1. 加载前 N 只基金的历史净值")
    print("2. 按基金类型加载（混合型/股票型/债券型等）")
    print("3. 自定义基金代码列表")
    print("0. 退出")

    choice = input("\n请输入选项 (0-3): ").strip()

    if choice == '0':
        print("已退出")
        return

    elif choice == '1':
        top_n = input("请输入要加载的基金数量 (默认 100): ").strip()
        top_n = int(top_n) if top_n else 100
        print(f"\n⚠️  提示：每只基金约需 1-2 秒，{top_n} 只基金预计需要 {top_n*1.5/60:.1f} 分钟")
        confirm = input("是否继续？(y/N): ").strip()
        if confirm.lower() == 'y':
            await load_top_n_history(top_n)
        else:
            print("已取消")

    elif choice == '2':
        fund_type = input("请输入基金类型 (如 混合型/股票型/债券型): ").strip()
        limit = input("请输入数量限制 (默认 50): ").strip()
        limit = int(limit) if limit else 50
        print(f"\n⚠️  提示：每只基金约需 1-2 秒，{limit} 只基金预计需要 {limit*1.5/60:.1f} 分钟")
        confirm = input("是否继续？(y/N): ").strip()
        if confirm.lower() == 'y':
            await load_history_by_type(fund_type, limit)
        else:
            print("已取消")

    elif choice == '3':
        input_str = input("请输入基金代码 (用逗号或空格分隔): ").strip()
        fund_codes = input_str.replace(',', ' ').split()
        print(f"\n⚠️  提示：每只基金约需 1-2 秒，{len(fund_codes)} 只基金预计需要 {len(fund_codes)*1.5/60:.1f} 分钟")
        confirm = input("是否继续？(y/N): ").strip()
        if confirm.lower() == 'y':
            await load_fund_history_batch(fund_codes, "custom")
        else:
            print("已取消")

    else:
        print("无效的选项")


if __name__ == "__main__":
    asyncio.run(main())
