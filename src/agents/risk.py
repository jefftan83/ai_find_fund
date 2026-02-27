"""风险评估 Agent - 评估用户风险承受能力"""

from typing import Dict, Any, List
from src.utils.llm import ClaudeClient


class RiskAgent:
    """
    风险评估 Agent

    负责评估用户的风险承受能力，给出风险等级：
    - 保守型：不能接受本金损失
    - 稳健型：能承受小幅波动
    - 积极型：能承受较大波动，追求高收益
    """

    SYSTEM_PROMPT = """你是一位专业的基金投资风险评估专家。
你的任务是通过一系列问题，评估用户的风险承受能力。

请通过以下维度评估用户风险承受能力：
1. 对本金损失的容忍度：能否接受本金亏损？能接受多少？
2. 对波动的承受能力：基金净值波动多少会让你睡不着觉？
3. 投资经验：投资经验越丰富，通常风险承受能力越强
4. 收入稳定性：收入是否稳定？是否有应急资金？
5. 投资目的：是为了什么投资？（养老/子女教育/财富增值等）

风险评估流程：
1. 先问 2-3 个核心问题（本金损失容忍度、波动承受能力）
2. 根据回答判断是否需要追问
3. 给出风险等级评估：
   - 保守型：不能接受任何本金损失，推荐货币基金、纯债基金
   - 稳健型：能承受 5-10% 的波动，推荐债券基金、固收+、平衡混合基金
   - 积极型：能承受 10-20% 的波动，推荐偏股混合基金、指数基金
   - 激进型：能承受 20% 以上的波动，推荐行业主题基金、股票型基金

4. 评估完成后，输出"【风险评估完成】风险等级：XXX 型"

注意事项：
- 一次只问 1-2 个问题
- 用通俗易懂的语言
- 态度友好、专业
- 给用户合理的风险建议

请用中文回复。"""

    def __init__(self, llm_client: ClaudeClient = None):
        self.llm = llm_client
        self.conversation_history: List[Dict[str, str]] = []
        self.risk_level: str = ""  # 保守型/稳健型/积极型/激进型
        self.risk_score: int = 0  # 风险评分 1-100
        self.is_complete = False

    async def process(self, user_input: str) -> str:
        """
        处理用户输入，生成回复

        Args:
            user_input: 用户输入

        Returns:
            Agent 回复
        """
        if not self.llm:
            return "【系统】LLM 客户端未初始化"

        # 添加用户消息到历史
        self.conversation_history.append({"role": "user", "content": user_input})

        # 调用 LLM
        try:
            response = self.llm.chat(
                messages=self.conversation_history[-30:],  # 保留最近 30 轮对话
                system=self.SYSTEM_PROMPT,
                max_tokens=500
            )

            # 检查是否完成
            if "【风险评估完成】" in response:
                self.is_complete = True
                # 提取风险等级
                self._extract_risk_level(response)

            # 添加 AI 回复到历史
            self.conversation_history.append({"role": "assistant", "content": response})

            return response

        except Exception as e:
            return f"【系统错误】风险评估失败：{str(e)}"

    def _extract_risk_level(self, response: str):
        """从回复中提取风险等级"""
        if "保守型" in response:
            self.risk_level = "保守型"
            self.risk_score = 20
        elif "稳健型" in response:
            self.risk_level = "稳健型"
            self.risk_score = 50
        elif "积极型" in response:
            self.risk_level = "积极型"
            self.risk_score = 75
        elif "激进型" in response:
            self.risk_level = "激进型"
            self.risk_score = 90
        else:
            # 默认稳健型
            self.risk_level = "稳健型"
            self.risk_score = 50

    def get_risk_level(self) -> str:
        """获取风险等级"""
        return self.risk_level

    def get_risk_score(self) -> int:
        """获取风险评分"""
        return self.risk_score

    def get_recommended_fund_types(self) -> List[str]:
        """根据风险等级获取推荐的基金类型"""
        recommendations = {
            "保守型": ["货币基金", "短债基金", "同业存单指数基金"],
            "稳健型": ["中长债基金", "固收 + 基金", "一级债基", "平衡混合基金"],
            "积极型": ["偏股混合基金", "灵活配置混合基金", "指数增强基金"],
            "激进型": ["股票型基金", "行业主题基金", "指数基金", "QDII 基金"]
        }
        return recommendations.get(self.risk_level, ["稳健型"])

    def reset(self):
        """重置 Agent 状态"""
        self.conversation_history = []
        self.risk_level = ""
        self.risk_score = 0
        self.is_complete = False


# 测试用
if __name__ == "__main__":
    async def test():
        from src.utils.config import config
        llm = ClaudeClient()
        agent = RiskAgent(llm)

        print("风险评估 Agent 测试")
        print("输入 'exit' 退出\n")

        # 初始问候
        response = await agent.process("你好，帮我评估一下风险")
        print(f"Agent: {response}\n")

        while not agent.is_complete:
            user_input = input("你：")
            if user_input.lower() == "exit":
                break
            response = await agent.process(user_input)
            print(f"Agent: {response}\n")

        print(f"\n风险评估结果：{agent.get_risk_level()}")
        print(f"推荐基金类型：{agent.get_recommended_fund_types()}")
