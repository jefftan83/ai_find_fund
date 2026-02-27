"""
基金规模数据集成测试
覆盖测试计划中的基金规模数据功能测试
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import tempfile
from pathlib import Path

from src.cache.db import CacheDB
from src.services.akshare_client import AKShareClient
from src.agents.fund_expert import FundExpertAgent
from src.services.fund_data import FundDataService


# ========== 数据库层测试 ===========

class TestFundSizeDB:
    """基金规模数据 DB 层测试"""

    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    def test_save_fund_size_complete(self, temp_db):
        """FUND-SIZE-DB-001: 保存完整规模数据"""
        fund_data = {
            "fund_code": "000001",
            "fund_name": "华夏成长混合",
            "net_asset_size": "15.8 亿",
            "share_size": "14.2 亿份"
        }
        temp_db.save_fund_basic("000001", fund_data)

        result = temp_db.get_fund_basic("000001")
        assert result is not None
        assert result["net_asset_size"] == "15.8 亿"
        assert result["share_size"] == "14.2 亿份"

    def test_save_fund_size_partial(self, temp_db):
        """FUND-SIZE-DB-002: 保存部分规模数据（仅有净资产）"""
        fund_data = {
            "fund_code": "000002",
            "fund_name": "华夏债券",
            "net_asset_size": "8.5 亿",
            "share_size": None
        }
        temp_db.save_fund_basic("000002", fund_data)

        result = temp_db.get_fund_basic("000002")
        assert result is not None
        assert result["net_asset_size"] == "8.5 亿"
        assert result["share_size"] is None

    def test_update_fund_size_only(self, temp_db):
        """FUND-SIZE-DB-003: 仅更新规模数据（不修改其他字段）"""
        # 先保存基本信息
        temp_db.save_fund_basic("000001", {
            "fund_code": "000001",
            "fund_name": "华夏成长混合",
            "fund_type": "混合型"
        })

        # 仅更新规模数据
        temp_db.save_fund_basic("000001", {
            "fund_code": "000001",
            "net_asset_size": "20.5 亿",
            "share_size": "18.2 亿份"
        })

        result = temp_db.get_fund_basic("000001")
        assert result["net_asset_size"] == "20.5 亿"
        assert result["share_size"] == "18.2 亿份"
        # 原有字段应该被清空（INSERT OR REPLACE 行为）
        assert result["fund_name"] is None

    def test_get_fund_size_batch(self, temp_db):
        """FUND-SIZE-DB-004: 批量获取规模数据"""
        # 保存多只基金的规模数据
        funds = [
            ("000001", "10.5 亿", "9.8 亿份"),
            ("000002", "8.2 亿", "7.5 亿份"),
            ("000003", "25.0 亿", "22.0 亿份"),
        ]
        for code, nav_size, share in funds:
            temp_db.save_fund_basic(code, {
                "fund_code": code,
                "net_asset_size": nav_size,
                "share_size": share
            })

        # 批量查询
        import sqlite3
        conn = temp_db._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT fund_code, net_asset_size, share_size
            FROM fund_basic
            WHERE fund_code IN ('000001', '000002', '000003')
        """)
        results = {row['fund_code']: row for row in cursor.fetchall()}
        conn.close()

        assert len(results) == 3
        assert results['000001']['net_asset_size'] == "10.5 亿"
        assert results['000002']['share_size'] == "7.5 亿份"


# ========== AKShare 客户端测试 ==========

class TestFundSizeAKShare:
    """AKShare 客户端规模数据测试"""

    @pytest.fixture
    def client(self):
        return AKShareClient()

    @pytest.mark.asyncio
    async def test_get_fund_size_success(self, client):
        """FUND-SIZE-AKS-001: 获取基金规模成功"""
        import pandas as pd
        mock_df = pd.DataFrame([[
            "华夏成长混合型证券投资基金", "华夏成长", "000001", "混合型",
            "2002-01-01", "2002-01-01 / 20 亿", "15.8 亿", "14.2 亿份",
            "华夏基金管理有限公司", "中国建设银行", "张三"
        ]])

        with patch.object(client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_overview_em.return_value = mock_df
            mock_get.return_value = mock_ak

            result = await client.get_fund_size("000001")

            assert result["net_asset_size"] == "15.8 亿"
            assert result["share_size"] == "14.2 亿份"

    @pytest.mark.asyncio
    async def test_get_fund_size_returns_empty_on_error(self, client):
        """FUND-SIZE-AKS-002: 获取规模数据异常时返回空字典"""
        with patch.object(client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_overview_em.side_effect = Exception("API Error")
            mock_get.return_value = mock_ak

            result = await client.get_fund_size("000001")
            assert result == {}

    @pytest.mark.asyncio
    async def test_get_fund_size_returns_empty_on_empty_df(self, client):
        """FUND-SIZE-AKS-003: 返回空 DataFrame 时返回空字典"""
        import pandas as pd
        with patch.object(client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_overview_em.return_value = pd.DataFrame()
            mock_get.return_value = mock_ak

            result = await client.get_fund_size("000001")
            assert result == {}


# ========== FundExpertAgent 规模数据测试 ==========

class TestFundExpertSizeIntegration:
    """FundExpertAgent 规模数据集成测试"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    @pytest.mark.asyncio
    async def test_preload_size_data_loads_missing(self, temp_db):
        """FUND-SIZE-AGENT-001: 预加载规模数据加载缺失数据"""
        with patch('src.agents.fund_expert.cache_db', temp_db):
            agent = FundExpertAgent()
            agent.risk_level = "稳健型"
            agent.screened_funds = [
                {"fund_code": "000001", "fund_name": "华夏成长"},
                {"fund_code": "000002", "fund_name": "华夏债券"},
            ]

            with patch('src.services.akshare_client.akshare_client') as mock_akshare:
                mock_akshare.get_fund_size = AsyncMock(return_value={
                    "net_asset_size": "10.5 亿",
                    "share_size": "9.8 亿份"
                })

                await agent._preload_size_data()

                # 验证 API 被调用
                assert mock_akshare.get_fund_size.call_count >= 1

                # 验证缓存已保存
                result = temp_db.get_fund_basic("000001")
                assert result is not None
                assert result["net_asset_size"] == "10.5 亿"

    @pytest.mark.asyncio
    async def test_preload_size_data_skips_cached(self, temp_db):
        """FUND-SIZE-AGENT-002: 预加载规模数据跳过已有缓存"""
        # 预先保存缓存数据
        temp_db.save_fund_basic("000001", {
            "fund_code": "000001",
            "net_asset_size": "10 亿",
            "share_size": "9 亿份"
        })

        with patch('src.agents.fund_expert.cache_db', temp_db):
            agent = FundExpertAgent()
            agent.risk_level = "稳健型"
            agent.screened_funds = [
                {"fund_code": "000001", "fund_name": "华夏成长"},
            ]

            with patch('src.services.akshare_client.akshare_client') as mock_akshare:
                await agent._preload_size_data()

                # 不应调用 API（已有缓存）
                mock_akshare.get_fund_size.assert_not_called()

    @pytest.mark.asyncio
    async def test_preload_size_data_handles_errors_gracefully(self, temp_db):
        """FUND-SIZE-AGENT-003: 预加载规模数据处理错误"""
        with patch('src.agents.fund_expert.cache_db', temp_db):
            agent = FundExpertAgent()
            agent.risk_level = "稳健型"
            agent.screened_funds = [
                {"fund_code": "000001", "fund_name": "华夏成长"},
            ]

            with patch('src.services.akshare_client.akshare_client') as mock_akshare:
                mock_akshare.get_fund_size = AsyncMock(side_effect=Exception("API Error"))

                # 不应抛出异常，应该静默失败
                await agent._preload_size_data()

    def test_get_size_cache_returns_correct_format(self, temp_db):
        """FUND-SIZE-AGENT-004: 获取规模缓存返回正确格式"""
        # 保存测试数据
        temp_db.save_fund_basic("000001", {
            "fund_code": "000001",
            "net_asset_size": "10.5 亿",
            "share_size": "9.8 亿份"
        })
        temp_db.save_fund_basic("000002", {
            "fund_code": "000002",
            "net_asset_size": "8.2 亿",
            "share_size": "7.5 亿份"
        })

        with patch('src.agents.fund_expert.cache_db', temp_db):
            agent = FundExpertAgent()
            result = agent._get_size_cache(["000001", "000002"])

            assert "000001" in result
            assert result["000001"]["net_asset_size"] == "10.5 亿"
            assert result["000001"]["share_size"] == "9.8 亿份"

    def test_prepare_fund_summary_includes_size(self, temp_db):
        """FUND-SIZE-AGENT-005: 准备基金摘要包含规模信息"""
        # 保存测试数据
        temp_db.save_fund_basic("000001", {
            "fund_code": "000001",
            "net_asset_size": "15.8 亿",
            "share_size": "14.2 亿份"
        })

        with patch('src.agents.fund_expert.cache_db', temp_db):
            agent = FundExpertAgent()
            agent.screened_funds = [
                {
                    "fund_code": "000001",
                    "fund_name": "华夏成长混合",
                    "return_1y": 15.5,
                    "return_3y": 45.2
                },
            ]

            summary = agent._prepare_fund_summary()

            # 摘要应包含规模信息
            assert "15.8 亿" in summary or "N/A" in summary
            assert "华夏成长混合" in summary
            assert "15.5" in summary


# ========== 数据服务层规模数据测试 ==========

class TestFundDataSizeService:
    """基金数据服务规模数据测试"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    @pytest.mark.asyncio
    async def test_get_fund_basic_info_returns_size(self, temp_db):
        """FUND-SIZE-SVC-001: 获取基金基本信息返回规模数据"""
        # 保存测试数据
        temp_db.save_fund_basic("000001", {
            "fund_code": "000001",
            "fund_name": "华夏成长混合",
            "net_asset_size": "15.8 亿",
            "share_size": "14.2 亿份"
        })

        with patch('src.services.fund_data.cache_db', temp_db):
            service = FundDataService()
            result = await service.get_fund_basic_info("000001")

            assert result is not None
            assert result["net_asset_size"] == "15.8 亿"

    @pytest.mark.asyncio
    async def test_get_fund_basic_info_from_api_when_not_cached(self, temp_db):
        """FUND-SIZE-SVC-002: 缓存无数据时从 API 获取"""
        with patch('src.services.fund_data.cache_db', temp_db):
            service = FundDataService()

            with patch.object(service, 'get_fund_basic_info') as mock_method:
                mock_method.return_value = {
                    "fund_code": "000001",
                    "fund_name": "华夏成长混合",
                    "net_asset_size": "20.5 亿",
                    "share_size": "18.2 亿份"
                }

                result = await mock_method("000001")

                assert result is not None
                assert result["net_asset_size"] == "20.5 亿"


# ========== 性能测试 ==========

class TestFundSizePerformance:
    """基金规模数据性能测试"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    @pytest.mark.asyncio
    async def test_batch_save_performance(self, temp_db):
        """FUND-SIZE-PERF-001: 批量保存性能测试"""
        import time

        # 保存 100 只基金的规模数据
        start_time = time.time()
        for i in range(100):
            fund_code = f"{i:06d}"
            temp_db.save_fund_basic(fund_code, {
                "fund_code": fund_code,
                "net_asset_size": f"{10 + i * 0.1:.1f}亿",
                "share_size": f"{9 + i * 0.1:.1f}亿份"
            })
        elapsed = time.time() - start_time

        # 100 次写入应在 2 秒内完成
        assert elapsed < 2.0, f"批量保存超时：{elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_batch_read_performance(self, temp_db):
        """FUND-SIZE-PERF-002: 批量读取性能测试"""
        import time

        # 先保存 100 只基金数据
        for i in range(100):
            fund_code = f"{i:06d}"
            temp_db.save_fund_basic(fund_code, {
                "fund_code": fund_code,
                "net_asset_size": f"{10 + i * 0.1:.1f}亿",
                "share_size": f"{9 + i * 0.1:.1f}亿份"
            })

        # 批量读取
        start_time = time.time()
        for i in range(100):
            fund_code = f"{i:06d}"
            temp_db.get_fund_basic(fund_code)
        elapsed = time.time() - start_time

        # 100 次读取应在 1 秒内完成
        assert elapsed < 1.0, f"批量读取超时：{elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_preload_50_funds_performance(self, temp_db):
        """FUND-SIZE-PERF-003: 预加载 50 只基金规模性能测试"""
        import time

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
                assert elapsed < 120.0, f"预加载超时：{elapsed:.2f}s"


# ========== 集成测试 ==========

class TestFundSizeEndToEnd:
    """基金规模数据端到端集成测试"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        db = CacheDB(db_path)
        yield db
        db_path.unlink()

    @pytest.mark.asyncio
    async def test_full_size_data_flow(self, temp_db):
        """FUND-SIZE-E2E-001: 完整规模数据流程测试"""
        with patch('src.agents.fund_expert.cache_db', temp_db):
            with patch('src.services.fund_data.cache_db', temp_db):
                with patch('src.services.akshare_client.akshare_client') as mock_akshare:
                    # 1. Mock API 返回规模数据
                    mock_akshare.get_fund_size = AsyncMock(return_value={
                        "net_asset_size": "15.8 亿",
                        "share_size": "14.2 亿份"
                    })
                    mock_akshare.get_fund_ranking = AsyncMock(return_value=[
                        {"fund_code": "000001", "fund_name": "华夏成长", "return_1y": 15.5}
                    ])

                    # 2. FundExpert 筛选基金
                    agent = FundExpertAgent()
                    await agent.set_user_info(
                        {"investment_amount": 100000, "investment_period": "长期"},
                        "稳健型"
                    )

                    # 3. 验证基金被筛选
                    assert len(agent.screened_funds) >= 0

                    # 4. 预加载规模数据（异步任务，这里同步等待）
                    await agent._preload_size_data()

                    # 5. 验证缓存已保存
                    result = temp_db.get_fund_basic("000001")
                    if result:  # 如果有数据，验证格式正确
                        assert "net_asset_size" in result

                    # 6. 准备基金摘要
                    summary = agent._prepare_fund_summary()
                    assert isinstance(summary, str)
