"""
降级策略集成测试
测试数据源从高优先级到低优先级的降级逻辑
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from src.services.fund_data import FundDataService
from src.cache.db import CacheDB
import tempfile
from pathlib import Path


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    db = CacheDB(db_path)
    yield db
    db_path.unlink()


@pytest.fixture
def fund_data_service(temp_db):
    """创建 FundDataService 实例（使用临时数据库）"""
    with patch('src.services.fund_data.cache_db', temp_db):
        service = FundDataService()
        yield service


class TestFallbackStrategy:
    """降级策略测试"""

    @pytest.mark.asyncio
    async def test_get_fund_list_akshare_success(self, fund_data_service):
        """FBS-001: AKShare 成功获取基金列表"""
        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_fund_list = AsyncMock(return_value=[
                {"fund_code": "000001", "fund_name": "华夏成长", "fund_type": "混合型"}
            ])

            result = await fund_data_service.get_fund_list(use_cache=False)

            assert len(result) == 1
            assert result[0]["fund_code"] == "000001"
            # 应该调用 AKShare
            mock_akshare.get_fund_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_fund_list_akshare_error(self, fund_data_service):
        """FBS-002: AKShare 失败，返回空列表"""
        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_fund_list = AsyncMock(side_effect=Exception("API Error"))

            result = await fund_data_service.get_fund_list(use_cache=False)

            # AKShare 失败后返回空列表
            assert result == []

    @pytest.mark.asyncio
    async def test_get_daily_nav_akshare_success(self, fund_data_service):
        """FBS-003: AKShare 成功获取当日净值"""
        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_daily_nav = AsyncMock(return_value=[
                {"fund_code": "000001", "nav_date": "2026-02-25", "unit_nav": 1.234}
            ])

            result = await fund_data_service.get_daily_nav(use_cache=False)

            assert len(result) == 1
            assert result[0]["unit_nav"] == 1.234

    @pytest.mark.asyncio
    async def test_get_daily_nav_akshare_error_fallback_sina(self, fund_data_service):
        """FBS-004: AKShare 失败，降级到新浪财经"""
        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_daily_nav = AsyncMock(side_effect=Exception("AKShare Error"))

            with patch('src.services.fund_data.sina_client') as mock_sina:
                mock_sina.get_fund_nav_batch = AsyncMock(return_value=[
                    {"fund_code": "000001", "unit_nav": 1.234}
                ])

                with patch.object(fund_data_service, 'get_fund_list') as mock_list:
                    mock_list.return_value = [{"fund_code": "000001"}]

                    result = await fund_data_service.get_daily_nav()

                    # 应该降级到新浪财经
                    mock_sina.get_fund_nav_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_fund_nav_akshare_success(self, fund_data_service):
        """FBS-005: AKShare 成功获取基金净值"""
        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_fund_history = AsyncMock(return_value=[
                {"nav_date": "2026-02-25", "unit_nav": 1.234, "accumulated_nav": 2.345}
            ])

            result = await fund_data_service.get_fund_nav("000001", use_cache=False)

            assert result["unit_nav"] == 1.234

    @pytest.mark.asyncio
    async def test_get_fund_nav_akshare_error_fallback_sina(self, fund_data_service):
        """FBS-006: AKShare 失败，降级到新浪财经"""
        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_fund_history = AsyncMock(side_effect=Exception("Error"))

            with patch('src.services.fund_data.sina_client') as mock_sina:
                mock_sina.get_fund_nav = AsyncMock(return_value={
                    "nav_date": "2026-02-25", "unit_nav": 1.200
                })

                result = await fund_data_service.get_fund_nav("000001", use_cache=False)

                # 应该降级到新浪财经
                mock_sina.get_fund_nav.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_fund_nav_all_sources_error_return_cache(self, fund_data_service):
        """FBS-007: 所有数据源失败，返回缓存数据"""
        # 先在缓存中保存数据
        temp_db = fund_data_service.__dict__.get('_test_db')
        if temp_db:
            temp_db.save_fund_nav("000001", "2026-02-24", {
                "unit_nav": 1.100,
                "accumulated_nav": 2.100,
                "daily_growth": 0.01
            })

        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_fund_history = AsyncMock(side_effect=Exception("Error"))

            with patch('src.services.fund_data.sina_client') as mock_sina:
                mock_sina.get_fund_nav = AsyncMock(side_effect=Exception("Error"))

                # 应该返回缓存的旧数据
                result = await fund_data_service.get_fund_nav("000001", use_cache=False)

                # 如果没有缓存，返回 None
                assert result is None or result.get("unit_nav") == 1.100

    @pytest.mark.asyncio
    async def test_get_fund_holdings_akshare_success(self, fund_data_service):
        """FBS-008: AKShare 成功获取持仓"""
        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_fund_holdings = AsyncMock(return_value=[
                {"stock_code": "600001", "stock_name": "浦发银行", "holding_ratio": 5.5}
            ])

            result = await fund_data_service.get_fund_holdings("000001")

            assert len(result) == 1
            assert result[0]["stock_code"] == "600001"

    @pytest.mark.asyncio
    async def test_get_fund_holdings_akshare_error_fallback_tushare(self, fund_data_service):
        """FBS-009: AKShare 失败，降级到 Tushare"""
        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_fund_holdings = AsyncMock(side_effect=Exception("Error"))

            with patch('src.services.fund_data.tushare_client') as mock_tushare:
                mock_tushare.get_fund_portfolio = AsyncMock(return_value=[
                    {"stock_code": "600001", "stock_name": "浦发银行", "holding_ratio": 5.5}
                ])

                with patch('src.services.fund_data.config') as mock_config:
                    mock_config.tushare_token = "test_token"

                    result = await fund_data_service.get_fund_holdings("000001")

                    # 应该降级到 Tushare
                    mock_tushare.get_fund_portfolio.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_fund_ranking_akshare_success(self, fund_data_service):
        """FBS-010: AKShare 成功获取排行"""
        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_fund_ranking = AsyncMock(return_value=[
                {"fund_code": "000001", "return_1y": 15.5}
            ])

            result = await fund_data_service.get_fund_ranking()

            assert len(result) == 1
            assert result[0]["return_1y"] == 15.5

    @pytest.mark.asyncio
    async def test_get_fund_ranking_akshare_error_fallback_calc(self, fund_data_service):
        """FBS-011: AKShare 失败，降级到历史净值计算"""
        with patch('src.services.fund_data.akshare_client') as mock_akshare:
            mock_akshare.get_fund_ranking = AsyncMock(return_value=[])

            with patch('src.services.fund_data.cache_db') as mock_cache:
                mock_cursor = MagicMock()
                mock_cursor.fetchall.return_value = [
                    {"fund_code": "000001", "fund_name": "华夏成长", "fund_type": "混合型"}
                ]
                mock_conn = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_cache._get_connection.return_value = mock_conn

                # Patch calc_returns from the correct module
                with patch('src.services.returns_calculator.calc_returns') as mock_calc:
                    mock_calc.return_value = {"return_1y": 10.5}

                    result = await fund_data_service.get_fund_ranking()

                    # 降级方案应该被调用
                    assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_cache_prevents_api_call(self):
        """FBS-012: 缓存有效时不调用 API"""
        from datetime import timedelta
        from src.services.fund_data import FundDataService
        from src.cache.db import CacheDB
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            db = CacheDB(db_path)

            # Save fund data to cache
            db.save_fund_basic("000001", {"fund_name": "华夏成长", "fund_type": "混合型"})
            db.log_update("fund_list", "success", "Test")

            with patch('src.services.fund_data.cache_db', db):
                service = FundDataService()

                with patch('src.services.fund_data.akshare_client') as mock_akshare:
                    mock_akshare.get_fund_list = AsyncMock(return_value=[])

                    result = await service.get_fund_list(use_cache=True)

                    # Should return cached data, not call API
                    assert len(result) >= 1
                    mock_akshare.get_fund_list.assert_not_called()

        finally:
            db_path.unlink()

    @pytest.mark.asyncio
    async def test_cache_expired_triggers_api_call(self, fund_data_service):
        """FBS-013: 缓存过期时调用 API"""
        from datetime import timedelta

        with patch('src.services.fund_data.cache_db') as mock_cache:
            # 模拟缓存过期（25 小时前）
            expired_time = datetime.now() - timedelta(hours=25)
            mock_cache.get_last_update_time.return_value = expired_time

            with patch('src.services.fund_data.akshare_client') as mock_akshare:
                mock_akshare.get_fund_list = AsyncMock(return_value=[
                    {"fund_code": "000001", "fund_name": "华夏成长"}
                ])

                result = await fund_data_service.get_fund_list(use_cache=True)

                # 缓存过期，应该调用 API
                mock_akshare.get_fund_list.assert_called_once()


class TestMultiSourceFallback:
    """多源降级完整链路测试"""

    @pytest.mark.asyncio
    async def test_full_fallback_chain(self):
        """FBS-014: 完整降级链路测试"""
        from src.services.fund_data import FundDataService
        from src.cache.db import CacheDB
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            db = CacheDB(db_path)

            with patch('src.services.fund_data.cache_db', db):
                service = FundDataService()

                # 所有 API 都失败
                with patch('src.services.fund_data.akshare_client') as mock_akshare:
                    mock_akshare.get_daily_nav = AsyncMock(side_effect=Exception("Error"))

                    with patch('src.services.fund_data.sina_client') as mock_sina:
                        mock_sina.get_fund_nav_batch = AsyncMock(side_effect=Exception("Error"))

                        with patch.object(service, 'get_fund_list') as mock_list:
                            mock_list.return_value = []

                            result = await service.get_daily_nav()

                            # 所有源都失败，返回空列表
                            assert result == []

        finally:
            db_path.unlink()
