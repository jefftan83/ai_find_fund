"""Group Chat Manager - 协调多 Agent 对话"""

from typing import Dict, Any, List, Optional
from src.utils.llm import ClaudeClient
from src.agents.requirement import RequirementAgent
from src.agents.risk import RiskAgent
from src.agents.fund_expert import FundExpertAgent
from src.agents.critic import CriticAgent


class GroupChatManager:
    """
    群聊管理器

    负责协调多个 Agent 之间的对话流程：
    1. 需求分析阶段 → RequirementAgent
    2. 风险评估阶段 → RiskAgent
    3. 基金推荐阶段 → FundExpertAgent
    4. 验证阶段 → CriticAgent

    使用状态机管理对话流程
    """

    # 对话阶段
    STAGE_REQUIREMENT = "requirement"
    STAGE_RISK = "risk"
    STAGE_RECOMMENDATION = "recommendation"
    STAGE_VALIDATION = "validation"
    STAGE_COMPLETE = "complete"

    SYSTEM_PROMPT = """你是一个基金推荐助手。
你的任务是根据用户输入，调用合适的 Agent 进行处理。

当前对话阶段：
- requirement: 需求分析阶段
- risk: 风险评估阶段
- recommendation: 基金推荐阶段
- validation: 验证阶段
- complete: 完成

请根据当前阶段和用户输入，生成合适的回复。
"""

    def __init__(self, llm_client: ClaudeClient = None):
        self.llm = llm_client

        # 初始化各 Agent
        self.requirement_agent = RequirementAgent(llm_client)
        self.risk_agent = RiskAgent(llm_client)
        self.fund_expert_agent = FundExpertAgent(llm_client)
        self.critic_agent = CriticAgent()  # 验证器不需要 LLM

        # 当前阶段
        self.current_stage = self.STAGE_REQUIREMENT
        self.conversation_history: List[Dict[str, str]] = []
        self.last_validation_result = None

    async def process(self, user_input: str) -> str:
        """
        处理用户输入

        Args:
            user_input: 用户输入

        Returns:
            回复内容
        """
        # 添加到历史
        self.conversation_history.append({"role": "user", "content": user_input})

        # 根据当前阶段调用相应的 Agent
        if self.current_stage == self.STAGE_REQUIREMENT:
            response = await self._handle_requirement_stage(user_input)
        elif self.current_stage == self.STAGE_RISK:
            response = await self._handle_risk_stage(user_input)
        elif self.current_stage == self.STAGE_RECOMMENDATION:
            response = await self._handle_recommendation_stage(user_input)
        elif self.current_stage == self.STAGE_COMPLETE:
            response = await self._handle_complete_stage(user_input)
        else:
            response = "【系统错误】未知阶段"

        # 添加回复到历史
        self.conversation_history.append({"role": "assistant", "content": response})

        return response

    async def _handle_requirement_stage(self, user_input: str) -> str:
        """处理需求分析阶段"""
        response = await self.requirement_agent.process(user_input)

        # 检查需求分析是否完成
        if self.requirement_agent.is_complete:
            self.current_stage = self.STAGE_RISK
            # 初始化风险评估
            await self.risk_agent.process("你好，我来帮您评估风险承受能力")

        return response

    async def _handle_risk_stage(self, user_input: str) -> str:
        """处理风险评估阶段"""
        response = await self.risk_agent.process(user_input)

        # 检查风险评估是否完成
        if self.risk_agent.is_complete:
            self.current_stage = self.STAGE_RECOMMENDATION
            # 设置用户信息并生成推荐
            profile = self.requirement_agent.get_profile()
            risk_level = self.risk_agent.get_risk_level()
            await self.fund_expert_agent.set_user_info(profile, risk_level)
            # 自动生成推荐
            return response + "\n\n" + await self._generate_and_validate_recommendation()

        return response

    async def _generate_and_validate_recommendation(self, retry_count: int = 0) -> str:
        """生成并验证推荐（支持重试）"""
        # 生成推荐
        recommendation = await self.fund_expert_agent.generate_recommendation()

        # 验证推荐
        profile = self.requirement_agent.get_profile()
        risk_level = self.risk_agent.get_risk_level()

        validation = self.critic_agent.validate(recommendation, profile, risk_level)
        self.last_validation_result = validation

        if not validation.passed and retry_count < 2:
            # 验证失败，尝试重新生成（最多 2 次）
            feedback = self.critic_agent.generate_improvement_suggestions(validation)
            print(f"验证失败，重新生成中...\n{feedback}")

            # 要求重新生成
            return await self._regenerate_with_feedback(feedback, retry_count + 1)

        # 验证通过，返回推荐
        return recommendation + f"\n\n【验证通过】得分：{validation.score:.0f}/100"

    async def _regenerate_with_feedback(self, feedback: str, retry_count: int) -> str:
        """要求 FundExpertAgent 重新生成（带反馈）"""
        if not self.llm:
            return "【系统】LLM 客户端未初始化"

        # 获取当前推荐和基金数据
        current_recommendation = self.fund_expert_agent.recommendation
        fund_summary = self.fund_expert_agent._prepare_fund_summary()

        # 准备用户信息摘要
        profile = self.requirement_agent.get_profile()
        risk_level = self.risk_agent.get_risk_level()

        user_summary = f"""
用户投资画像：
- 投资金额：{profile.get('investment_amount', '未指定')}元
- 投资期限：{profile.get('investment_period', '未指定')}
- 投资目标：{profile.get('investment_goal', '未指定')}
- 投资经验：{profile.get('experience', '未指定')}
- 风险等级：{risk_level}
"""

        try:
            messages = [
                {"role": "user", "content": f"""
当前推荐存在以下问题：
{feedback}

请根据以下信息重新生成推荐：
{user_summary}

可选基金池：
{fund_summary}

请严格按照 XML 格式输出，确保：
1. 配置比例总和为 100%
2. 每只基金都有具体的风险警告
3. 包含免责声明
4. 推荐与用户风险等级匹配
"""}
            ]

            response = self.llm.chat(
                messages=messages,
                system=self.fund_expert_agent.SYSTEM_PROMPT,
                max_tokens=3000,
                temperature=0.3
            )

            # 更新推荐
            self.fund_expert_agent.recommendation = response

            # 再次验证
            validation = self.critic_agent.validate(response, profile, risk_level)
            self.last_validation_result = validation

            if not validation.passed:
                return response + f"\n\n【验证警告】得分：{validation.score:.0f}/100\n请注意：{validation.feedback}"

            return response + f"\n\n【验证通过】得分：{validation.score:.0f}/100"

        except Exception as e:
            return f"【系统错误】重新生成失败：{str(e)}"

    async def _handle_recommendation_stage(self, user_input: str) -> str:
        """处理基金推荐阶段"""
        # 此阶段主要是回答用户的问题
        if not self.llm:
            return "【系统】LLM 客户端未初始化"

        # 准备上下文
        profile = self.requirement_agent.get_profile()
        risk_level = self.risk_agent.get_risk_level()

        context = f"""用户画像：{profile}
风险等级：{risk_level}
推荐基金：{self.fund_expert_agent.get_top_funds()}"""

        try:
            messages = self.conversation_history[-30:]  # 最近 30 条消息
            messages = [{"role": "user", "content": f"{context}\n\n{user_input}"}]

            response = self.llm.chat(
                messages=messages,
                system="你是基金投资顾问，请根据用户画像和推荐基金，回答用户的问题。",
                max_tokens=1000
            )
            return response
        except Exception as e:
            return f"【系统错误】{str(e)}"

    async def _handle_complete_stage(self, user_input: str) -> str:
        """处理完成阶段（用户重新开始）"""
        if "重新" in user_input or "再来一次" in user_input:
            self.reset()
            return "好的，我们重新开始。\n\n您好！我是您的基金投资顾问。请问您打算投资多少钱呢？"
        else:
            return "如果您需要重新评估，请说'重新开始'"

    def get_current_stage(self) -> str:
        """获取当前阶段"""
        return self.current_stage

    def is_complete(self) -> bool:
        """是否完成"""
        return self.current_stage == self.STAGE_COMPLETE

    def reset(self):
        """重置管理器"""
        self.current_stage = self.STAGE_REQUIREMENT
        self.conversation_history = []
        self.requirement_agent.reset()
        self.risk_agent.reset()
        self.fund_expert_agent.reset()

    def get_user_profile(self) -> Dict[str, Any]:
        """获取用户画像"""
        return self.requirement_agent.get_profile()

    def get_risk_level(self) -> str:
        """获取风险等级"""
        return self.risk_agent.get_risk_level()

    def get_recommendation(self) -> str:
        """获取推荐结果"""
        return self.fund_expert_agent.recommendation


# 测试用
if __name__ == "__main__":
    async def test():
        llm = ClaudeClient()
        manager = GroupChatManager(llm)

        print("Group Chat Manager 测试")
        print("输入 'exit' 退出\n")

        # 初始问候
        response = await manager.process("你好，我想买基金")
        print(f"Agent: {response}\n")

        while manager.get_current_stage() != GroupChatManager.STAGE_COMPLETE:
            user_input = input("你：")
            if user_input.lower() == "exit":
                break
            response = await manager.process(user_input)
            print(f"Agent: {response}\n")

    # asyncio.run(test())
