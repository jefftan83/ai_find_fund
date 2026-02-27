"""需求分析 Agent - 收集用户投资需求"""

from typing import Dict, Any, List
from src.utils.llm import ClaudeClient


class RequirementAgent:
    """
    需求分析 Agent

    负责通过对话收集用户的投资需求：
    - 投资金额
    - 投资期限（短期/中期/长期）
    - 投资目标（保值/稳健增长/高收益）
    - 投资经验
    - 其他偏好
    """

    SYSTEM_PROMPT = """你是一位专业的基金投资顾问助手的需求分析专家。
你的任务是通过友好、专业的对话，了解用户的投资需求和偏好。

请收集以下信息：
1. 投资金额：用户打算投资多少钱？
2. 投资期限：短期（1 年内）、中期（1-3 年）、还是长期（3 年以上）？
3. 投资目标：保值为主、稳健增长、还是追求高收益？
4. 投资经验：是否有基金投资经验？经验如何？
5. 其他偏好：是否有偏好的基金类型？是否有需要避开的行业？

注意事项：
- 一次只问 1-2 个问题，不要一次性问太多
- 用通俗易懂的语言，避免专业术语
- 态度友好、专业
- 当用户回答后，给予适当的回应再问下一个问题
- 当收集完所有信息后，输出"【需求收集完成】"并总结用户画像

请用中文回复。"""

    def __init__(self, llm_client: ClaudeClient = None):
        self.llm = llm_client
        self.conversation_history: List[Dict[str, str]] = []
        self.user_profile: Dict[str, Any] = {}
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
            if "【需求收集完成】" in response:
                self.is_complete = True
                # 提取用户画像
                self._extract_profile(response)

            # 添加 AI 回复到历史
            self.conversation_history.append({"role": "assistant", "content": response})

            return response

        except Exception as e:
            return f"【系统错误】需求分析失败：{str(e)}"

    def _extract_profile(self, response: str):
        """从对话中提取用户画像"""
        # 简单关键词提取，实际应用中可以用更复杂的 NLP
        text = response.lower()

        # 投资金额
        if "万" in response:
            import re
            amounts = re.findall(r'(\d+(?:\.\d+)?)\s*万', response)
            if amounts:
                self.user_profile["investment_amount"] = float(amounts[-1]) * 10000

        # 投资期限
        if any(kw in text for kw in ["短期", "1 年以内", "几个月"]):
            self.user_profile["investment_period"] = "短期"
        elif any(kw in text for kw in ["中期", "1-3 年", "一两年"]):
            self.user_profile["investment_period"] = "中期"
        elif any(kw in text for kw in ["长期", "3 年以上", "三年以上", "五年"]):
            self.user_profile["investment_period"] = "长期"

        # 投资目标
        if any(kw in text for kw in ["保值", "稳健", "风险小"]):
            self.user_profile["investment_goal"] = "稳健"
        elif any(kw in text for kw in ["高收益", "激进", "风险大"]):
            self.user_profile["investment_goal"] = "进取"
        else:
            self.user_profile["investment_goal"] = "稳健"

        # 投资经验
        if any(kw in text for kw in ["没有经验", "第一次", "新手"]):
            self.user_profile["experience"] = "新手"
        elif any(kw in text for kw in ["有一些经验", "买过"]):
            self.user_profile["experience"] = "有经验"
        elif any(kw in text for kw in ["经验丰富", "老手", "多年"]):
            self.user_profile["experience"] = "资深"

    def get_profile(self) -> Dict[str, Any]:
        """获取用户画像"""
        return self.user_profile

    def reset(self):
        """重置 Agent 状态"""
        self.conversation_history = []
        self.user_profile = {}
        self.is_complete = False


# 测试用
if __name__ == "__main__":
    async def test():
        from src.utils.config import config
        llm = ClaudeClient()
        agent = RequirementAgent(llm)

        print("需求分析 Agent 测试")
        print("输入 'exit' 退出\n")

        # 初始问候
        response = await agent.process("你好，我想买基金")
        print(f"Agent: {response}\n")

        while not agent.is_complete:
            user_input = input("你：")
            if user_input.lower() == "exit":
                break
            response = await agent.process(user_input)
            print(f"Agent: {response}\n")

        print(f"\n用户画像：{agent.get_profile()}")
