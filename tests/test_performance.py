"""
性能测试
覆盖测试计划中的模块 7：性能测试
"""

import pytest
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from src.cache.db import CacheDB
from src.services.fund_data import FundDataService
from src.agents.fund_expert import FundExpertAgent


# ========== 缓存性能测试 ==========

class TestCachePerformance:
    """缓存性能测试"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    @pytest.mark.asyncio
    async def test_batch_write_1000_records(self, temp_db):
        """PERF-001: 缓存批量写入 1000 条记录 < 10s"""
        start_time = time.time()

        for i in range(1000):
            fund_code = f"{i:06d}"
            temp_db.save_fund_basic(fund_code, {
                "fund_code": fund_code,
                "fund_name": f"基金{i}",
                "fund_type": "混合型",
                "net_asset_size": f"{10 + i * 0.1:.1f}亿",
                "share_size": f"{9 + i * 0.1:.1f}亿份"
            })

        elapsed = time.time() - start_time

        # 性能断言：1000 次写入应在 10 秒内完成
        assert elapsed < 10.0, f"批量写入超时：{elapsed:.2f}s"
        print(f"\nPERF-001: 1000 次写入耗时 {elapsed:.2f}s (标准：< 10s)")

    @pytest.mark.asyncio
    async def test_batch_read_1000_records(self, temp_db):
        """PERF-002: 缓存批量读取 1000 次 < 10s"""
        # 先写入 1000 条数据
        for i in range(1000):
            fund_code = f"{i:06d}"
            temp_db.save_fund_basic(fund_code, {
                "fund_code": fund_code,
                "fund_name": f"基金{i}"
            })

        start_time = time.time()

        # 批量读取
        for i in range(1000):
            fund_code = f"{i:06d}"
            temp_db.get_fund_basic(fund_code)

        elapsed = time.time() - start_time

        # 性能断言：1000 次读取应在 10 秒内完成
        assert elapsed < 10.0, f"批量读取超时：{elapsed:.2f}s"
        print(f"\nPERF-002: 1000 次读取耗时 {elapsed:.2f}s (标准：< 10s)")

    @pytest.mark.asyncio
    async def test_nav_batch_write(self, temp_db):
        """PERF-003: 净值数据批量写入性能"""
        start_time = time.time()

        # 写入 100 只基金，每只 10 条净值记录
        for i in range(100):
            fund_code = f"{i:06d}"
            for j in range(10):
                date = (datetime.now() - timedelta(days=j)).strftime("%Y-%m-%d")
                temp_db.save_fund_nav(fund_code, date, {
                    "unit_nav": 1.0 + j * 0.01,
                    "accumulated_nav": 2.0 + j * 0.01,
                    "daily_growth": 0.01
                })

        elapsed = time.time() - start_time

        # 1000 次净值写入应在 15 秒内完成
        assert elapsed < 15.0, f"净值批量写入超时：{elapsed:.2f}s"
        print(f"\nPERF-003: 1000 次净值写入耗时 {elapsed:.2f}s (标准：< 15s)")

    @pytest.mark.asyncio
    async def test_nav_date_range_query(self, temp_db):
        """PERF-004: 净值日期范围查询性能"""
        # 准备数据：100 只基金，每只 100 条记录
        for i in range(100):
            fund_code = f"{i:06d}"
            for j in range(100):
                date = (datetime.now() - timedelta(days=j)).strftime("%Y-%m-%d")
                temp_db.save_fund_nav(fund_code, date, {
                    "unit_nav": 1.0 + j * 0.001,
                    "accumulated_nav": 2.0 + j * 0.001,
                    "daily_growth": 0.001
                })

        start_time = time.time()

        # 查询 50 只基金的历史净值（30 天范围）
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        for i in range(50):
            fund_code = f"{i:06d}"
            temp_db.get_fund_nav(fund_code, start_date=start_date)

        elapsed = time.time() - start_time

        # 50 次范围查询应在 5 秒内完成
        assert elapsed < 5.0, f"范围查询超时：{elapsed:.2f}s"
        print(f"\nPERF-004: 50 次范围查询耗时 {elapsed:.2f}s (标准：< 5s)")


# ========== 数据服务性能测试 ==========

class TestFundData_ServicePerformance:
    """基金数据服务性能测试"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    @pytest.mark.asyncio
    async def test_fund_screening_response_time(self, temp_db):
        """PERF-005: 基金筛选响应 < 10s (含覆盖率)"""
        with patch('src.services.fund_data.cache_db', temp_db):
            service = FundDataService()

            with patch('src.services.akshare_client.akshare_client') as mock_akshare:
                # Mock 返回 100 只基金
                mock_akshare.get_fund_ranking = AsyncMock(return_value=[
                    {"fund_code": f"{i:06d}", "fund_name": f"基金{i}", "return_1y": 10 + i * 0.1}
                    for i in range(100)
                ])

                with patch.object(service, 'get_fund_rating') as mock_rating:
                    mock_rating = AsyncMock(return_value={"rating_1y": 5})

                    start_time = time.time()
                    result = await service.screen_funds(min_return_1y=10)
                    elapsed = time.time() - start_time

                    # 筛选响应应在 10 秒内完成 (含覆盖率测试)
                    assert elapsed < 10.0, f"基金筛选超时：{elapsed:.2f}s"
                    print(f"\nPERF-005: 基金筛选耗时 {elapsed:.2f}s (标准：< 10s)")

    @pytest.mark.asyncio
    async def test_fund_analysis_response_time(self, temp_db):
        """PERF-006: 基金综合分析响应 < 5s (不含 LLM)"""
        with patch('src.services.fund_data.cache_db', temp_db):
            service = FundDataService()

            # Mock 所有数据源
            with patch.object(service, 'get_fund_nav') as mock_nav:
                mock_nav.return_value = {"unit_nav": 1.234, "nav_date": "2026-02-25"}

                with patch.object(service, 'get_fund_basic_info') as mock_basic:
                    mock_basic.return_value = {"fund_name": "华夏成长混合"}

                    with patch.object(service, 'get_fund_holdings') as mock_holdings:
                        mock_holdings.return_value = []

                        with patch.object(service, 'get_fund_rating') as mock_rating:
                            mock_rating.return_value = {"rating_1y": 5}

                            with patch.object(service, 'get_fund_history') as mock_history:
                                mock_history.return_value = [
                                    {"nav_date": "2026-02-25", "unit_nav": 1.234},
                                    {"nav_date": "2026-02-24", "unit_nav": 1.220},
                                ]

                                start_time = time.time()
                                result = await service.get_fund_analysis("000001")
                                elapsed = time.time() - start_time

                                # 分析响应应在 5 秒内完成
                                assert elapsed < 5.0, f"基金分析超时：{elapsed:.2f}s"
                                print(f"\nPERF-006: 基金分析耗时 {elapsed:.2f}s (标准：< 5s)")

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self, temp_db):
        """PERF-007: 缓存命中时性能"""
        # 先在缓存中保存数据
        for i in range(100):
            fund_code = f"{i:06d}"
            temp_db.save_fund_basic(fund_code, {
                "fund_code": fund_code,
                "fund_name": f"基金{i}",
                "net_asset_size": "10 亿"
            })
            temp_db.log_update("fund_list", "success", "Test")

        with patch('src.services.fund_data.cache_db', temp_db):
            service = FundDataService()

            start_time = time.time()

            # 缓存命中，不应调用 API
            with patch('src.services.akshare_client.akshare_client') as mock_akshare:
                result = await service.get_fund_list(use_cache=True)
                elapsed = time.time() - start_time

                # 缓存命中应非常快速
                assert elapsed < 1.0, f"缓存读取超时：{elapsed:.2f}s"
                # 不应调用 API
                mock_akshare.get_fund_list.assert_not_called()
                print(f"\nPERF-007: 缓存命中耗时 {elapsed:.2f}s (标准：< 1s)")


# ========== Agent 性能测试 ==========

class TestAgentPerformance:
    """Agent 性能测试"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    @pytest.mark.asyncio
    async def test_preload_size_data_50_funds(self, temp_db):
        """PERF-008: 规模数据预加载 50 只基金 < 2min"""
        with patch('src.agents.fund_expert.cache_db', temp_db):
            agent = FundExpertAgent()
            agent.risk_level = "稳健型"
            # 准备 50 只基金
            agent.screened_funds = [
                {"fund_code": f"{i:06d}", "fund_name": f"基金{i}"}
                for i in range(50)
            ]

            with patch('src.services.akshare_client.akshare_client') as mock_akshare:
                mock_akshare.get_fund_size = AsyncMock(return_value={
                    "net_asset_size": "10.5 亿",
                    "share_size": "9.8 亿份"
                })

                start_time = time.time()
                await agent._preload_size_data()
                elapsed = time.time() - start_time

                # 50 只基金预加载应在 2 分钟内完成
                assert elapsed < 120.0, f"规模预加载超时：{elapsed:.2f}s"
                print(f"\nPERF-008: 50 只基金规模预加载耗时 {elapsed:.2f}s (标准：< 120s)")

    @pytest.mark.asyncio
    async def test_prepare_fund_summary_performance(self, temp_db):
        """PERF-009: 准备基金摘要性能"""
        # 准备缓存数据
        for i in range(30):
            fund_code = f"{i:06d}"
            temp_db.save_fund_basic(fund_code, {
                "fund_code": fund_code,
                "net_asset_size": f"{10 + i:.1f}亿",
                "share_size": f"{9 + i:.1f}亿份"
            })

        with patch('src.agents.fund_expert.cache_db', temp_db):
            agent = FundExpertAgent()
            agent.screened_funds = [
                {
                    "fund_code": f"{i:06d}",
                    "fund_name": f"基金{i}",
                    "return_1y": 10 + i * 0.5
                }
                for i in range(30)
            ]

            start_time = time.time()
            summary = agent._prepare_fund_summary()
            elapsed = time.time() - start_time

            # 准备摘要应在 2 秒内完成
            assert elapsed < 2.0, f"准备摘要超时：{elapsed:.2f}s"
            assert isinstance(summary, str)
            print(f"\nPERF-009: 准备基金摘要耗时 {elapsed:.2f}s (标准：< 2s)")


# ========== 并发性能测试 ==========

class TestConcurrencyPerformance:
    """并发性能测试"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    @pytest.mark.asyncio
    async def test_concurrent_nav_queries(self, temp_db):
        """PERF-010: 并发净值查询性能"""
        # 准备数据
        for i in range(50):
            fund_code = f"{i:06d}"
            for j in range(30):
                date = (datetime.now() - timedelta(days=j)).strftime("%Y-%m-%d")
                temp_db.save_fund_nav(fund_code, date, {
                    "unit_nav": 1.0 + j * 0.01,
                    "accumulated_nav": 2.0 + j * 0.01,
                    "daily_growth": 0.01
                })

        async def query_nav(fund_code):
            return temp_db.get_fund_nav(fund_code)

        start_time = time.time()

        # 并发查询 50 只基金的净值
        tasks = [query_nav(f"{i:06d}") for i in range(50)]
        await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        # 50 次并发查询应在 5 秒内完成
        assert elapsed < 5.0, f"并发查询超时：{elapsed:.2f}s"
        print(f"\nPERF-010: 50 次并发净值查询耗时 {elapsed:.2f}s (标准：< 5s)")

    @pytest.mark.asyncio
    async def test_concurrent_basic_info_writes(self, temp_db):
        """PERF-011: 并发基本信息写入性能"""
        async def save_basic(fund_code, i):
            temp_db.save_fund_basic(fund_code, {
                "fund_code": fund_code,
                "fund_name": f"基金{i}",
                "net_asset_size": f"{10 + i:.1f}亿"
            })

        start_time = time.time()

        # 并发写入 100 只基金
        tasks = [save_basic(f"{i:06d}", i) for i in range(100)]
        await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        # 100 次并发写入应在 10 秒内完成
        assert elapsed < 10.0, f"并发写入超时：{elapsed:.2f}s"
        print(f"\nPERF-011: 100 次并发写入耗时 {elapsed:.2f}s (标准：< 10s)")


# ========== 大数据量测试 ==========

class TestLargeDatasetPerformance:
    """大数据量性能测试"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    @pytest.mark.asyncio
    async def test_1000_funds_basic_operations(self, temp_db):
        """PERF-012: 1000 只基金基本操作性能"""
        # 保存 1000 只基金
        for i in range(1000):
            fund_code = f"{i:06d}"
            temp_db.save_fund_basic(fund_code, {
                "fund_code": fund_code,
                "fund_name": f"基金{i}",
                "fund_type": "混合型",
                "net_asset_size": f"{10 + i * 0.1:.1f}亿",
                "share_size": f"{9 + i * 0.1:.1f}亿份"
            })

        start_time = time.time()

        # 查询所有基金
        import sqlite3
        conn = temp_db._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT fund_code, fund_name, net_asset_size FROM fund_basic")
        results = cursor.fetchall()
        conn.close()

        elapsed = time.time() - start_time

        assert len(results) == 1000
        # 查询应在 2 秒内完成
        assert elapsed < 2.0, f"大数据量查询超时：{elapsed:.2f}s"
        print(f"\nPERF-012: 1000 只基金查询耗时 {elapsed:.2f}s (标准：< 2s)")

    @pytest.mark.asyncio
    async def test_multi_fund_isolation(self, temp_db):
        """PERF-013: 多基金数据隔离性能"""
        # 保存 100 只基金的数据
        for i in range(100):
            fund_code = f"{i:06d}"
            temp_db.save_fund_basic(fund_code, {
                "fund_code": fund_code,
                "fund_name": f"基金{i}"
            })
            for j in range(10):
                date = (datetime.now() - timedelta(days=j)).strftime("%Y-%m-%d")
                temp_db.save_fund_nav(fund_code, date, {
                    "unit_nav": 1.0 + i * 0.01,
                    "accumulated_nav": 2.0 + i * 0.01,
                    "daily_growth": 0.01
                })

        start_time = time.time()

        # 分别查询每只基金的数据（验证隔离）
        for i in range(100):
            fund_code = f"{i:06d}"
            basic = temp_db.get_fund_basic(fund_code)
            navs = temp_db.get_fund_nav(fund_code)

            assert basic["fund_code"] == fund_code
            assert len(navs) == 10

        elapsed = time.time() - start_time

        # 100 次隔离查询应在 5 秒内完成
        assert elapsed < 5.0, f"隔离查询超时：{elapsed:.2f}s"
        print(f"\nPERF-013: 100 次隔离查询耗时 {elapsed:.2f}s (标准：< 5s)")


# ========== 缓存过期策略测试 ==========

class TestCacheExpiryPerformance:
    """缓存过期策略性能测试"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    @pytest.mark.asyncio
    async def test_cache_expiry_check_performance(self, temp_db):
        """PERF-014: 缓存过期检查性能"""
        # 保存 100 条更新日志
        for i in range(100):
            temp_db.log_update(f"data_type_{i}", "success", f"Test {i}")

        start_time = time.time()

        # 检查所有类型的最后更新时间
        for i in range(100):
            temp_db.get_last_update_time(f"data_type_{i}")

        elapsed = time.time() - start_time

        # 100 次过期检查应在 2 秒内完成
        assert elapsed < 2.0, f"过期检查超时：{elapsed:.2f}s"
        print(f"\nPERF-014: 100 次过期检查耗时 {elapsed:.2f}s (标准：< 2s)")

    @pytest.mark.asyncio
    async def test_clear_old_data_performance(self, temp_db):
        """PERF-015: 清理旧数据性能"""
        # 保存 365 天的数据
        for i in range(100):
            fund_code = f"{i:06d}"
            for j in range(365):
                date = (datetime.now() - timedelta(days=j)).strftime("%Y-%m-%d")
                temp_db.save_fund_nav(fund_code, date, {
                    "unit_nav": 1.0 + j * 0.001,
                    "accumulated_nav": 2.0 + j * 0.001,
                    "daily_growth": 0.001
                })

        start_time = time.time()

        # 清理 30 天前的数据
        temp_db.clear_old_data(days=30)

        elapsed = time.time() - start_time

        # 清理应在 10 秒内完成
        assert elapsed < 10.0, f"清理旧数据超时：{elapsed:.2f}s"
        print(f"\nPERF-015: 清理旧数据耗时 {elapsed:.2f}s (标准：< 10s)")


# 需要导入 asyncio
import asyncio
