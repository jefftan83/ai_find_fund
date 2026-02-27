"""Critic Agent - 验证器 Agent，检查推荐的合理性和合规性"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    feedback: List[str]
    score: float  # 0-100 分


class CriticAgent:
    """
    验证器 Agent

    负责检查 FundExpertAgent 的推荐结果：
    1. 配置比例总和是否为 100%
    2. 推荐是否符合用户风险等级
    3. 是否包含必要的风险披露
    4. 数据引用是否一致
    5. XML 格式是否正确
    """

    # 风险等级对应的预期配置
    RISK_CONFIG = {
        "保守型": {
            "min_bond_ratio": 70,
            "max_stock_ratio": 10,
            "allowed_types": ["债券型", "货币型", "固收+"]
        },
        "稳健型": {
            "min_bond_ratio": 30,
            "max_stock_ratio": 40,
            "allowed_types": ["债券型", "混合型", "固收+", "指数型"]
        },
        "积极型": {
            "min_bond_ratio": 20,
            "max_stock_ratio": 60,
            "allowed_types": ["混合型", "股票型", "指数型", "债券型"]
        },
        "激进型": {
            "min_bond_ratio": 0,
            "max_stock_ratio": 80,
            "allowed_types": ["股票型", "混合型", "指数型", "行业型"]
        }
    }

    def __init__(self):
        self.validation_history: List[ValidationResult] = []

    def validate(self, recommendation: str, user_profile: Dict, risk_level: str) -> ValidationResult:
        """
        验证推荐结果

        Args:
            recommendation: 推荐内容（XML 格式）
            user_profile: 用户画像
            risk_level: 风险等级

        Returns:
            验证结果
        """
        feedback = []
        score = 100.0

        # 1. 验证 XML 格式
        xml_valid, xml_feedback = self._validate_xml_format(recommendation)
        feedback.extend(xml_feedback)
        if not xml_valid:
            score -= 20

        # 2. 验证配置比例总和
        allocation_valid, allocation_feedback = self._validate_allocation_sum(recommendation)
        feedback.extend(allocation_feedback)
        if not allocation_valid:
            score -= 25

        # 3. 验证风险披露
        disclosure_valid, disclosure_feedback = self._validate_risk_disclosure(recommendation)
        feedback.extend(disclosure_feedback)
        if not disclosure_valid:
            score -= 20

        # 4. 验证风险等级匹配
        risk_valid, risk_feedback = self._validate_risk_level_match(recommendation, risk_level)
        feedback.extend(risk_feedback)
        if not risk_valid:
            score -= 25

        # 5. 验证免责声明
        disclaimer_valid, disclaimer_feedback = self._validate_disclaimer(recommendation)
        feedback.extend(disclaimer_feedback)
        if not disclaimer_valid:
            score -= 10

        # 确保分数在 0-100 之间
        score = max(0, min(100, score))

        passed = score >= 60
        result = ValidationResult(passed=passed, feedback=feedback, score=score)
        self.validation_history.append(result)

        return result

    def _validate_xml_format(self, recommendation: str) -> tuple:
        """验证 XML 格式"""
        feedback = []

        # 检查必需的顶层标签
        required_tags = ["analysis", "fund_evaluation", "recommendation", "disclaimer"]
        for tag in required_tags:
            open_count = recommendation.count(f"<{tag}>")
            close_count = recommendation.count(f"</{tag}>")
            if open_count != close_count:
                feedback.append(f"XML 标签<{tag}>未正确闭合（开：{open_count}, 闭：{close_count}）")

        # 检查推荐基金标签
        fund_tags = ["code", "name", "allocation", "rationale", "risk_warning", "confidence"]
        for tag in fund_tags:
            if f"<{tag}>" not in recommendation:
                feedback.append(f"缺少必需标签<{tag}>")

        valid = len(feedback) == 0
        return valid, feedback

    def _validate_allocation_sum(self, recommendation: str) -> tuple:
        """验证配置比例总和"""
        feedback = []

        # 提取所有配置比例
        allocation_pattern = r"<allocation>(\d+(?:\.\d+)?)\s*%</allocation>"
        allocations = re.findall(allocation_pattern, recommendation)

        if not allocations:
            feedback.append("未找到配置比例数据")
            return False, feedback

        try:
            total = sum(float(a) for a in allocations)
            if abs(total - 100) > 1:  # 允许 1% 的误差
                feedback.append(f"配置比例总和为{total:.1f}%，应为 100%")
                return False, feedback
        except Exception as e:
            feedback.append(f"解析配置比例失败：{e}")
            return False, feedback

        return True, feedback

    def _validate_risk_disclosure(self, recommendation: str) -> tuple:
        """验证风险披露"""
        feedback = []

        # 检查是否有风险警告标签
        risk_warning_pattern = r"<risk_warning>(.*?)</risk_warning>"
        risk_warnings = re.findall(risk_warning_pattern, recommendation, re.DOTALL)

        if not risk_warnings:
            feedback.append("缺少风险警告")
            return False, feedback

        # 检查每个推荐基金是否有风险警告
        fund_pattern = r"<fund>(.*?)</fund>"
        funds = re.findall(fund_pattern, recommendation, re.DOTALL)

        for i, fund in enumerate(funds):
            if "<risk_warning>" not in fund:
                feedback.append(f"第{i+1}只基金缺少风险警告")

        # 检查风险警告是否具体（包含数字或具体描述）
        for warning in risk_warnings:
            if len(warning.strip()) < 5:
                feedback.append("风险警告过于简单，需要具体描述")

        valid = len(feedback) == 0
        return valid, feedback

    def _validate_risk_level_match(self, recommendation: str, risk_level: str) -> tuple:
        """验证推荐与风险等级匹配"""
        feedback = []

        # 获取该风险等级的预期配置
        expected_config = self.RISK_CONFIG.get(risk_level)
        if not expected_config:
            feedback.append(f"未知风险等级：{risk_level}")
            return True, feedback  # 不阻断

        # 检查推荐中是否包含明显不匹配的基金类型
        # 保守型不应推荐股票型基金
        if risk_level == "保守型":
            forbidden_keywords = ["股票型", "行业主题", "创业板", "科创板"]
            for keyword in forbidden_keywords:
                if keyword in recommendation:
                    feedback.append(f"保守型推荐中包含不适宜的基金类型：{keyword}")

        # 激进型应有较高比例的股票型/混合型
        if risk_level == "激进型":
            # 简单检查是否有股票相关关键词
            stock_keywords = ["股票", "混合", "指数"]
            has_stock = any(kw in recommendation for kw in stock_keywords)
            if not has_stock:
                feedback.append("激进型推荐应包含股票型或混合型基金")

        valid = len(feedback) == 0
        return valid, feedback

    def _validate_disclaimer(self, recommendation: str) -> tuple:
        """验证免责声明"""
        feedback = []

        # 检查是否有免责声明标签
        if "<disclaimer>" not in recommendation or "</disclaimer>" not in recommendation:
            feedback.append("缺少免责声明")
            return False, feedback

        # 提取免责声明内容
        disclaimer_pattern = r"<disclaimer>(.*?)</disclaimer>"
        match = re.search(disclaimer_pattern, recommendation, re.DOTALL)

        if match:
            disclaimer = match.group(1).strip()
            if len(disclaimer) < 10:
                feedback.append("免责声明过于简单")
        else:
            feedback.append("免责声明格式不正确")

        valid = len(feedback) == 0
        return valid, feedback

    def generate_improvement_suggestions(self, result: ValidationResult) -> str:
        """生成改进建议"""
        if result.passed:
            return f"验证通过！得分：{result.score:.0f}/100"

        suggestions = ["需要改进以下方面：\n"]
        for i, issue in enumerate(result.feedback, 1):
            suggestions.append(f"{i}. {issue}")

        return "\n".join(suggestions)

    def get_validation_stats(self) -> Dict[str, Any]:
        """获取验证统计"""
        if not self.validation_history:
            return {"total": 0, "passed": 0, "average_score": 0}

        total = len(self.validation_history)
        passed = sum(1 for r in self.validation_history if r.passed)
        avg_score = sum(r.score for r in self.validation_history) / total

        return {
            "total": total,
            "passed": passed,
            "pass_rate": passed / total * 100,
            "average_score": avg_score
        }


# 测试用
if __name__ == "__main__":
    critic = CriticAgent()

    # 测试用例 1：有效的推荐
    valid_recommendation = """
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
<fund>
  <code>000002</code>
  <name>南方价值混合</name>
  <allocation>70%</allocation>
  <rationale>长期业绩优秀</rationale>
  <risk_warning>波动率较高，达 12%</risk_warning>
  <confidence>medium</confidence>
</fund>
</recommendation>

<disclaimer>
本推荐基于历史数据分析，不构成投资建议。投资有风险，入市需谨慎。
</disclaimer>
"""

    result = critic.validate(
        valid_recommendation,
        {"investment_amount": 100000, "investment_period": "长期"},
        "稳健型"
    )

    print("测试 1 - 有效的推荐：")
    print(f"通过：{result.passed}")
    print(f"得分：{result.score}")
    print(f"反馈：{result.feedback}")
    print()

    # 测试用例 2：配置比例错误
    invalid_allocation = """
<recommendation>
<fund>
  <code>000001</code>
  <name>华夏成长混合</name>
  <allocation>50%</allocation>
  <rationale>业绩稳定</rationale>
  <risk_warning>最大回撤 -15%</risk_warning>
  <confidence>high</confidence>
</fund>
<fund>
  <code>000002</code>
  <name>南方价值混合</name>
  <allocation>40%</allocation>
  <rationale>长期优秀</rationale>
  <risk_warning>波动率高</risk_warning>
  <confidence>medium</confidence>
</fund>
</recommendation>
"""

    result = critic.validate(invalid_allocation, {}, "稳健型")
    print("测试 2 - 配置比例错误（总和 90%）：")
    print(f"通过：{result.passed}")
    print(f"得分：{result.score}")
    print(f"反馈：{result.feedback}")
    print()

    # 测试用例 3：缺少风险披露
    no_risk_warning = """
<recommendation>
<fund>
  <code>000001</code>
  <name>华夏成长混合</name>
  <allocation>100%</allocation>
  <rationale>业绩稳定</rationale>
  <confidence>high</confidence>
</fund>
</recommendation>
"""

    result = critic.validate(no_risk_warning, {}, "稳健型")
    print("测试 3 - 缺少风险披露：")
    print(f"通过：{result.passed}")
    print(f"得分：{result.score}")
    print(f"反馈：{result.feedback}")
