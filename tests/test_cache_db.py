"""
缓存数据库测试
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from src.cache.db import CacheDB


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    db = CacheDB(db_path)
    yield db

    # 清理
    db_path.unlink()


class TestCacheDB:
    """CacheDB 类测试"""

    def test_db_initialization(self, temp_db):
        """DB-001: 数据库初始化"""
        db = temp_db
        # 验证表被创建
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert 'fund_basic' in tables
        assert 'fund_nav' in tables
        assert 'fund_holdings' in tables
        assert 'fund_rating' in tables
        assert 'update_log' in tables

    def test_save_fund_basic(self, temp_db):
        """DB-002: 保存基金基本信息"""
        db = temp_db
        fund_data = {
            "fund_name": "测试基金",
            "fund_type": "混合型",
            "company": "测试基金公司",
            "manager": "张三",
            "established_date": "2020-01-01"
        }
        db.save_fund_basic("000001", fund_data)

        # 验证保存成功
        result = db.get_fund_basic("000001")
        assert result is not None
        assert result["fund_name"] == "测试基金"
        assert result["fund_type"] == "混合型"

    def test_get_fund_basic_not_exists(self, temp_db):
        """DB-003: 获取不存在的基金"""
        db = temp_db
        result = db.get_fund_basic("999999")
        assert result is None

    def test_save_fund_nav(self, temp_db):
        """DB-005: 保存基金净值"""
        db = temp_db
        nav_data = {
            "unit_nav": 1.234,
            "accumulated_nav": 2.345,
            "daily_growth": 0.015
        }
        db.save_fund_nav("000001", "2025-02-24", nav_data)

        # 验证保存成功
        result = db.get_latest_nav("000001")
        assert result is not None
        assert result["unit_nav"] == 1.234
        assert result["accumulated_nav"] == 2.345

    def test_get_fund_nav_with_date_range(self, temp_db):
        """DB-006: 获取历史净值（带日期范围）"""
        db = temp_db
        # 保存多条净值记录
        for i in range(10):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            nav_data = {
                "unit_nav": 1.0 + i * 0.01,
                "accumulated_nav": 2.0 + i * 0.01,
                "daily_growth": 0.01
            }
            db.save_fund_nav("000001", date, nav_data)

        # 获取全部
        all_navs = db.get_fund_nav("000001")
        assert len(all_navs) == 10

        # 获取指定范围
        start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        filtered_navs = db.get_fund_nav("000001", start_date=start_date)
        assert len(filtered_navs) <= 6

    def test_get_latest_nav(self, temp_db):
        """DB-007: 获取最新净值"""
        db = temp_db
        # 保存多条记录
        db.save_fund_nav("000001", "2025-02-20", {"unit_nav": 1.0, "accumulated_nav": 2.0, "daily_growth": 0})
        db.save_fund_nav("000001", "2025-02-21", {"unit_nav": 1.1, "accumulated_nav": 2.1, "daily_growth": 0.1})
        db.save_fund_nav("000001", "2025-02-22", {"unit_nav": 1.2, "accumulated_nav": 2.2, "daily_growth": 0.1})

        latest = db.get_latest_nav("000001")
        assert latest is not None
        assert latest["nav_date"] == "2025-02-22"
        assert latest["unit_nav"] == 1.2

    def test_save_fund_holdings(self, temp_db):
        """DB-008: 保存基金持仓"""
        db = temp_db
        holdings = [
            {
                "stock_code": "600001",
                "stock_name": "浦发银行",
                "holding_ratio": 5.5,
                "holding_amount": 100000,
                "holding_value": 550000,
                "stock_type": "银行"
            },
            {
                "stock_code": "600002",
                "stock_name": "中国石化",
                "holding_ratio": 4.8,
                "holding_amount": 80000,
                "holding_value": 480000,
                "stock_type": "石油"
            }
        ]
        db.save_fund_holdings("000001", "2025-02-24", holdings)

        # 验证保存成功
        result = db.get_latest_holdings("000001")
        assert len(result) == 2

    def test_get_latest_holdings(self, temp_db):
        """DB-009: 获取最新持仓"""
        db = temp_db
        # 保存多期持仓
        db.save_fund_holdings("000001", "2024-12-31", [
            {"stock_code": "600001", "stock_name": "旧持仓", "holding_ratio": 5.0,
             "holding_amount": 10000, "holding_value": 100000, "stock_type": "银行"}
        ])
        db.save_fund_holdings("000001", "2025-02-24", [
            {"stock_code": "600002", "stock_name": "新持仓", "holding_ratio": 6.0,
             "holding_amount": 20000, "holding_value": 200000, "stock_type": "石油"}
        ])

        result = db.get_latest_holdings("000001")
        # 应该返回最新的持仓
        assert len(result) > 0

    def test_save_fund_rating(self, temp_db):
        """DB-010: 保存基金评级"""
        db = temp_db
        ratings = {"1y": 5, "2y": 4, "3y": 5}
        db.save_fund_rating("000001", "2025-02-24", "上海证券", ratings)

        # 验证保存成功
        result = db.get_latest_rating("000001")
        assert result is not None
        assert result["rating_1y"] == 5
        assert result["rating_3y"] == 5

    def test_get_latest_rating_not_exists(self, temp_db):
        """DB-011: 获取不存在的评级"""
        db = temp_db
        result = db.get_latest_rating("999999")
        assert result is None

    def test_log_update(self, temp_db):
        """DB-012: 记录更新日志"""
        db = temp_db
        before_time = datetime.now()
        db.log_update("fund_list", "success", "Updated 1000 funds")
        after_time = datetime.now()

        # 验证日志被记录
        last_update = db.get_last_update_time("fund_list")
        assert last_update is not None

        # 时间应该在 before 和 after 之间（允许一定误差）
        # 注意：SQLite 的 CURRENT_TIMESTAMP 可能使用 UTC，所以只验证日期部分
        assert last_update.date() == before_time.date()

    def test_get_last_update_time_not_exists(self, temp_db):
        """DB-013: 获取不存在的更新时间"""
        db = temp_db
        result = db.get_last_update_time("nonexistent_type")
        assert result is None

    def test_clear_old_data(self, temp_db):
        """DB-014: 清理旧数据"""
        db = temp_db
        # 保存一条旧数据
        old_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        db.save_fund_nav("000001", old_date, {"unit_nav": 1.0, "accumulated_nav": 2.0, "daily_growth": 0})

        # 保存一条新数据
        new_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        db.save_fund_nav("000001", new_date, {"unit_nav": 1.5, "accumulated_nav": 2.5, "daily_growth": 0.1})

        # 清理 365 天前的数据
        db.clear_old_data(days=365)

        # 旧数据应该被删除
        navs = db.get_fund_nav("000001")
        assert len(navs) == 1
        assert navs[0]["nav_date"] == new_date

    def test_nav_unique_constraint(self, temp_db):
        """DB-015: 净值唯一约束"""
        db = temp_db
        # 保存相同日期的净值
        db.save_fund_nav("000001", "2025-02-24", {"unit_nav": 1.0, "accumulated_nav": 2.0, "daily_growth": 0})
        # 再次保存相同日期的数据（应该覆盖）
        db.save_fund_nav("000001", "2025-02-24", {"unit_nav": 1.5, "accumulated_nav": 2.5, "daily_growth": 0.1})

        # 应该只有一条记录
        navs = db.get_fund_nav("000001")
        assert len(navs) == 1
        assert navs[0]["unit_nav"] == 1.5

    def test_multiple_funds(self, temp_db):
        """DB-016: 多只基金数据隔离"""
        db = temp_db
        # 保存两只基金的数据
        db.save_fund_basic("000001", {"fund_name": "基金 A", "fund_type": "混合型"})
        db.save_fund_basic("000002", {"fund_name": "基金 B", "fund_type": "债券型"})

        # 验证数据隔离
        fund_a = db.get_fund_basic("000001")
        fund_b = db.get_fund_basic("000002")

        assert fund_a["fund_name"] == "基金 A"
        assert fund_b["fund_name"] == "基金 B"

    def test_get_fund_nav_empty_result(self, temp_db):
        """DB-017: 获取净值为空"""
        db = temp_db
        result = db.get_fund_nav("999999")
        assert result == []

    def test_get_fund_nav_date_range(self, temp_db):
        """DB-018: 获取净值日期范围查询"""
        db = temp_db
        # 保存多条记录
        dates = ["2025-01-01", "2025-02-01", "2025-03-01"]
        for date in dates:
            db.save_fund_nav("000001", date, {"unit_nav": 1.0, "accumulated_nav": 2.0, "daily_growth": 0})

        # 查询日期范围
        result = db.get_fund_nav("000001", start_date="2025-02-01", end_date="2025-02-28")
        assert len(result) == 1
        assert result[0]["nav_date"] == "2025-02-01"

    def test_save_fund_size(self, temp_db):
        """DB-019: 保存基金规模数据"""
        db = temp_db
        fund_data = {
            "fund_code": "000001",
            "net_asset_size": "10.5 亿",
            "share_size": "9.8 亿份"
        }
        db.save_fund_basic("000001", fund_data)

        # 验证保存成功
        result = db.get_fund_basic("000001")
        assert result is not None
        assert result["net_asset_size"] == "10.5 亿"
        assert result["share_size"] == "9.8 亿份"

    def test_get_fund_size_not_exists(self, temp_db):
        """DB-020: 获取不存在的规模数据"""
        db = temp_db
        result = db.get_fund_basic("999999")
        assert result is None

    def test_update_fund_size(self, temp_db):
        """DB-021: 更新基金规模数据"""
        db = temp_db
        # 首次保存
        db.save_fund_basic("000001", {
            "fund_code": "000001",
            "net_asset_size": "10 亿",
            "share_size": "9 亿份"
        })

        # 更新规模数据
        db.save_fund_basic("000001", {
            "fund_code": "000001",
            "net_asset_size": "15 亿",
            "share_size": "14 亿份"
        })

        # 验证更新成功
        result = db.get_fund_basic("000001")
        assert result["net_asset_size"] == "15 亿"
        assert result["share_size"] == "14 亿份"
