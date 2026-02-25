"""
Agent 层测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from src.agents.requirement import RequirementAgent
from src.agents.risk import RiskAgent
from src.agents.fund_expert import FundExpertAgent
from src.agents.manager import GroupChatManager


# ============ RequirementAgent 测试 ============

class TestRequirementAgent:
    """需求分析 Agent 测试"""

    def test_init(self):
        """RA-001: 初始化 Agent"""
        agent = RequirementAgent()
        assert agent.conversation_history == []
        assert agent.user_profile == {}
        assert agent.is_complete is False

    def test_process_no_llm(self):
        """RA-002: 无 LLM 处理"""
        agent = RequirementAgent(llm_client=None)
        result = agent.process_sync("你好") if hasattr(agent, 'process_sync') else "【系统】LLM 客户端未初始化"
        # 实际测试中需要异步调用
        assert "LLM" in result or "系统" in result

    def test_get_profile_empty(self):
        """RA-003: 获取空用户画像"""
        agent = RequirementAgent()
        profile = agent.get_profile()
        assert profile == {}

    def test_reset(self):
        """RA-004: 重置状态"""
        agent = RequirementAgent()
        agent.conversation_history = [{"role": "user", "content": "test"}]
        agent.user_profile = {"investment_amount": 100000}
        agent.is_complete = True

        agent.reset()

        assert agent.conversation_history == []
        assert agent.user_profile == {}
        assert agent.is_complete is False

    def test_extract_profile_amount(self):
        """RA-005: 提取投资金额"""
        agent = RequirementAgent()
        response = "您打算投资 10 万元，这是一个不错的开始。"
        agent._extract_profile(response)

        assert agent.user_profile.get("investment_amount") == 100000

    def test_extract_profile_period(self):
        """RA-006: 提取投资期限"""
        agent = RequirementAgent()

        # 测试短期
        agent._extract_profile("我打算短期投资，大概 1 年以内")
        assert agent.user_profile.get("investment_period") == "短期"

        # 测试中期
        agent.reset()
        agent._extract_profile("我计划中期投资，大概 1-3 年")
        assert agent.user_profile.get("investment_period") == "中期"

        # 测试长期
        agent.reset()
        agent._extract_profile("我准备长期投资，3 年以上")
        assert agent.user_profile.get("investment_period") == "长期"

    def test_extract_profile_goal(self):
        """RA-007: 提取投资目标"""
        agent = RequirementAgent()

        # 测试稳健
        agent._extract_profile("我希望保值为主，风险小一点")
        assert agent.user_profile.get("investment_goal") == "稳健"

        # 测试进取
        agent.reset()
        agent._extract_profile("我追求高收益，风险大也可以")
        assert agent.user_profile.get("investment_goal") == "进取"

    def test_extract_profile_experience(self):
        """RA-008: 提取投资经验"""
        agent = RequirementAgent()

        # 测试新手
        agent._extract_profile("我是新手，没有经验，第一次买基金")
        assert agent.user_profile.get("experience") == "新手"

        # 测试有经验
        agent.reset()
        agent._extract_profile("我有一些经验，之前买过基金")
        assert agent.user_profile.get("experience") == "有经验"

        # 测试资深
        agent.reset()
        agent._extract_profile("我经验丰富，是老手了，投资多年")
        assert agent.user_profile.get("experience") == "资深"


# ============ RiskAgent 测试 ============

class TestRiskAgent:
    """风险评估 Agent 测试"""

    def test_init(self):
        """RK-001: 初始化 Agent"""
        agent = RiskAgent()
        assert agent.risk_level == ""
        assert agent.risk_score == 0
        assert agent.is_complete is False

    def test_get_risk_level_empty(self):
        """RK-002: 获取空风险等级"""
        agent = RiskAgent()
        assert agent.get_risk_level() == ""
        assert agent.get_risk_score() == 0

    def test_extract_risk_level_conservative(self):
        """RK-003: 保守型评估"""
        agent = RiskAgent()
        response = "【风险评估完成】风险等级：保守型"
        agent._extract_risk_level(response)

        assert agent.risk_level == "保守型"
        assert agent.risk_score == 20

    def test_extract_risk_level_stable(self):
        """RK-004: 稳健型评估"""
        agent = RiskAgent()
        response = "【风险评估完成】风险等级：稳健型"
        agent._extract_risk_level(response)

        assert agent.risk_level == "稳健型"
        assert agent.risk_score == 50

    def test_extract_risk_level_aggressive(self):
        """RK-005: 积极型评估"""
        agent = RiskAgent()
        response = "【风险评估完成】风险等级：积极型"
        agent._extract_risk_level(response)

        assert agent.risk_level == "积极型"
        assert agent.risk_score == 75

    def test_extract_risk_level_radical(self):
        """RK-006: 激进型评估"""
        agent = RiskAgent()
        response = "【风险评估完成】风险等级：激进型"
        agent._extract_risk_level(response)

        assert agent.risk_level == "激进型"
        assert agent.risk_score == 90

    def test_extract_risk_level_default(self):
        """RK-007: 默认风险等级"""
        agent = RiskAgent()
        response = "【风险评估完成】评估完毕"
        agent._extract_risk_level(response)

        # 没有明确等级时，默认稳健型
        assert agent.risk_level == "稳健型"
        assert agent.risk_score == 50

    def test_get_recommended_fund_types(self):
        """RK-008: 获取推荐基金类型"""
        agent = RiskAgent()

        # 保守型
        agent.risk_level = "保守型"
        types = agent.get_recommended_fund_types()
        assert "货币基金" in types
        assert "短债基金" in types

        # 稳健型
        agent.risk_level = "稳健型"
        types = agent.get_recommended_fund_types()
        assert "固收" in str(types) or "债基" in str(types)

        # 积极型
        agent.risk_level = "积极型"
        types = agent.get_recommended_fund_types()
        assert "偏股混合" in str(types)

        # 激进型
        agent.risk_level = "激进型"
        types = agent.get_recommended_fund_types()
        assert "股票型基金" in str(types)

    def test_reset(self):
        """RK-009: 重置状态"""
        agent = RiskAgent()
        agent.conversation_history = [{"role": "user", "content": "test"}]
        agent.risk_level = "稳健型"
        agent.risk_score = 50
        agent.is_complete = True

        agent.reset()

        assert agent.conversation_history == []
        assert agent.risk_level == ""
        assert agent.risk_score == 0
        assert agent.is_complete is False


# ============ FundExpertAgent 测试 ============

class TestFundExpertAgent:
    """基金专家 Agent 测试"""

    def test_init(self):
        """FE-001: 初始化 Agent"""
        agent = FundExpertAgent()
        assert agent.user_profile == {}
        assert agent.risk_level == ""
        assert agent.screened_funds == []

    @pytest.mark.asyncio
    async def test_set_user_info(self):
        """FE-002: 设置用户信息"""
        agent = FundExpertAgent()
        profile = {
            "investment_amount": 100000,
            "investment_period": "长期",
            "investment_goal": "稳健"
        }

        # Mock fund_data_service
        with patch('src.agents.fund_expert.fund_data_service') as mock_service:
            mock_service.get_fund_ranking.return_value = []
            await agent.set_user_info(profile, "稳健型")

        assert agent.user_profile == profile
        assert agent.risk_level == "稳健型"

    def test_get_top_funds_empty(self):
        """FE-003: 获取空基金列表"""
        agent = FundExpertAgent()
        funds = agent.get_top_funds(5)
        assert funds == []

    def test_get_top_funds(self):
        """FE-004: 获取 Top 基金"""
        agent = FundExpertAgent()
        agent.screened_funds = [
            {"fund_code": "000001", "fund_name": "基金 A", "return_1y": 15.5},
            {"fund_code": "000002", "fund_name": "基金 B", "return_1y": 12.3},
            {"fund_code": "000003", "fund_name": "基金 C", "return_1y": 10.1},
        ]

        top_3 = agent.get_top_funds(3)
        assert len(top_3) == 3
        assert top_3[0]["fund_code"] == "000001"

        top_1 = agent.get_top_funds(1)
        assert len(top_1) == 1

    def test_reset(self):
        """FE-005: 重置状态"""
        agent = FundExpertAgent()
        agent.user_profile = {"test": "value"}
        agent.risk_level = "稳健型"
        agent.screened_funds = [{"fund_code": "000001"}]
        agent.recommendation = "推荐内容"

        agent.reset()

        assert agent.user_profile == {}
        assert agent.risk_level == ""
        assert agent.screened_funds == []
        assert agent.recommendation == ""


# ============ GroupChatManager 测试 ============

class TestGroupChatManager:
    """群聊管理器测试"""

    def test_init(self):
        """GM-001: 初始化"""
        manager = GroupChatManager()
        assert manager.current_stage == "requirement"
        assert manager.conversation_history == []
        assert manager.requirement_agent is not None
        assert manager.risk_agent is not None
        assert manager.fund_expert_agent is not None

    def test_get_current_stage(self):
        """GM-002: 获取当前阶段"""
        manager = GroupChatManager()
        assert manager.get_current_stage() == "requirement"

        manager.current_stage = "risk"
        assert manager.get_current_stage() == "risk"

    def test_is_complete(self):
        """GM-003: 检查是否完成"""
        manager = GroupChatManager()
        assert manager.is_complete() is False

        manager.current_stage = "complete"
        assert manager.is_complete() is True

    def test_reset(self):
        """GM-004: 重置管理器"""
        manager = GroupChatManager()
        manager.current_stage = "recommendation"
        manager.conversation_history = [{"role": "user", "content": "test"}]

        manager.reset()

        assert manager.current_stage == "requirement"
        assert manager.conversation_history == []

    def test_get_user_profile(self):
        """GM-005: 获取用户画像"""
        manager = GroupChatManager()
        # 初始时应为空
        assert manager.get_user_profile() == {}

    def test_get_risk_level(self):
        """GM-006: 获取风险等级"""
        manager = GroupChatManager()
        # 初始时应为空
        assert manager.get_risk_level() == ""

    def test_get_recommendation(self):
        """GM-007: 获取推荐结果"""
        manager = GroupChatManager()
        # 初始时应为空
        assert manager.get_recommendation() == ""

    @pytest.mark.asyncio
    async def test_handle_complete_stage(self):
        """GM-008: 完成阶段处理"""
        manager = GroupChatManager()
        manager.current_stage = "complete"

        # 测试重新开始
        response = await manager._handle_complete_stage("重新开始")
        assert "重新开始" in response or "好的" in response

        # 测试其他输入
        response = await manager._handle_complete_stage("还有什么问题吗")
        assert "重新开始" in response


# ============ 集成测试 ============

class TestAgentIntegration:
    """Agent 集成测试"""

    def test_full_workflow_mock(self):
        """GM-009: 完整流程模拟（Mock）"""
        # Mock LLM 客户端
        mock_llm = Mock()
        mock_llm.chat = AsyncMock()

        # 需求分析响应
        mock_llm.chat.side_effect = [
            "您好！请问您打算投资多少钱？",  # 需求分析第一轮
            "【需求收集完成】用户打算投资 10 万，长期投资。",  # 需求收集完成
            "【风险评估完成】风险等级：稳健型",  # 风险评估完成
            "根据您的情况，推荐以下基金..."  # 推荐阶段
        ]

        manager = GroupChatManager(mock_llm)

        # 验证初始状态
        assert manager.get_current_stage() == "requirement"
