"""
AKShare 数据源客户端测试
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd

from src.services.akshare_client import AKShareClient


@pytest.fixture
def akshare_client():
    """创建 AKShare 客户端实例"""
    return AKShareClient()


class TestAKShareClient:
    """AKShareClient 类测试"""

    def test_initialization(self, akshare_client):
        """AKS-001: 客户端初始化"""
        assert akshare_client._akshare is None

    @pytest.mark.asyncio
    async def test_get_fund_list(self, akshare_client):
        """AKS-002: 获取基金列表"""
        # Mock AKShare 返回数据
        mock_df = pd.DataFrame([
            ["000001", "HXCH", "华夏成长", "混合型", "huaxiachengzhang"],
            ["000002", "HXZQ", "华夏债券", "债券型", "huaxiazhaiquan"],
        ])

        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_name_em.return_value = mock_df
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_list()

            assert len(result) == 2
            assert result[0]["fund_code"] == "000001"
            assert result[0]["fund_name"] == "华夏成长"
            assert result[0]["fund_type"] == "混合型"

    @pytest.mark.asyncio
    async def test_get_fund_list_error(self, akshare_client):
        """AKS-003: 获取基金列表异常处理"""
        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_name_em.side_effect = Exception("API Error")
            mock_get.return_value = mock_ak

            with pytest.raises(Exception) as exc_info:
                await akshare_client.get_fund_list()
            assert "API Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_daily_nav(self, akshare_client):
        """AKS-004: 获取当日净值"""
        # Mock 带日期列名的 DataFrame
        mock_df = pd.DataFrame([
            ["000001", "华夏成长", 1.234, 2.345, 1.220, 2.330, 0.014, 0.015],
        ])
        mock_df.columns = ["基金代码", "基金简称", "2026-02-25-单位净值", "2026-02-25-累计净值",
                         "上日单位净值", "上日累计净值", "日增长值", "日增长率"]

        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_open_fund_daily_em.return_value = mock_df
            mock_get.return_value = mock_ak

            result = await akshare_client.get_daily_nav()

            assert len(result) == 1
            assert result[0]["fund_code"] == "000001"
            assert result[0]["unit_nav"] == 1.234
            assert result[0]["accumulated_nav"] == 2.345
            assert result[0]["nav_date"] == "2026-02-25"

    @pytest.mark.asyncio
    async def test_get_fund_history(self, akshare_client):
        """AKS-005: 获取基金历史净值"""
        mock_df = pd.DataFrame([
            ["2026-02-25", 1.234, 2.345, 0.015],
            ["2026-02-24", 1.220, 2.330, 0.010],
        ])

        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_open_fund_info_em.return_value = mock_df
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_history("000001")

            assert len(result) == 2
            assert result[0]["nav_date"] == "2026-02-25"
            assert result[0]["unit_nav"] == 1.234

    @pytest.mark.asyncio
    async def test_get_fund_ranking(self, akshare_client):
        """AKS-006: 获取基金排行"""
        # Mock data with correct column structure matching the actual code
        # Column indices: 0-序号，1-基金代码，2-基金简称，8-近 1 月，9-近 3 月，10-近 6 月，11-近 1 年，13-近 3 年，14-今年来
        # 需要 15 列数据来匹配 iloc[14] 的访问
        mock_df = pd.DataFrame([
            [1, "000001", "华夏成长", None, None, None, None, None, 5.0, 10.0, 12.0, 15.5, None, 45.2, 10.2],
            [2, "000002", "华夏债券", None, None, None, None, None, 2.0, 4.0, 6.0, 8.5, None, 25.0, 5.1],
        ])

        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_open_fund_rank_em.return_value = mock_df
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_ranking()

            assert len(result) == 2
            assert result[0]["fund_code"] == "000001"
            assert result[0]["return_1y"] == 15.5
            assert result[0]["return_3y"] == 45.2

    @pytest.mark.asyncio
    async def test_get_fund_ranking_with_nan(self, akshare_client):
        """AKS-007: 获取基金排行处理 NaN 值"""
        import math
        # Mock data with NaN value for 3y return
        mock_df = pd.DataFrame([
            [1, "000001", "新基金", 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, float('nan'), 12.0, 14.0, 16.0, float('nan'), 2.0],
        ])

        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_open_fund_rank_em.return_value = mock_df
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_ranking()

            assert len(result) == 1
            # NaN 值应该被转换为 0
            assert result[0]["return_3y"] == 0

    @pytest.mark.asyncio
    async def test_get_fund_holdings(self, akshare_client):
        """AKS-008: 获取基金持仓"""
        mock_df = pd.DataFrame([
            [1, "600001", "浦发银行", 5.5, 100000, 550000, "2024Q4"],
            [2, "600002", "中国石化", 4.8, 80000, 480000, "2024Q4"],
        ])

        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_portfolio_hold_em.return_value = mock_df
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_holdings("000001")

            assert len(result) == 2
            assert result[0]["stock_code"] == "600001"
            assert result[0]["stock_name"] == "浦发银行"
            assert result[0]["holding_ratio"] == 5.5

    @pytest.mark.asyncio
    async def test_get_fund_rating(self, akshare_client):
        """AKS-009: 获取基金评级"""
        mock_df = pd.DataFrame([
            ["000001", "华夏成长", "张三", "华夏基金", 5, 5, 4, 5, "★★★"],
            ["000002", "华夏债券", "李四", "华夏基金", 4, 4, 3, 4, "★★★"],
        ])

        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_rating_all.return_value = mock_df
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_rating()

            assert len(result) == 2
            assert result[0]["fund_code"] == "000001"
            assert result[0]["rating_1y"] == 5
            assert result[0]["rating_3y"] == 5

    @pytest.mark.asyncio
    async def test_get_fund_basic_info(self, akshare_client):
        """AKS-010: 获取基金基本信息"""
        mock_df = pd.DataFrame([
            ["华夏成长混合型证券投资基金", "华夏成长", "000001", "混合型",
             "2002-01-01", "2002-01-01 / 20 亿", "10.5 亿", "9.8 亿份",
             "华夏基金管理有限公司", "中国建设银行", "张三"]
        ])

        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_overview_em.return_value = mock_df
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_basic_info("000001")

            assert result["fund_code"] == "000001"
            assert result["fund_name"] == "华夏成长"
            assert result["fund_type"] == "混合型"
            assert result["manager"] == "张三"
            assert result["net_asset_size"] == "10.5 亿"
            assert result["share_size"] == "9.8 亿份"

    @pytest.mark.asyncio
    async def test_get_fund_size(self, akshare_client):
        """AKS-011: 获取基金规模"""
        mock_df = pd.DataFrame([
            ["华夏成长混合型证券投资基金", "华夏成长", "000001", "混合型",
             "2002-01-01", "2002-01-01 / 20 亿", "10.5 亿", "9.8 亿份",
             "华夏基金管理有限公司", "中国建设银行", "张三"]
        ])

        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_overview_em.return_value = mock_df
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_size("000001")

            assert result["net_asset_size"] == "10.5 亿"
            assert result["share_size"] == "9.8 亿份"

    @pytest.mark.asyncio
    async def test_get_fund_size_empty(self, akshare_client):
        """AKS-012: 获取基金规模返回空"""
        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_overview_em.return_value = pd.DataFrame()
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_size("000001")
            assert result == {}

    @pytest.mark.asyncio
    async def test_get_fund_size_error(self, akshare_client):
        """AKS-013: 获取基金规模异常处理"""
        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_overview_em.side_effect = Exception("API Error")
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_size("000001")
            # 应该返回空字典而不是抛出异常
            assert result == {}

    @pytest.mark.asyncio
    async def test_get_fund_basic_info_empty(self, akshare_client):
        """AKS-014: 获取基金基本信息返回空"""
        with patch.object(akshare_client, '_get_akshare') as mock_get:
            mock_ak = MagicMock()
            mock_ak.fund_overview_em.return_value = pd.DataFrame()
            mock_get.return_value = mock_ak

            result = await akshare_client.get_fund_basic_info("000001")
            assert result == {}
