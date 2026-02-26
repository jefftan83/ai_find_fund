#!/usr/bin/env python3
"""
基金数据加载工具 - 统一脚本

整合了以下功能：
1. 初始化基金基本信息、评级、持仓
2. 加载当日净值
3. 加载基金历史净值
4. 加载基金规模数据
"""

import asyncio
import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.akshare_client import akshare_client
from src.cache.db import cache_db


# ========== 通用工具函数 ==========

def get_fund_codes_from_db(limit: int = 100, fund_type: str = None) -> List[str]:
    """从数据库获取基金代码列表"""
    conn = cache_db._get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if fund_type:
        cursor.execute("SELECT fund_code FROM fund_basic WHERE fund_type LIKE ? LIMIT ?",
                      (f"%{fund_type}%", limit))
    else:
        cursor.execute("SELECT fund_code FROM fund_basic LIMIT ?", (limit,))

    fund_codes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return fund_codes


def check_existing_nav(fund_code: str) -> int:
    """检查基金已有的净值记录数"""
    conn = cache_db._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM fund_nav WHERE fund_code = ?", (fund_code,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def check_existing_size(fund_code: str) -> Optional[dict]:
    """检查基金是否已有规模数据（7 天内）"""
    conn = cache_db._get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT net_asset_size, share_size, updated_at
        FROM fund_basic
        WHERE fund_code = ?
    """, (fund_code,))
    row = cursor.fetchone()
    conn.close()

    if row and row['net_asset_size'] and row['share_size']:
        if row['updated_at']:
            last_update = datetime.strptime(
                row['updated_at'].split('.')[0], '%Y-%m-%d %H:%M:%S'
            )
            if (datetime.now() - last_update).days < 7:
                return {'net_asset_size': row['net_asset_size'], 'share_size': row['share_size']}
    return None


# ========== 数据加载功能 ==========

async def load_fund_basic(limit: Optional[int] = None):
    """初始化/更新基金基本信息"""
    print("\n=== 加载基金基本信息 ===\n")

    try:
        fund_list = await akshare_client.get_fund_list()
        if limit:
            fund_list = fund_list[:limit]

        print(f"获取到 {len(fund_list)} 只基金")

        for i, fund in enumerate(fund_list, 1):
            cache_db.save_fund_basic(fund["fund_code"], fund)
            if i % 5000 == 0:
                print(f"  已保存 {i}/{len(fund_list)} 只基金...")

        cache_db.log_update("fund_basic", "success", f"Updated {len(fund_list)} funds")
        print(f"\n✅ 完成！共 {len(fund_list)} 只基金")
        return len(fund_list)

    except Exception as e:
        cache_db.log_update("fund_basic", "error", str(e))
        print(f"\n❌ 失败：{e}")
        return 0


async def load_fund_ratings():
    """初始化/更新基金评级"""
    print("\n=== 加载基金评级 ===\n")

    try:
        ratings = await akshare_client.get_fund_rating()
        print(f"获取到 {len(ratings)} 条评级记录")

        rating_date = datetime.now().strftime("%Y-%m-%d")
        for i, rating in enumerate(ratings, 1):
            cache_db.save_fund_rating(
                rating["fund_code"], rating_date, rating["rating_agency"],
                {"1y": rating.get("rating_1y", 0), "2y": rating.get("rating_2y", 0), "3y": rating.get("rating_3y", 0)}
            )
            if i % 5000 == 0:
                print(f"  已保存 {i}/{len(ratings)} 条评级...")

        cache_db.log_update("fund_rating", "success", f"Updated {len(ratings)} ratings")
        print(f"\n✅ 完成！共 {len(ratings)} 条记录")
        return len(ratings)

    except Exception as e:
        cache_db.log_update("fund_rating", "error", str(e))
        print(f"\n❌ 失败：{e}")
        return 0


async def load_fund_holdings(fund_codes: List[str] = None, limit: int = 100):
    """加载基金持仓数据"""
    print("\n=== 加载基金持仓 ===\n")

    if fund_codes is None:
        fund_codes = get_fund_codes_from_db(limit=limit)

    print(f"准备处理 {len(fund_codes)} 只基金的持仓数据")

    success_count, error_count = 0, 0

    for i, fund_code in enumerate(fund_codes, 1):
        try:
            holdings = await akshare_client.get_fund_holdings(fund_code)
            if holdings:
                report_date = datetime.now().strftime("%Y-%m-%d")
                cache_db.save_fund_holdings(fund_code, report_date, holdings)
                success_count += 1
        except Exception:
            error_count += 1

        if i % 50 == 0:
            print(f"  进度：{i}/{len(fund_codes)} (成功:{success_count}, 失败:{error_count})")

    cache_db.log_update("fund_holdings", "success", f"Updated {success_count} holdings")
    print(f"\n✅ 完成！成功 {success_count} 只，失败 {error_count} 只")
    return success_count


async def load_daily_nav():
    """加载所有基金的当日净值"""
    print("\n=== 加载当日净值 ===\n")
    start_time = datetime.now()

    try:
        daily_nav = await akshare_client.get_daily_nav()
        print(f"获取到 {len(daily_nav)} 条净值记录")

        saved_count, skip_count, error_count = 0, 0, 0

        for i, nav in enumerate(daily_nav, 1):
            try:
                fund_code = nav.get("fund_code", "")
                nav_date = nav.get("nav_date", "")
                if not fund_code or not nav_date:
                    continue

                conn = cache_db._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM fund_nav WHERE fund_code = ? AND nav_date = ?", (fund_code, nav_date))
                if cursor.fetchone():
                    skip_count += 1
                    conn.close()
                    continue

                cache_db.save_fund_nav(fund_code, nav_date, nav)
                saved_count += 1
                conn.close()

            except Exception:
                error_count += 1

            if i % 5000 == 0:
                print(f"  进度：{i}/{len(daily_nav)} (新增:{saved_count}, 跳过:{skip_count}, 错误:{error_count})")

        elapsed = (datetime.now() - start_time).total_seconds()
        cache_db.log_update("daily_nav", "success", f"Added {saved_count} records")

        print(f"\n✅ 完成！")
        print(f"   新增：{saved_count} 条 | 跳过：{skip_count} 条 | 错误：{error_count} 条")
        print(f"   耗时：{elapsed:.1f}s")
        return saved_count

    except Exception as e:
        cache_db.log_update("daily_nav", "error", str(e))
        print(f"\n❌ 失败：{e}")
        return 0


async def load_fund_history_batch(fund_codes: List[str], batch_name: str = ""):
    """批量加载基金历史净值"""
    print(f"\n=== 批量加载历史净值 [{batch_name}] ===\n")
    print(f"准备加载 {len(fund_codes)} 只基金\n")

    start_time = datetime.now()
    success_count, error_count, skip_count = 0, 0, 0

    for i, fund_code in enumerate(fund_codes, 1):
        try:
            existing = check_existing_nav(fund_code)
            if existing >= 100:
                skip_count += 1
                if i % 50 == 0:
                    print(f"  进度：{i}/{len(fund_codes)} - {fund_code} - 已有 ({existing}条)")
                continue

            history = await akshare_client.get_fund_history(fund_code)
            if history:
                saved = 0
                for record in history:
                    nav_date = record.get("nav_date", "")
                    if nav_date:
                        cache_db.save_fund_nav(fund_code, nav_date, record)
                        saved += 1
                success_count += 1
                if i % 50 == 0 or i <= 5:
                    print(f"  进度：{i}/{len(fund_codes)} - {fund_code} - 成功 ({saved}条)")
            else:
                error_count += 1
                if i % 50 == 0:
                    print(f"  进度：{i}/{len(fund_codes)} - {fund_code} - 返回空数据")

        except Exception as e:
            error_count += 1
            if i % 50 == 0 or i <= 3:
                print(f"  进度：{i}/{len(fund_codes)} - {fund_code} - 错误：{str(e)[:40]}")

        if i % 100 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\n  [{i}/{len(fund_codes)}] 耗时：{elapsed:.1f}s | 成功:{success_count} | 失败:{error_count} | 跳过:{skip_count}\n")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n✅ 完成！")
    print(f"   成功：{success_count} 只 | 失败：{error_count} 只 | 跳过：{skip_count} 只")
    print(f"   总耗时：{elapsed:.1f}s ({elapsed/60:.1f} 分钟)")

    cache_db.log_update(f"history_batch_{batch_name}", "success", f"Loaded {success_count} funds")
    return success_count


async def load_top_n_history(top_n: int = 100):
    """加载前 N 只基金的历史净值"""
    fund_codes = get_fund_codes_from_db(limit=top_n)
    await load_fund_history_batch(fund_codes, f"top{top_n}")


async def load_history_by_type(fund_type: str = "混合型", limit: int = 50):
    """按基金类型加载历史净值"""
    fund_codes = get_fund_codes_from_db(limit=limit, fund_type=fund_type)
    await load_fund_history_batch(fund_codes, f"{fund_type}_limit{limit}")


async def load_single_fund_history(fund_code: str):
    """加载单只基金的历史净值"""
    print(f"\n=== 加载 {fund_code} 的历史净值 ===\n")

    try:
        history = await akshare_client.get_fund_history(fund_code)
        if history:
            saved = 0
            for record in history:
                nav_date = record.get("nav_date", "")
                if nav_date:
                    cache_db.save_fund_nav(fund_code, nav_date, record)
                    saved += 1
            print(f"✅ 成功加载 {saved} 条历史净值记录")
            return saved
        else:
            print("❌ 返回空数据")
            return 0
    except Exception as e:
        print(f"❌ 加载失败：{e}")
        return 0


async def load_fund_size_batch(fund_codes: List[str], batch_name: str = ""):
    """批量加载基金规模数据"""
    print(f"\n=== 批量加载基金规模 [{batch_name}] ===\n")
    print(f"准备加载 {len(fund_codes)} 只基金\n")

    start_time = datetime.now()
    success_count, error_count, skip_count = 0, 0, 0

    for i, fund_code in enumerate(fund_codes, 1):
        try:
            existing = check_existing_size(fund_code)
            if existing:
                skip_count += 1
                if i % 50 == 0:
                    print(f"  进度：{i}/{len(fund_codes)} - {fund_code} - 已有数据")
                continue

            size_info = await akshare_client.get_fund_size(fund_code)
            if size_info and (size_info.get("net_asset_size") or size_info.get("share_size")):
                cache_db.save_fund_basic(fund_code, {
                    "fund_code": fund_code,
                    "net_asset_size": size_info.get("net_asset_size", ""),
                    "share_size": size_info.get("share_size", "")
                })
                success_count += 1
                if i % 50 == 0 or i <= 5:
                    print(f"  进度：{i}/{len(fund_codes)} - {fund_code} - 成功 ({size_info.get('net_asset_size', 'N/A')})")
            else:
                error_count += 1
                if i % 50 == 0:
                    print(f"  进度：{i}/{len(fund_codes)} - {fund_code} - 返回空数据")

        except Exception as e:
            error_count += 1
            if i % 50 == 0 or i <= 3:
                print(f"  进度：{i}/{len(fund_codes)} - {fund_code} - 错误：{str(e)[:40]}")

        if i % 100 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\n  [{i}/{len(fund_codes)}] 耗时：{elapsed:.1f}s | 成功:{success_count} | 失败:{error_count} | 跳过:{skip_count}\n")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n✅ 完成！")
    print(f"   成功：{success_count} 只 | 失败：{error_count} 只 | 跳过：{skip_count} 只")
    print(f"   总耗时：{elapsed:.1f}s ({elapsed/60:.1f} 分钟)")

    cache_db.log_update(f"size_batch_{batch_name}", "success", f"Loaded {success_count} funds")
    return success_count


async def load_size_by_type(fund_type: str = "混合型", limit: int = 50):
    """按基金类型加载规模数据"""
    fund_codes = get_fund_codes_from_db(limit=limit, fund_type=fund_type)
    await load_fund_size_batch(fund_codes, f"{fund_type}_size")


async def load_screened_funds_size():
    """加载推荐基金池的规模数据（4 种类型 x 50 只）"""
    print("\n=== 加载推荐基金池规模数据 ===\n")
    for risk_type, fund_type in [("保守型", "债券型"), ("稳健型", "混合型"), ("积极型", "混合型"), ("激进型", "股票型")]:
        print(f"\n加载 {risk_type} ({fund_type}) 前 50 只基金规模...")
        fund_codes = get_fund_codes_from_db(limit=50, fund_type=fund_type)
        await load_fund_size_batch(fund_codes, f"screened_{fund_type}")


# ========== 主菜单 ==========

async def main():
    """主函数"""
    print("=" * 60)
    print("基金数据加载工具")
    print("=" * 60)

    while True:
        print("\n请选择要执行的操作:")
        print("\n【基本信息】")
        print("  1. 加载基金基本信息")
        print("  2. 加载基金评级")
        print("  3. 加载基金持仓")
        print("\n【净值数据】")
        print("  4. 加载当日净值（全部基金）")
        print("  5. 加载单只基金历史净值")
        print("  6. 加载前 N 只基金历史净值")
        print("  7. 按基金类型加载历史净值")
        print("\n【规模数据】")
        print("  8. 加载前 N 只基金规模")
        print("  9. 按基金类型加载规模")
        print("  10. 加载推荐基金池规模（4 类型 x50 只）")
        print("\n【其他】")
        print("  0. 退出")

        choice = input("\n请输入选项 (0-10): ").strip()

        if choice == '0':
            print("已退出")
            return
        elif choice == '1':
            limit = input("请输入数量限制 (默认全部): ").strip()
            limit = int(limit) if limit else None
            await load_fund_basic(limit)
        elif choice == '2':
            await load_fund_ratings()
        elif choice == '3':
            limit = input("请输入要处理的基金数量 (默认 100): ").strip()
            limit = int(limit) if limit else 100
            await load_fund_holdings(limit=limit)
        elif choice == '4':
            await load_daily_nav()
        elif choice == '5':
            fund_code = input("请输入基金代码：").strip()
            if fund_code:
                await load_single_fund_history(fund_code)
        elif choice == '6':
            top_n = input("请输入要加载的基金数量 (默认 100): ").strip()
            top_n = int(top_n) if top_n else 100
            print(f"\n⚠️  提示：每只基金约需 1-2 秒，{top_n} 只基金预计需要 {top_n*1.5/60:.1f} 分钟")
            confirm = input("是否继续？(y/N): ").strip()
            if confirm.lower() == 'y':
                await load_top_n_history(top_n)
        elif choice == '7':
            fund_type = input("请输入基金类型 (如 混合型/股票型/债券型): ").strip()
            limit = input("请输入数量限制 (默认 50): ").strip()
            limit = int(limit) if limit else 50
            print(f"\n⚠️  提示：每只基金约需 1-2 秒，{limit} 只基金预计需要 {limit*1.5/60:.1f} 分钟")
            confirm = input("是否继续？(y/N): ").strip()
            if confirm.lower() == 'y':
                await load_history_by_type(fund_type, limit)
        elif choice == '8':
            top_n = input("请输入要加载的基金数量 (默认 100): ").strip()
            top_n = int(top_n) if top_n else 100
            print(f"\n⚠️  提示：每只基金约需 1-2 秒，{top_n} 只基金预计需要 {top_n*1.5/60:.1f} 分钟")
            confirm = input("是否继续？(y/N): ").strip()
            if confirm.lower() == 'y':
                fund_codes = get_fund_codes_from_db(limit=top_n)
                await load_fund_size_batch(fund_codes, f"top{top_n}")
        elif choice == '9':
            fund_type = input("请输入基金类型 (如 混合型/股票型/债券型): ").strip()
            limit = input("请输入数量限制 (默认 50): ").strip()
            limit = int(limit) if limit else 50
            await load_size_by_type(fund_type, limit)
        elif choice == '10':
            print(f"\n⚠️  提示：共约 200 只基金，预计需要 5-6 分钟")
            confirm = input("是否继续？(y/N): ").strip()
            if confirm.lower() == 'y':
                await load_screened_funds_size()
        else:
            print("无效的选项")


if __name__ == "__main__":
    asyncio.run(main())
