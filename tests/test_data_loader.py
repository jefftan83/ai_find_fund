"""
data_loader.py CLI 工具测试
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from io import StringIO
import sys

from scripts.data_loader import (
    load_fund_basic,
    load_fund_ratings,
    load_fund_holdings,
    load_daily_nav,
    load_single_fund_history,
    load_top_n_history,
    load_history_by_type,
    load_fund_size_batch,
    load_size_by_type,
    load_screened_funds_size,
    get_fund_codes_from_db,
    check_existing_nav,
    check_existing_size,
)


class TestDataLoaderFunctions:
    """数据加载函数测试"""

    @pytest.mark.asyncio
    async def test_load_fund_basic(self):
        """CL-001: 加载基金基本信息"""
        with patch('scripts.data_loader.akshare_client') as mock_akshare:
            mock_akshare.get_fund_list = AsyncMock(return_value=[
                {"fund_code": "000001", "fund_name": "华夏成长", "fund_type": "混合型"}
            ])

            with patch('scripts.data_loader.cache_db') as mock_cache:
                result = await load_fund_basic(limit=1)

                assert result == 1
                mock_cache.save_fund_basic.assert_called()
                mock_cache.log_update.assert_called()

    @pytest.mark.asyncio
    async def test_load_fund_basic_error(self):
        """CL-002: 加载基金基本信息失败"""
        with patch('scripts.data_loader.akshare_client') as mock_akshare:
            mock_akshare.get_fund_list = AsyncMock(side_effect=Exception("API Error"))

            with patch('scripts.data_loader.cache_db') as mock_cache:
                result = await load_fund_basic()

                assert result == 0
                mock_cache.log_update.assert_called_with("fund_basic", "error", "API Error")

    @pytest.mark.asyncio
    async def test_load_fund_ratings(self):
        """CL-003: 加载基金评级"""
        with patch('scripts.data_loader.akshare_client') as mock_akshare:
            mock_akshare.get_fund_rating = AsyncMock(return_value=[
                {"fund_code": "000001", "rating_1y": 5, "rating_2y": 4, "rating_3y": 5, "rating_agency": "上海证券"}
            ])

            with patch('scripts.data_loader.cache_db') as mock_cache:
                result = await load_fund_ratings()

                assert result == 1
                mock_cache.save_fund_rating.assert_called()

    @pytest.mark.asyncio
    async def test_load_fund_holdings(self):
        """CL-004: 加载基金持仓"""
        with patch('scripts.data_loader.get_fund_codes_from_db') as mock_get:
            mock_get.return_value = ["000001"]

            with patch('scripts.data_loader.akshare_client') as mock_akshare:
                mock_akshare.get_fund_holdings = AsyncMock(return_value=[
                    {"stock_code": "600001", "stock_name": "浦发银行", "holding_ratio": 5.5}
                ])

                with patch('scripts.data_loader.cache_db') as mock_cache:
                    result = await load_fund_holdings(limit=1)

                    assert result == 1
                    mock_cache.save_fund_holdings.assert_called()

    @pytest.mark.asyncio
    async def test_load_daily_nav(self):
        """CL-005: 加载当日净值"""
        with patch('scripts.data_loader.akshare_client') as mock_akshare:
            mock_akshare.get_daily_nav = AsyncMock(return_value=[
                {"fund_code": "000001", "nav_date": "2026-02-25", "unit_nav": 1.234}
            ])

            with patch('scripts.data_loader.cache_db') as mock_cache:
                # 模拟数据库不存在该记录
                mock_cursor = MagicMock()
                mock_cursor.fetchone.return_value = None
                mock_conn = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_cache._get_connection.return_value = mock_conn

                result = await load_daily_nav()

                assert result >= 0
                mock_cache.save_fund_nav.assert_called()

    @pytest.mark.asyncio
    async def test_load_single_fund_history(self):
        """CL-006: 加载单只基金历史净值"""
        with patch('scripts.data_loader.akshare_client') as mock_akshare:
            mock_akshare.get_fund_history = AsyncMock(return_value=[
                {"nav_date": "2026-02-25", "unit_nav": 1.234},
                {"nav_date": "2026-02-24", "unit_nav": 1.220},
            ])

            with patch('scripts.data_loader.cache_db') as mock_cache:
                result = await load_single_fund_history("000001")

                assert result == 2

    @pytest.mark.asyncio
    async def test_load_single_fund_history_empty(self):
        """CL-007: 加载单只基金历史净值返回空"""
        with patch('scripts.data_loader.akshare_client') as mock_akshare:
            mock_akshare.get_fund_history = AsyncMock(return_value=[])

            with patch('scripts.data_loader.cache_db') as mock_cache:
                result = await load_single_fund_history("000001")

                assert result == 0

    @pytest.mark.asyncio
    async def test_load_top_n_history(self):
        """CL-008: 加载前 N 只基金历史净值"""
        with patch('scripts.data_loader.get_fund_codes_from_db') as mock_get:
            mock_get.return_value = ["000001", "000002"]

            with patch('scripts.data_loader.load_fund_history_batch') as mock_batch:
                mock_batch = AsyncMock(return_value=2)
                await load_top_n_history(top_n=2)

                mock_get.assert_called_once_with(limit=2)

    @pytest.mark.asyncio
    async def test_load_history_by_type(self):
        """CL-009: 按基金类型加载历史净值"""
        with patch('scripts.data_loader.get_fund_codes_from_db') as mock_get:
            mock_get.return_value = ["000001"]

            with patch('scripts.data_loader.load_fund_history_batch') as mock_batch:
                mock_batch = AsyncMock()
                await load_history_by_type(fund_type="混合型", limit=1)

                mock_get.assert_called_once_with(limit=1, fund_type="混合型")

    @pytest.mark.asyncio
    async def test_load_fund_size_batch(self):
        """CL-010: 批量加载基金规模"""
        with patch('scripts.data_loader.check_existing_size') as mock_check:
            mock_check.return_value = None  # 没有现有数据

            with patch('scripts.data_loader.akshare_client') as mock_akshare:
                mock_akshare.get_fund_size = AsyncMock(return_value={
                    "net_asset_size": "10.5 亿",
                    "share_size": "9.8 亿份"
                })

                with patch('scripts.data_loader.cache_db') as mock_cache:
                    result = await load_fund_size_batch(["000001"], "test")

                    assert result == 1
                    mock_cache.save_fund_basic.assert_called()

    @pytest.mark.asyncio
    async def test_load_fund_size_batch_skip_existing(self):
        """CL-011: 批量加载基金规模（跳过已有数据）"""
        with patch('scripts.data_loader.check_existing_size') as mock_check:
            mock_check.return_value = {"net_asset_size": "10 亿"}  # 已有数据

            with patch('scripts.data_loader.akshare_client') as mock_akshare:
                # 不应该调用 API
                result = await load_fund_size_batch(["000001"], "test")

                assert result == 0
                mock_akshare.get_fund_size.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_size_by_type(self):
        """CL-012: 按基金类型加载规模"""
        with patch('scripts.data_loader.get_fund_codes_from_db') as mock_get:
            mock_get.return_value = ["000001"]

            with patch('scripts.data_loader.load_fund_size_batch') as mock_batch:
                mock_batch = AsyncMock()
                await load_size_by_type(fund_type="混合型", limit=1)

                mock_get.assert_called_once_with(limit=1, fund_type="混合型")

    @pytest.mark.asyncio
    async def test_load_screened_funds_size(self):
        """CL-013: 加载推荐基金池规模数据"""
        # Mock get_fund_codes_from_db to return a small list for each call
        with patch('scripts.data_loader.get_fund_codes_from_db') as mock_get:
            mock_get.return_value = ["000001"]

            with patch('scripts.data_loader.load_fund_size_batch') as mock_batch:
                mock_batch = AsyncMock(return_value=1)
                # Replace the actual function with our mock
                import scripts.data_loader as dl_module
                original_func = dl_module.load_fund_size_batch
                dl_module.load_fund_size_batch = mock_batch

                try:
                    await load_screened_funds_size()
                    # Should be called 4 times (4 risk types)
                    assert mock_batch.call_count == 4
                finally:
                    # Restore original function
                    dl_module.load_fund_size_batch = original_func


class TestHelperFunctions:
    """辅助函数测试"""

    def test_get_fund_codes_from_db(self):
        """CL-014: 从数据库获取基金代码"""
        with patch('scripts.data_loader.cache_db') as mock_cache:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                MagicMock(__getitem__=lambda self, key: "000001"),
                MagicMock(__getitem__=lambda self, key: "000002"),
            ]
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cache._get_connection.return_value = mock_conn

            result = get_fund_codes_from_db(limit=2)

            assert len(result) == 2

    def test_get_fund_codes_from_db_with_type(self):
        """CL-015: 按类型从数据库获取基金代码"""
        with patch('scripts.data_loader.cache_db') as mock_cache:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                MagicMock(__getitem__=lambda self, key: "000001"),
            ]
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cache._get_connection.return_value = mock_conn

            result = get_fund_codes_from_db(limit=1, fund_type="混合型")

            assert len(result) == 1

    def test_check_existing_nav(self):
        """CL-016: 检查已有净值记录数"""
        with patch('scripts.data_loader.cache_db') as mock_cache:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = [100]
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cache._get_connection.return_value = mock_conn

            result = check_existing_nav("000001")

            assert result == 100

    def test_check_existing_size_has_data(self):
        """CL-017: 检查已有规模数据（7 天内）"""
        from datetime import datetime, timedelta

        recent_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')

        with patch('scripts.data_loader.cache_db') as mock_cache:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {
                'net_asset_size': '10 亿',
                'share_size': '9 亿份',
                'updated_at': recent_date
            }
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cache._get_connection.return_value = mock_conn

            result = check_existing_size("000001")

            assert result is not None
            assert result['net_asset_size'] == '10 亿'

    def test_check_existing_size_no_data(self):
        """CL-018: 检查已有规模数据（无数据）"""
        with patch('scripts.data_loader.cache_db') as mock_cache:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cache._get_connection.return_value = mock_conn

            result = check_existing_size("000001")

            assert result is None

    def test_check_existing_size_expired(self):
        """CL-019: 检查已有规模数据（已过期）"""
        from datetime import datetime, timedelta

        old_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

        with patch('scripts.data_loader.cache_db') as mock_cache:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {
                'net_asset_size': '10 亿',
                'share_size': '9 亿份',
                'updated_at': old_date
            }
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cache._get_connection.return_value = mock_conn

            result = check_existing_size("000001")

            # 超过 7 天，应该返回 None
            assert result is None
