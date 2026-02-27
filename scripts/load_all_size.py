#!/usr/bin/env python3
"""
加载所有基金的规模数据
"""

import asyncio
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cache.db import cache_db
from src.services.akshare_client import akshare_client


async def load_all_fund_size():
    """加载所有基金的规模数据"""
    print('=' * 60)
    print('加载所有基金资产规模数据')
    print('=' * 60)

    # 从数据库获取所有基金代码
    conn = cache_db._get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT fund_code, fund_name FROM fund_basic')
    all_funds = [{'fund_code': row['fund_code'], 'fund_name': row['fund_name']}
                 for row in cursor.fetchall()]
    conn.close()

    print(f'\n共获取到 {len(all_funds)} 只基金')

    start_time = datetime.now()
    success_count, error_count, skip_count = 0, 0, 0

    for i, fund in enumerate(all_funds, 1):
        fund_code = fund['fund_code']

        try:
            # 检查是否已有数据（7 天内）
            existing = cache_db.get_fund_basic(fund_code)
            if existing and existing.get('net_asset_size') and existing.get('share_size'):
                if existing.get('updated_at'):
                    last_update = datetime.strptime(existing['updated_at'].split('.')[0], '%Y-%m-%d %H:%M:%S')
                    if (datetime.now() - last_update).days < 7:
                        skip_count += 1
                        if i % 5000 == 0:
                            print(f'  进度：{i}/{len(all_funds)} - {fund_code} - 已有数据 [跳过]')
                        continue

            # 获取规模数据
            size_info = await akshare_client.get_fund_size(fund_code)

            if size_info and (size_info.get('net_asset_size') or size_info.get('share_size')):
                cache_db.save_fund_basic(fund_code, {
                    'fund_code': fund_code,
                    'net_asset_size': size_info.get('net_asset_size', ''),
                    'share_size': size_info.get('share_size', '')
                })
                success_count += 1
                if i % 1000 == 0 or i <= 5:
                    print(f'  进度：{i}/{len(all_funds)} - {fund_code} - 成功：{size_info.get("net_asset_size", "N/A")}')
            else:
                error_count += 1
                if i % 1000 == 0:
                    print(f'  进度：{i}/{len(all_funds)} - {fund_code} - 返回空数据')

        except Exception as e:
            error_count += 1
            if i % 1000 == 0:
                print(f'  进度：{i}/{len(all_funds)} - {fund_code} - 错误：{str(e)[:40]}')

        if i % 5000 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f'\n  [{i}/{len(all_funds)}] 耗时：{elapsed:.1f}s | 成功:{success_count} | 失败:{error_count} | 跳过:{skip_count}\n')

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f'\n✅ 完成！')
    print(f'   成功：{success_count} 只 | 失败：{error_count} 只 | 跳过:{skip_count} 只')
    print(f'   总耗时：{elapsed:.1f}s ({elapsed/60:.1f} 分钟)')

    cache_db.log_update('size_all_funds', 'success', f'Loaded {success_count} funds')


if __name__ == '__main__':
    asyncio.run(load_all_fund_size())
