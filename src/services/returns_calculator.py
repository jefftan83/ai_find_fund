"""
基金收益率计算工具

当实时数据源不稳定时，通过本地历史净值数据计算收益率
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from src.cache.db import cache_db


def calc_returns(fund_code: str) -> Dict[str, float]:
    """
    通过历史净值计算基金收益率

    Args:
        fund_code: 基金代码

    Returns:
        包含各时间段收益率的字典：
        - return_1m: 近 1 月收益率
        - return_3m: 近 3 月收益率
        - return_6m: 近 6 月收益率
        - return_1y: 近 1 年收益率
        - return_3y: 近 3 年收益率
        - return_ytd: 今年来收益率
    """
    conn = cache_db._get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取最新净值日期
    # 注意：AKShare 历史数据只提供单位净值，累计净值字段为空
    # 所以这里使用单位净值计算收益率
    cursor.execute("""
        SELECT nav_date, unit_nav
        FROM fund_nav
        WHERE fund_code = ? AND unit_nav > 0
        ORDER BY nav_date DESC
        LIMIT 1
    """, (fund_code,))

    latest = cursor.fetchone()
    if not latest:
        return {}

    latest_date = datetime.strptime(latest['nav_date'], '%Y-%m-%d')
    latest_nav = latest['unit_nav']

    if latest_nav <= 0:
        return {}

    # 计算各时间段的起始日期
    today = datetime.now()
    dates = {
        '1m': today - timedelta(days=30),
        '3m': today - timedelta(days=90),
        '6m': today - timedelta(days=180),
        '1y': today - timedelta(days=365),
        '3y': today - timedelta(days=1095),
        'ytd': datetime(today.year, 1, 1)  # 年初
    }

    returns = {}

    for period, start_date in dates.items():
        # 获取该日期附近的净值
        cursor.execute("""
            SELECT unit_nav
            FROM fund_nav
            WHERE fund_code = ?
            AND nav_date BETWEEN ? AND ?
            AND unit_nav > 0
            ORDER BY nav_date DESC
            LIMIT 1
        """, (
            fund_code,
            start_date.strftime('%Y-%m-%d'),
            (start_date + timedelta(days=7)).strftime('%Y-%m-%d')
        ))

        row = cursor.fetchone()
        if row and row['unit_nav'] > 0:
            start_nav = row['unit_nav']
            # 计算收益率
            returns[f'return_{period}'] = round((latest_nav - start_nav) / start_nav * 100, 2)
        else:
            # 没有足够历史数据，返回 0
            returns[f'return_{period}'] = 0.0

    conn.close()
    return returns


def calc_single_return(fund_code: str, days: int) -> Optional[float]:
    """
    计算指定天数的收益率

    Args:
        fund_code: 基金代码
        days: 天数

    Returns:
        收益率百分比，如果数据不足则返回 None
    """
    conn = cache_db._get_connection()
    cursor = conn.cursor()

    # 获取最新净值
    cursor.execute("""
        SELECT nav_date, unit_nav
        FROM fund_nav
        WHERE fund_code = ? AND unit_nav > 0
        ORDER BY nav_date DESC
        LIMIT 1
    """, (fund_code,))

    latest = cursor.fetchone()
    if not latest:
        conn.close()
        return None

    latest_date = datetime.strptime(latest['nav_date'], '%Y-%m-%d')
    latest_nav = latest['unit_nav']

    # 计算起始日期
    start_date = latest_date - timedelta(days=days)

    # 获取起始日期附近的净值
    cursor.execute("""
        SELECT unit_nav
        FROM fund_nav
        WHERE fund_code = ?
        AND nav_date BETWEEN ? AND ?
        AND unit_nav > 0
        ORDER BY nav_date DESC
        LIMIT 1
    """, (
        fund_code,
        start_date.strftime('%Y-%m-%d'),
        (start_date + timedelta(days=7)).strftime('%Y-%m-%d')
    ))

    row = cursor.fetchone()
    conn.close()

    if row and row['unit_nav'] > 0:
        start_nav = row['unit_nav']
        return round((latest_nav - start_nav) / start_nav * 100, 2)

    return None


def get_fund_with_returns(fund_codes: List[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    获取基金列表及其收益率（通过历史净值计算）

    Args:
        fund_codes: 基金代码列表，如果为 None 则从数据库获取
        limit: 最多处理多少只基金

    Returns:
        包含基金信息和收益率的列表
    """
    conn = cache_db._get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 如果没有指定基金代码，从数据库获取
    if fund_codes is None:
        cursor.execute("SELECT fund_code FROM fund_basic LIMIT ?", (limit,))
        fund_codes = [row['fund_code'] for row in cursor.fetchall()]

    conn.close()

    result = []
    for code in fund_codes:
        returns = calc_returns(code)
        if returns:
            result.append({
                'fund_code': code,
                **returns
            })

    return result


def bulk_calc_returns() -> Dict[str, Dict[str, float]]:
    """
    批量计算所有基金的收益率

    Returns:
        以基金代码为键的收益率字典
    """
    conn = cache_db._get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取所有有历史净值的基金代码
    cursor.execute("""
        SELECT DISTINCT fund_code FROM fund_nav
    """)
    fund_codes = [row['fund_code'] for row in cursor.fetchall()]

    conn.close()

    result = {}
    for code in fund_codes:
        returns = calc_returns(code)
        if returns:
            result[code] = returns

    return result


# 测试
if __name__ == "__main__":
    print("=== 基金收益率计算工具测试 ===\n")

    # 测试单只基金
    fund_code = "000001"
    returns = calc_returns(fund_code)

    print(f"{fund_code} 华夏成长混合:")
    for key, value in returns.items():
        print(f"  {key}: {value}%")

    # 测试多只基金
    print("\n=== 前 10 只基金收益率 ===")
    funds = get_fund_with_returns(limit=10)
    for fund in funds:
        print(f"  {fund['fund_code']}: 近 1 年={fund.get('return_1y', 'N/A')}%, 今年来={fund.get('return_ytd', 'N/A')}%")
