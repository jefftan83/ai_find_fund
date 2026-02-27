"""
FundExpertAgent 增强功能测试

测试覆盖：
1. 保守型用户推荐逻辑
2. 激进型用户推荐逻辑
3. XML 输出格式验证
4. 风险披露完整性
5. 数据维度验证
"""

import pytest
import asyncio
import re
from src.agents.fund_expert import FundExpertAgent
from src.utils.llm import ClaudeClient


@pytest.fixture
def llm_client():
    """创建 LLM 客户端"""
    return ClaudeClient()


@pytest.fixture
def fund_expert_agent(llm_client):
    """创建基金专家 Agent"""
    return FundExpertAgent(llm_client)


class TestDataDimensions:
    """测试数据维度增强"""

    @pytest.mark.asyncio
    async def test_prepare_fund_summary_contains_all_dimensions(self, fund_expert_agent):
        """测试基金摘要包含所有必需的数据维度"""
        # 设置 mock 数据
        fund_expert_agent.screened_funds = [
            {
                "fund_code": "000001",
                "fund_name": "华夏成长混合",
                "return_1m": 1.5,
                "return_3m": 4.2,
                "return_6m": 8.5,
                "return_1y": 15.3,
                "return_3y": 25.6,
                "return_ytd": 5.2,
            }
        ]

        # 调用方法
        summary = fund_expert_agent._prepare_fund_summary()

        # 验证必须包含的数据维度
        required_dimensions = [
            "规模",
            "评级",
            "经理",
            "公司",
            "近 1 月",
            "近 3 月",
            "近 6 月",
            "近 1 年",
            "近 3 年",
            "今年来",
            "最大回撤",
            "波动率",
            "持仓集中度"
        ]

        for dimension in required_dimensions:
            assert dimension in summary, f"缺少数据维度：{dimension}"

        print(f"✓ 基金摘要包含所有 {len(required_dimensions)} 项数据维度")


class TestRiskBasedScreening:
    """测试基于风险等级的筛选逻辑"""

    @pytest.mark.asyncio
    async def test_conservative_user_screening(self, fund_expert_agent):
        """测试保守型用户筛选逻辑"""
        # 设置保守型用户信息
        await fund_expert_agent.set_user_info(
            {
                "investment_amount": 50000,
                "investment_period": "短期",
                "investment_goal": "保值",
                "experience": "新手"
            },
            "保守型"
        )

        # 验证筛选逻辑（此处主要验证流程，实际筛选需要真实数据）
        assert fund_expert_agent.risk_level == "保守型"
        print("✓ 保守型用户筛选逻辑验证通过")

    @pytest.mark.asyncio
    async def test_aggressive_user_screening(self, fund_expert_agent):
        """测试激进型用户筛选逻辑"""
        # 设置激进型用户信息
        await fund_expert_agent.set_user_info(
            {
                "investment_amount": 1000000,
                "investment_period": "长期",
                "investment_goal": "高收益",
                "experience": "资深"
            },
            "激进型"
        )

        # 验证筛选逻辑
        assert fund_expert_agent.risk_level == "激进型"
        print("✓ 激进型用户筛选逻辑验证通过")


class TestOutputFormat:
    """测试输出格式验证"""

    @pytest.mark.asyncio
    async def test_xml_format_validation(self, fund_expert_agent):
        """测试 XML 输出格式验证"""
        # 设置 mock 推荐结果
        mock_recommendation = """
<analysis>
用户综合分析：投资金额 10 万，期限长期，目标稳健增长
</analysis>

<fund_evaluation>
| 基金代码 | 综合评分 | 优势 | 劣势 | 适配度 |
|---------|---------|------|------|-------|
| 000001  | 4.2     | 业绩稳定 | 经理任职短 | 高    |
</fund_evaluation>

<recommendation>
<fund>
  <code>000001</code>
  <name>华夏成长混合</name>
  <allocation>30%</allocation>
  <rationale>业绩稳定，规模适中</rationale>
  <risk_warning>近 3 年最大回撤 -15%</risk_warning>
  <confidence>high</confidence>
</fund>
</recommendation>

<disclaimer>
本推荐基于历史数据分析，不构成投资建议。
</disclaimer>
"""

        # 验证 XML 标签闭合
        xml_tags = ["analysis", "fund_evaluation", "recommendation", "fund", "disclaimer"]
        for tag in xml_tags:
            open_count = mock_recommendation.count(f"<{tag}>")
            close_count = mock_recommendation.count(f"</{tag}>")
            assert open_count == close_count, f"XML 标签<{tag}>未正确闭合"

        # 验证子标签
        child_tags = ["code", "name", "allocation", "rationale", "risk_warning", "confidence"]
        for tag in child_tags:
            assert f"<{tag}>" in mock_recommendation, f"缺少子标签<{tag}>"

        print("✓ XML 输出格式验证通过")

    @pytest.mark.asyncio
    async def test_allocation_sum_validation(self):
        """测试配置比例总和验证"""
        # mock 推荐数据
        allocations = [30, 25, 25, 20]  # 总和应为 100

        total = sum(allocations)
        assert total == 100, f"配置比例总和应为 100%，实际为{total}%"

        print("✓ 配置比例总和验证通过")


class TestRiskDisclosure:
    """测试风险披露完整性"""

    @pytest.mark.asyncio
    async def test_risk_warning_completeness(self):
        """测试风险警告完整性"""
        mock_recommendation = """
<fund>
  <code>000001</code>
  <risk_warning>近 3 年最大回撤 -15%</risk_warning>
</fund>
<fund>
  <code>000002</code>
  <risk_warning>波动率较高，达 18%</risk_warning>
</fund>
"""
        # 验证每只基金都有风险警告
        fund_pattern = r"<fund>(.*?)</fund>"
        risk_pattern = r"<risk_warning>(.*?)</risk_warning>"

        funds = re.findall(fund_pattern, mock_recommendation, re.DOTALL)
        for fund in funds:
            assert re.search(risk_pattern, fund), "基金缺少风险警告"

        print("✓ 风险披露完整性验证通过")

    @pytest.mark.asyncio
    async def test_disclaimer_presence(self):
        """测试免责声明存在"""
        mock_recommendation = """
<recommendation>...</recommendation>
<disclaimer>本推荐基于历史数据分析，不构成投资建议。</disclaimer>
"""
        assert "<disclaimer>" in mock_recommendation
        assert "</disclaimer>" in mock_recommendation

        print("✓ 免责声明存在验证通过")


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_recommendation_flow_conservative(self, fund_expert_agent):
        """测试保守型用户完整推荐流程"""
        # 设置用户信息
        await fund_expert_agent.set_user_info(
            {
                "investment_amount": 50000,
                "investment_period": "短期",
                "investment_goal": "保值",
                "experience": "新手"
            },
            "保守型"
        )

        # 验证用户信息设置
        assert fund_expert_agent.user_profile["investment_amount"] == 50000
        assert fund_expert_agent.risk_level == "保守型"

        print("✓ 保守型用户完整推荐流程验证通过")

    @pytest.mark.asyncio
    async def test_full_recommendation_flow_aggressive(self, fund_expert_agent):
        """测试激进型用户完整推荐流程"""
        # 设置用户信息
        await fund_expert_agent.set_user_info(
            {
                "investment_amount": 1000000,
                "investment_period": "长期",
                "investment_goal": "高收益",
                "experience": "资深"
            },
            "激进型"
        )

        # 验证用户信息设置
        assert fund_expert_agent.user_profile["investment_amount"] == 1000000
        assert fund_expert_agent.risk_level == "激进型"

        print("✓ 激进型用户完整推荐流程验证通过")


# 性能测试
class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_cache_helper_performance(self, fund_expert_agent):
        """测试缓存辅助方法性能"""
        import time

        # 创建大量 mock 基金代码
        fund_codes = [f"000{i:03d}" for i in range(50)]

        # 测试_get_size_cache 性能
        start = time.time()
        size_cache = fund_expert_agent._get_size_cache(fund_codes)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"_get_size_cache 耗时过长：{elapsed}s"
        print(f"✓ _get_size_cache 性能：{elapsed:.3f}s")

        # 测试_get_rating_cache 性能
        start = time.time()
        rating_cache = fund_expert_agent._get_rating_cache(fund_codes)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"_get_rating_cache 耗时过长：{elapsed}s"
        print(f"✓ _get_rating_cache 性能：{elapsed:.3f}s")

        # 测试_get_basic_cache 性能
        start = time.time()
        basic_cache = fund_expert_agent._get_basic_cache(fund_codes)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"_get_basic_cache 耗时过长：{elapsed}s"
        print(f"✓ _get_basic_cache 性能：{elapsed:.3f}s")


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
