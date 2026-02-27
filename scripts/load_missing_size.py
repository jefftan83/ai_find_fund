#!/usr/bin/env python3
"""
补加载缺失规模数据的基金
"""

import asyncio
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cache.db import cache_db
from src.services.akshare_client import akshare_client


async def load_missing_fund_size():
    """加载缺失规模数据的基金"""
    print('=' * 60)
    print('补加载缺失规模数据的基金')
    print('=' * 60)

    # 从数据库获取所有缺少规模数据的基金代码
    conn = cache_db._get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT fund_code, fund_name FROM fund_basic
        WHERE (net_asset_size IS NULL OR net_asset_size = '' OR net_asset_size = '---')
           OR (share_size IS NULL OR share_size = '' OR share_size = '---')
    ''')
    missing_funds = [{'fund_code': row['fund_code'], 'fund_name': row['fund_name']}
                     for row in cursor.fetchall()]
    conn.close()

    print(f'\n共找到 {len(missing_funds)} 只基金缺少规模数据')

    if len(missing_funds) == 0:
        print('所有基金已有规模数据，无需加载')
        return

    start_time = datetime.now()
    success_count, error_count, skip_count = 0, 0, 0

    for i, fund in enumerate(missing_funds, 1):
        fund_code = fund['fund_code']

        try:
            # 获取规模数据
            size_info = await akshare_client.get_fund_size(fund_code)

            if size_info and (size_info.get('net_asset_size') or size_info.get('share_size')):
                # 过滤掉 '---' 这样的无效数据
                net_size = size_info.get('net_asset_size', '')
                share_size = size_info.get('share_size', '')

                if net_size and net_size not in ['---', ''] and share_size and share_size not in ['---', '']:
                    cache_db.save_fund_basic(fund_code, {
                        'fund_code': fund_code,
                        'net_asset_size': net_size,
                        'share_size': share_size
                    })
                    success_count += 1
                    if i % 100 == 0 or i <= 10:
                        print(f'  进度：{i}/{len(missing_funds)} - {fund_code} - 成功：{net_size}')
                else:
                    error_count += 1
                    if i % 100 == 0:
                        print(f'  进度：{i}/{len(missing_funds)} - {fund_code} - 返回无效数据：{net_size}')
            else:
                error_count += 1
                if i % 100 == 0:
                    print(f'  进度：{i}/{len(missing_funds)} - {fund_code} - 返回空数据')

        except Exception as e:
            error_count += 1
            if i % 100 == 0:
                print(f'  进度：{i}/{len(missing_funds)} - {fund_code} - 错误：{str(e)[:50]}')

        if i % 500 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f'\n  [{i}/{len(missing_funds)}] 耗时：{elapsed:.1f}s | 成功:{success_count} | 失败:{error_count} | 跳过:{skip_count}\n')

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f'\n✅ 完成！')
    print(f'   成功：{success_count} 只 | 失败：{error_count} 只 | 跳过:{skip_count} 只')
    print(f'   总耗时：{elapsed:.1f}s ({elapsed/60:.1f} 分钟)')

    cache_db.log_update('size_missing_funds', 'success', f'Loaded {success_count} funds')


if __name__ == '__main__':
    asyncio.run(load_missing_fund_size())
