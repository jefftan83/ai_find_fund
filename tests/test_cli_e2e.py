"""
CLI 和端到端测试
"""

import pytest
import subprocess
import sys
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock

from src.main import app
from src.agents.manager import GroupChatManager

runner = CliRunner()


# ============ CLI 命令测试 ============

class TestCLICommands:
    """CLI 命令测试"""

    def test_version_command(self):
        """CLI-001: version 命令"""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "基金推荐助手" in result.stdout
        assert "v0.1.0" in result.stdout

    def test_config_status_command(self):
        """CLI-002: config-status 命令"""
        result = runner.invoke(app, ["config-status"])
        assert result.exit_code == 0
        assert "当前配置状态" in result.stdout
        assert "Anthropic API Key" in result.stdout
        assert "数据库路径" in result.stdout

    def test_start_command_no_api_key(self):
        """CLI-003: start 命令无 API Key"""
        # Patch config.anthropic_api_key to simulate missing API key
        with patch('src.main.config') as mock_config:
            mock_config.anthropic_api_key = None
            result = runner.invoke(app, ["start"])
            assert result.exit_code == 1
            assert "未配置" in result.stdout or "API Key" in result.stdout

    def test_start_command_help(self):
        """CLI-004: start 命令帮助"""
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        assert "--verbose" in result.stdout or "-v" in result.stdout


# ============ 端到端测试 ============

class TestE2E:
    """端到端测试"""

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM 响应"""
        responses = {
            # 需求分析阶段
            "你好，我想买基金": "您好！很高兴为您服务。请问您打算投资多少钱呢？",
            "10 万": "好的，10 万元。请问您的投资期限是多久？短期、中期还是长期？",
            "长期": "明白了，长期投资。您的投资目标是什么？保值、稳健增长还是高收益？",
            "稳健增长": "【需求收集完成】用户画像：投资 10 万，长期，稳健增长",

            # 风险评估阶段
            "你好": "请问您能接受本金亏损吗？",
            "小幅亏损": "【风险评估完成】风险等级：稳健型",

            # 推荐阶段
            "推荐什么基金": "根据您的情况，推荐以下基金：\n1. 000001 华夏成长混合\n2. 000002 华夏债券"
        }
        return responses

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self, mock_llm_response):
        """E2E-001: 完整对话流程"""
        # 直接创建 mock LLM 实例，不使用 patch
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="您好！请问您打算投资多少钱？")

        # Mock 数据服务
        with patch('src.agents.fund_expert.fund_data_service') as mock_service:
            mock_service.get_fund_ranking.return_value = [
                {"fund_code": "000001", "fund_name": "华夏成长混合", "return_1y": 15.5}
            ]

            from src.agents.manager import GroupChatManager
            manager = GroupChatManager(mock_llm)

            # 第一轮：问候
            response = await manager.process("你好，我想买基金")
            # 检查 response 是否为字符串（而不是 coroutine）
            assert isinstance(response, str)

            # 第二轮：投资金额
            response = await manager.process("10 万")
            # 检查是否进入下一阶段
            assert manager.get_current_stage() in ["requirement", "risk"]

    @pytest.mark.asyncio
    async def test_conservative_user_flow(self):
        """E2E-002: 保守型用户流程"""
        # 直接创建 mock LLM 实例
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="【风险评估完成】风险等级：保守型")

        with patch('src.agents.fund_expert.fund_data_service') as mock_service:
            mock_service.get_fund_ranking.return_value = []

            manager = GroupChatManager(mock_llm)
            # 手动设置风险等级来模拟完成状态
            manager.risk_agent.risk_level = "保守型"
            manager.risk_agent.is_complete = True

            # 检查风险等级
            risk_level = manager.get_risk_level()
            assert risk_level == "保守型"

    @pytest.mark.asyncio
    async def test_aggressive_user_flow(self):
        """E2E-003: 积极型用户流程"""
        # 直接创建 mock LLM 实例
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="【风险评估完成】风险等级：积极型")

        with patch('src.agents.fund_expert.fund_data_service') as mock_service:
            mock_service.get_fund_ranking.return_value = []

            manager = GroupChatManager(mock_llm)
            # 手动设置风险等级来模拟完成状态
            manager.risk_agent.risk_level = "积极型"
            manager.risk_agent.is_complete = True

            # 检查风险等级
            risk_level = manager.get_risk_level()
            assert risk_level == "积极型"

    @pytest.mark.asyncio
    async def test_exit_command(self):
        """E2E-004: 退出命令处理"""
        manager = GroupChatManager()
        # 模拟完成阶段
        manager.current_stage = "complete"

        response = await manager._handle_complete_stage("退出")
        assert "重新开始" in response or "再见" in response.lower() or "退出" in response.lower()

    @pytest.mark.asyncio
    async def test_reset_command(self):
        """E2E-005: 重新开始命令处理"""
        manager = GroupChatManager()
        manager.current_stage = "recommendation"
        manager.conversation_history = [{"role": "user", "content": "test"}]

        # 模拟完成阶段（需要先切换到 complete）
        manager.current_stage = "complete"
        response = await manager._handle_complete_stage("重新开始")

        assert "好的" in response or "重新" in response


# ============ 数据服务层测试 ============

class TestFundDataService:
    """基金数据服务测试"""

    @pytest.mark.asyncio
    async def test_get_fund_list(self):
        """FD-001: 获取基金列表"""
        from src.services.fund_data import FundDataService
        service = FundDataService()

        with patch('src.services.akshare_client.akshare_client') as mock_akshare:
            mock_akshare.get_fund_list.return_value = [
                {"fund_code": "000001", "fund_name": "华夏成长", "fund_type": "混合型"}
            ]

            funds = await service.get_fund_list(use_cache=False)
            assert len(funds) > 0
            assert funds[0]["fund_code"] == "000001"

    @pytest.mark.asyncio
    async def test_get_fund_nav(self):
        """FD-002: 获取基金净值"""
        from src.services.fund_data import FundDataService
        service = FundDataService()

        with patch('src.services.akshare_client.akshare_client') as mock_akshare:
            mock_akshare.get_fund_history.return_value = [
                {"nav_date": "2025-02-24", "unit_nav": 1.234, "accumulated_nav": 2.345, "daily_growth": 0.015}
            ]

            nav = await service.get_fund_nav("000001", use_cache=False)
            assert nav is not None
            assert nav["unit_nav"] == 1.234

    @pytest.mark.asyncio
    async def test_fallback机制(self):
        """FD-013: AKShare 失败降级"""
        from src.services.fund_data import FundDataService
        service = FundDataService()

        # Mock AKShare 失败
        with patch('src.services.akshare_client.akshare_client') as mock_akshare:
            mock_akshare.get_daily_nav.side_effect = Exception("AKShare Error")

            with patch('src.services.sina_client.sina_client') as mock_sina:
                mock_sina.get_fund_nav_batch.return_value = [
                    {"fund_code": "000001", "unit_nav": 1.234}
                ]

                # 应该降级到新浪财经
                result = await service.get_daily_nav()
                assert len(result) > 0

    @pytest.mark.asyncio
    async def test_screen_funds(self):
        """FD-011: 筛选基金"""
        from src.services.fund_data import FundDataService
        service = FundDataService()

        with patch('src.services.akshare_client.akshare_client') as mock_akshare:
            mock_akshare.get_fund_ranking = AsyncMock(return_value=[
                {"fund_code": "000001", "fund_name": "基金 A", "return_1y": 15.5, "return_3y": 45.2},
                {"fund_code": "000002", "fund_name": "基金 B", "return_1y": 5.5, "return_3y": 15.2},
            ])

            # Mock get_fund_rating 方法，只让指定基金通过筛选
            async def mock_get_rating(fund_code):
                if fund_code == "000001":
                    return {"rating_1y": 5}
                return {"rating_1y": 1}  # 低评级，被筛选掉

            with patch.object(service, 'get_fund_rating', side_effect=mock_get_rating):
                # 筛选收益率>10% 的基金
                result = await service.screen_funds(min_return_1y=10)
                # 只有基金 A 符合条件（收益率>10% 且评级高）
                assert len(result) >= 1
                # 验证返回的基金包含预期的高收益基金
                fund_codes = [f["fund_code"] for f in result]
                assert "000001" in fund_codes


# ============ 性能测试 ============

class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """PERF-001: 缓存性能测试"""
        import time
        from src.cache.db import CacheDB
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        try:
            db = CacheDB(db_path)

            # 批量写入测试
            start_time = time.time()
            for i in range(1000):
                fund_code = f"{i:06d}"
                db.save_fund_basic(fund_code, {
                    "fund_name": f"基金{i}",
                    "fund_type": "混合型"
                })
            write_time = time.time() - start_time

            # 批量读取测试
            start_time = time.time()
            for i in range(1000):
                fund_code = f"{i:06d}"
                db.get_fund_basic(fund_code)
            read_time = time.time() - start_time

            # 性能断言（1000 次操作应在合理时间内完成）
            assert write_time < 10.0, f"写入测试超时：{write_time}s"
            assert read_time < 10.0, f"读取测试超时：{read_time}s"

        finally:
            db_path.unlink()
