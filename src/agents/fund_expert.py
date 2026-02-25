"""基金专家 Agent - 根据用户需求和风险等级推荐基金"""

from typing import Dict, Any, List
from src.utils.llm import ClaudeClient
from src.services.fund_data import fund_data_service


class FundExpertAgent:
    """
    基金专家 Agent

    负责根据用户画像和风险等级，筛选和推荐合适的基金组合：
    - 调用数据服务获取基金数据
    - 根据条件筛选基金
    - 生成配置建议
    """

    SYSTEM_PROMPT = """你是一位经验丰富的基金投资专家。
你的任务是根据用户的投资需求和风险等级，推荐合适的基金组合。

推荐基金时需要考虑：
1. 用户的投资金额和期限
2. 用户的风险等级（保守/稳健/积极/激进）
3. 基金的历史业绩（近 1 年、近 3 年收益）
4. 基金的风险指标（波动率、最大回撤）
5. 基金的评级
6. 基金经理的稳定性
7. 基金公司的实力

资产配置建议：
- 保守型：80% 债券基金 + 20% 货币基金
- 稳健型：50% 债券基金 + 30% 固收 +/ 平衡混合 + 20% 偏股基金
- 积极型：40% 债券基金 + 40% 偏股混合 + 20% 指数基金
- 激进型：20% 债券基金 + 50% 股票型/行业基金 + 30% 指数基金

输出格式：
1. 先分析用户情况
2. 给出资产配置建议
3. 推荐具体基金（3-5 只），包括：
   - 基金代码和名称
   - 推荐理由
   - 建议配置比例
   - 风险提示
4. 给出投资建议和注意事项

请用中文回复，专业但通俗易懂。"""

    def __init__(self, llm_client: ClaudeClient = None):
        self.llm = llm_client
        self.user_profile: Dict[str, Any] = {}
        self.risk_level: str = ""
        self.screened_funds: List[Dict[str, Any]] = []
        self.recommendation: str = ""

    async def set_user_info(self, user_profile: Dict[str, Any], risk_level: str):
        """
        设置用户信息

        Args:
            user_profile: 用户画像
            risk_level: 风险等级
        """
        self.user_profile = user_profile
        self.risk_level = risk_level

        # 根据风险等级筛选基金
        await self._screen_funds()

    async def _screen_funds(self):
        """筛选基金"""
        # 获取基金排行
        fund_type_map = {
            "保守型": "债券型",
            "稳健型": "混合型",
            "积极型": "混合型",
            "激进型": "股票型"
        }

        target_type = fund_type_map.get(self.risk_level, "混合型")

        try:
            # 获取排行数据
            ranking = await fund_data_service.get_fund_ranking(target_type)

            # 筛选：近 1 年收益>0，近 3 年收益>0
            self.screened_funds = [
                f for f in ranking
                if f.get("return_1y", 0) > 0 and f.get("return_3y", 0) > 0
            ][:20]  # 取前 20 只

        except Exception as e:
            print(f"筛选基金失败：{e}")
            self.screened_funds = []

    async def generate_recommendation(self) -> str:
        """
        生成基金推荐

        Returns:
            推荐内容
        """
        if not self.llm:
            return "【系统】LLM 客户端未初始化"

        if not self.screened_funds:
            return "【系统】暂无符合条件的基金数据，请稍后重试"

        # 准备基金数据摘要
        fund_summary = self._prepare_fund_summary()

        # 准备用户信息摘要
        user_summary = f"""
用户投资画像：
- 投资金额：{self.user_profile.get('investment_amount', '未指定')}元
- 投资期限：{self.user_profile.get('investment_period', '未指定')}
- 投资目标：{self.user_profile.get('investment_goal', '未指定')}
- 投资经验：{self.user_profile.get('experience', '未指定')}
- 风险等级：{self.risk_level}
"""

        # 调用 LLM 生成推荐
        try:
            messages = [
                {"role": "user", "content": f"""
{user_summary}

可选基金池（近 1 年、近 3 年收益均为正）：
{fund_summary}

请根据用户情况，推荐 3-5 只基金，并给出配置建议。
"""}
            ]

            response = self.llm.chat(
                messages=messages,
                system=self.SYSTEM_PROMPT,
                max_tokens=2000
            )

            self.recommendation = response
            return response

        except Exception as e:
            return f"【系统错误】生成推荐失败：{str(e)}"

    def _prepare_fund_summary(self) -> str:
        """准备基金数据摘要"""
        lines = []
        for i, fund in enumerate(self.screened_funds[:10], 1):
            lines.append(f"""
{i}. {fund.get('fund_code')} - {fund.get('fund_name')}
   近 1 月：{fund.get('return_1m', 0):.2f}% | 近 3 月：{fund.get('return_3m', 0):.2f}%
   近 6 月：{fund.get('return_6m', 0):.2f}% | 近 1 年：{fund.get('return_1y', 0):.2f}%
   近 3 年：{fund.get('return_3y', 0):.2f}% | 今年来：{fund.get('return_ytd', 0):.2f}%
""")
        return "\n".join(lines)

    def get_top_funds(self, n: int = 5) -> List[Dict[str, Any]]:
        """获取推荐的 top N 基金"""
        return self.screened_funds[:n]

    def reset(self):
        """重置 Agent 状态"""
        self.user_profile = {}
        self.risk_level = ""
        self.screened_funds = []
        self.recommendation = ""


# 测试用
if __name__ == "__main__":
    async def test():
        llm = ClaudeClient()
        agent = FundExpertAgent(llm)

        print("基金专家 Agent 测试\n")

        # 设置用户信息
        await agent.set_user_info(
            {
                "investment_amount": 100000,
                "investment_period": "长期",
                "investment_goal": "稳健增长",
                "experience": "有经验"
            },
            "稳健型"
        )

        # 生成推荐
        response = await agent.generate_recommendation()
        print(f"推荐结果:\n{response}")
