"""SQLite 缓存数据库管理"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from src.utils.config import config


class CacheDB:
    """基金数据缓存数据库"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 基金基本信息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fund_basic (
                    fund_code TEXT PRIMARY KEY,
                    fund_name TEXT,
                    fund_type TEXT,
                    company TEXT,
                    manager TEXT,
                    established_date TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 基金净值表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fund_nav (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fund_code TEXT,
                    nav_date DATE,
                    unit_nav REAL,
                    accumulated_nav REAL,
                    daily_growth REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(fund_code, nav_date)
                )
            """)

            # 基金持仓表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fund_holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fund_code TEXT,
                    report_date DATE,
                    stock_code TEXT,
                    stock_name TEXT,
                    holding_ratio REAL,
                    holding_amount INTEGER,
                    holding_value REAL,
                    stock_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 基金评级表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fund_rating (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fund_code TEXT,
                    rating_date DATE,
                    rating_agency TEXT,
                    rating_1y INTEGER,
                    rating_2y INTEGER,
                    rating_3y INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 数据更新日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS update_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_type TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    message TEXT
                )
            """)

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nav_code_date ON fund_nav(fund_code, nav_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_code ON fund_holdings(fund_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating_code ON fund_rating(fund_code)")

            conn.commit()

    # ========== 基金基本信息 ==========
    def save_fund_basic(self, fund_code: str, data: Dict[str, Any]):
        """保存基金基本信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO fund_basic
                (fund_code, fund_name, fund_type, company, manager, established_date, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                fund_code,
                data.get("fund_name"),
                data.get("fund_type"),
                data.get("company"),
                data.get("manager"),
                data.get("established_date"),
                datetime.now()
            ))
            conn.commit()

    def get_fund_basic(self, fund_code: str) -> Optional[Dict[str, Any]]:
        """获取基金基本信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fund_basic WHERE fund_code = ?", (fund_code,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    # ========== 基金净值 ==========
    def save_fund_nav(self, fund_code: str, nav_date: str, data: Dict[str, Any]):
        """保存基金净值"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO fund_nav
                (fund_code, nav_date, unit_nav, accumulated_nav, daily_growth)
                VALUES (?, ?, ?, ?, ?)
            """, (
                fund_code,
                nav_date,
                data.get("unit_nav"),
                data.get("accumulated_nav"),
                data.get("daily_growth")
            ))
            conn.commit()

    def get_fund_nav(self, fund_code: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """获取基金历史净值"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM fund_nav WHERE fund_code = ?"
            params = [fund_code]

            if start_date:
                query += " AND nav_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND nav_date <= ?"
                params.append(end_date)

            query += " ORDER BY nav_date DESC"

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_nav(self, fund_code: str) -> Optional[Dict[str, Any]]:
        """获取最新净值"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM fund_nav WHERE fund_code = ? ORDER BY nav_date DESC LIMIT 1
            """, (fund_code,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    # ========== 基金持仓 ==========
    def save_fund_holdings(self, fund_code: str, report_date: str, holdings: List[Dict[str, Any]]):
        """保存基金持仓"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for holding in holdings:
                cursor.execute("""
                    INSERT INTO fund_holdings
                    (fund_code, report_date, stock_code, stock_name, holding_ratio,
                     holding_amount, holding_value, stock_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fund_code,
                    report_date,
                    holding.get("stock_code"),
                    holding.get("stock_name"),
                    holding.get("holding_ratio"),
                    holding.get("holding_amount"),
                    holding.get("holding_value"),
                    holding.get("stock_type")
                ))
            conn.commit()

    def get_latest_holdings(self, fund_code: str) -> List[Dict[str, Any]]:
        """获取最新持仓"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM fund_holdings
                WHERE fund_code = ?
                ORDER BY report_date DESC LIMIT 10
            """, (fund_code,))
            return [dict(row) for row in cursor.fetchall()]

    # ========== 基金评级 ==========
    def save_fund_rating(self, fund_code: str, rating_date: str, agency: str, ratings: Dict[str, int]):
        """保存基金评级"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fund_rating
                (fund_code, rating_date, rating_agency, rating_1y, rating_2y, rating_3y)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                fund_code,
                rating_date,
                agency,
                ratings.get("1y"),
                ratings.get("2y"),
                ratings.get("3y")
            ))
            conn.commit()

    def get_latest_rating(self, fund_code: str) -> Optional[Dict[str, Any]]:
        """获取最新评级"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM fund_rating
                WHERE fund_code = ? ORDER BY rating_date DESC LIMIT 1
            """, (fund_code,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    # ========== 更新日志 ==========
    def log_update(self, data_type: str, status: str, message: str = ""):
        """记录更新日志"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO update_log (data_type, status, message)
                VALUES (?, ?, ?)
            """, (data_type, status, message))
            conn.commit()

    def get_last_update_time(self, data_type: str) -> Optional[datetime]:
        """获取最后更新时间"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT updated_at FROM update_log
                WHERE data_type = ? AND status = 'success'
                ORDER BY updated_at DESC LIMIT 1
            """, (data_type,))
            row = cursor.fetchone()
            if row:
                return datetime.fromisoformat(row["updated_at"])
            return None

    # ========== 缓存清理 ==========
    def clear_old_data(self, days: int = 365):
        """清理旧数据"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cutoff_date = (datetime.now().date() - __import__("datetime").timedelta(days=days)).isoformat()

            # 清理旧净值数据
            cursor.execute("DELETE FROM fund_nav WHERE nav_date < ?", (cutoff_date,))

            # 清理旧评级数据
            cursor.execute("DELETE FROM fund_rating WHERE rating_date < ?", (cutoff_date,))

            conn.commit()


# 全局缓存实例
cache_db = CacheDB()
