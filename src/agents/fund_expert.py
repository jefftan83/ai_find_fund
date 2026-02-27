"""基金专家 Agent - 根据用户需求和风险等级推荐基金"""

import asyncio
import sqlite3
from typing import Dict, Any, List
from src.utils.llm import ClaudeClient
from src.services.fund_data import fund_data_service
from src.cache.db import cache_db


class FundExpertAgent:
    """
    基金专家 Agent

    负责根据用户画像和风险等级，筛选和推荐合适的基金组合：
    - 调用数据服务获取基金数据
    - 根据条件筛选基金
    - 生成配置建议
    """

    SYSTEM_PROMPT = """你是一位持牌基金投资分析师，擅长基于多维度数据生成个性化基金推荐。

## 任务背景
根据用户画像和候选基金池，推荐 3-5 只最适合的基金，并给出详细的配置建议。

## 分析框架（必须按步骤思考）

### 步骤 1：用户情况综合分析
- 投资金额决定单次配置的最小单位（如 10 万以下避免过度分散）
- 投资期限决定流动性要求（短期避免高波动，长期可承受波动换取收益）
- 投资目标决定风险偏好（保值/稳健/进取）
- 投资经验决定解释深度（新手需要更多教育性说明）
- 风险等级决定资产配置上限

### 步骤 2：基金筛选与排序
对每只候选基金进行多维度评分（1-5 分）：
1. 业绩稳定性：近 1 年、近 3 年收益是否一致性好
2. 风险控制：最大回撤、波动率是否在可接受范围
3. 规模适宜性：2 亿 < 规模 < 100 亿为最佳
4. 评级背书：是否有 3 星以上评级
5. 经理稳定性：经理任职时长是否超过 3 年

### 步骤 3：配置比例计算
根据用户风险等级和投资期限，动态计算配置比例：
- 保守型：债券基金 70-90%
- 稳健型：混合基金 40-60% + 债券基金 30-50%
- 积极型：偏股混合 50-70% + 债券 20-40%
- 激进型：股票型 60-80% + 偏股混合 20-40%

### 步骤 4：风险披露生成
针对每只推荐基金，明确指出：
- 最大可能回撤幅度
- 最坏情景下的损失
- 流动性风险（如有）

## 输出格式（必须严格遵守）

<analysis>
用户综合分析：[投资金额、期限、目标、经验、风险等级的综合影响分析]
</analysis>

<fund_evaluation>
| 基金代码 | 综合评分 | 优势 | 劣势 | 适配度 |
|---------|---------|------|------|-------|
| 000001  | 4.2     | 业绩稳定，规模适中 | 经理任职短 | 高    |
...
</fund_evaluation>

<recommendation>
<fund>
  <code>000001</code>
  <name>华夏成长混合</name>
  <allocation>30%</allocation>
  <rationale>[推荐理由，必须引用具体数据支撑]</rationale>
  <risk_warning>[具体风险，如"近 3 年最大回撤 -25%"]</risk_warning>
  <confidence>high/medium/low</confidence>
</fund>
...
</recommendation>

<disclaimer>
本推荐基于历史数据分析，不构成投资建议。投资有风险，入市需谨慎。
</disclaimer>
"""

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
        """筛选基金（根据风险等级动态筛选）"""
        # 获取基金排行
        fund_type_map = {
            "保守型": "债券型",
            "稳健型": "混合型",
            "积极型": "混合型",
            "激进型": "股票型"
        }

        target_type = fund_type_map.get(self.risk_level, "混合型")

        # 风险阈值配置
        risk_thresholds = {
            "保守型": {"max_drawdown": 5, "volatility": 3, "min_rating": 3},
            "稳健型": {"max_drawdown": 10, "volatility": 8, "min_rating": 3},
            "积极型": {"max_drawdown": 20, "volatility": 15, "min_rating": 2},
            "激进型": {"max_drawdown": 50, "volatility": 30, "min_rating": 0}
        }

        thresholds = risk_thresholds.get(self.risk_level, {"max_drawdown": 15, "volatility": 20, "min_rating": 2})

        try:
            # 获取排行数据
            ranking = await fund_data_service.get_fund_ranking(target_type)

            # 获取风险指标缓存
            fund_codes = [f.get('fund_code') for f in ranking[:100]]
            performance_cache = self._get_performance_cache(fund_codes)
            rating_cache = self._get_rating_cache(fund_codes)
            size_cache = self._get_size_cache(fund_codes)

            # 筛选
            screened = []
            for fund in ranking:
                code = fund.get('fund_code')

                # 基本筛选：近 1 年收益为正
                if fund.get("return_1y", 0) <= 0:
                    continue

                # 获取风险指标
                perf = performance_cache.get(code, {})
                max_dd = perf.get('max_drawdown', 100)
                volatility = perf.get('volatility', 50)

                # 获取评级
                rating = rating_cache.get(code, {})
                rating_3y = rating.get('rating_3y') or rating.get('rating_2y') or rating.get('rating_1y') or 0

                # 获取规模
                size = size_cache.get(code, {})
                net_asset_size = size.get('net_asset_size', '')

                # 解析规模（处理 "10.5 亿" 格式）
                size_value = 0
                if '亿' in net_asset_size:
                    try:
                        size_value = float(net_asset_size.replace('亿', ''))
                    except:
                        size_value = 0

                # 风险指标筛选
                if max_dd > thresholds["max_drawdown"]:
                    continue
                if volatility > thresholds["volatility"]:
                    continue

                # 评级筛选（保守型和稳健型要求 3 星以上）
                if rating_3y < thresholds["min_rating"]:
                    continue

                # 规模筛选（避免规模过小<2 亿或过大>500 亿）
                if size_value > 0 and (size_value < 2 or size_value > 500):
                    continue

                screened.append(fund)

            # 按近 1 年收益排序，取前 50 只
            screened.sort(key=lambda x: x.get("return_1y", 0), reverse=True)
            self.screened_funds = screened[:50]

            # 异步补充规模数据
            asyncio.create_task(self._preload_size_data())

        except Exception as e:
            print(f"筛选基金失败：{e}")
            self.screened_funds = []

    async def _preload_size_data(self):
        """预加载规模数据到缓存"""
        from src.services.akshare_client import akshare_client

        fund_codes = [f.get('fund_code') for f in self.screened_funds]

        for code in fund_codes:
            try:
                # 检查缓存是否有数据
                basic = cache_db.get_fund_basic(code)
                if basic and basic.get('net_asset_size'):
                    continue  # 已有数据，跳过

                # 获取规模
                size_info = await akshare_client.get_fund_size(code)
                if size_info:
                    # 更新缓存
                    cache_db.save_fund_basic(code, {
                        "fund_code": code,
                        "net_asset_size": size_info.get("net_asset_size"),
                        "share_size": size_info.get("share_size")
                    })
            except Exception as e:
                pass  # 静默失败，不影响主流程

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

可选基金池（包含规模、评级、经理、公司、风险指标等维度）：
{fund_summary}

请根据用户情况，推荐 3-5 只基金，并给出配置建议。
按以下步骤思考：
1. 先分析用户情况（投资金额、期限、目标、经验、风险等级）
2. 对候选基金进行多维度评分
3. 计算配置比例
4. 生成风险披露

请严格按照 XML 格式输出。
"""}
            ]

            response = self.llm.chat(
                messages=messages,
                system=self.SYSTEM_PROMPT,
                max_tokens=3000,  # 增加到 3000 以容纳完整推理
                temperature=0.3   # 降低到 0.3 减少随机性
            )

            self.recommendation = response
            return response

        except Exception as e:
            return f"【系统错误】生成推荐失败：{str(e)}"

    def _prepare_fund_summary(self) -> str:
        """准备基金数据摘要（增强版 - 13+ 数据维度）"""
        lines = []

        # 批量获取各类数据
        fund_codes = [f.get('fund_code') for f in self.screened_funds[:30]]
        size_cache = self._get_size_cache(fund_codes)
        rating_cache = self._get_rating_cache(fund_codes)
        basic_cache = self._get_basic_cache(fund_codes)
        performance_cache = self._get_performance_cache(fund_codes)
        holdings_cache = self._get_holdings_concentration(fund_codes)

        # 展示前 30 只基金给 LLM（增强数据维度）
        for i, fund in enumerate(self.screened_funds[:30], 1):
            code = fund.get('fund_code')
            size_info = size_cache.get(code, {})
            rating_info = rating_cache.get(code, {})
            basic_info = basic_cache.get(code, {})
            perf_info = performance_cache.get(code, {})
            holding_concentration = holdings_cache.get(code, 'N/A')

            # 获取评级（取三年评级，若无则取二年，再无取一年）
            rating = rating_info.get('rating_3y') or rating_info.get('rating_2y') or rating_info.get('rating_1y') or '无'

            lines.append(f"""
{i}. {code} - {fund.get('fund_name')}
   规模：{size_info.get('net_asset_size', 'N/A')} | 评级：{rating}星
   经理：{basic_info.get('manager', 'N/A')} | 公司：{basic_info.get('company', 'N/A')}
   近 1 月：{fund.get('return_1m', 0):.2f}% | 近 3 月：{fund.get('return_3m', 0):.2f}%
   近 6 月：{fund.get('return_6m', 0):.2f}% | 近 1 年：{fund.get('return_1y', 0):.2f}%
   近 3 年：{fund.get('return_3y', 0):.2f}% | 今年来：{fund.get('return_ytd', 0):.2f}%
   最大回撤：{perf_info.get('max_drawdown', 'N/A')}% | 波动率：{perf_info.get('volatility', 'N/A')}%
   持仓集中度：{holding_concentration}%
""")
        return "\n".join(lines)

    def _get_size_cache(self, fund_codes: List[str]) -> Dict[str, Dict[str, str]]:
        """
        从缓存获取基金规模数据

        Args:
            fund_codes: 基金代码列表

        Returns:
            规模数据缓存
        """
        cache = {}
        try:
            conn = cache_db._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fund_code, net_asset_size, share_size
                FROM fund_basic
                WHERE fund_code IN ({})
            """.format(','.join('?' * len(fund_codes))), fund_codes)

            for row in cursor.fetchall():
                cache[row['fund_code']] = {
                    'net_asset_size': row['net_asset_size'] or 'N/A',
                    'share_size': row['share_size'] or 'N/A'
                }
            conn.close()
        except Exception as e:
            print(f"获取规模缓存失败：{e}")

        return cache

    def _get_rating_cache(self, fund_codes: List[str]) -> Dict[str, Dict[str, int]]:
        """
        从缓存获取基金评级数据

        Args:
            fund_codes: 基金代码列表

        Returns:
            评级数据缓存 {fund_code: {rating_1y, rating_2y, rating_3y}}
        """
        cache = {}
        try:
            conn = cache_db._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fund_code, rating_1y, rating_2y, rating_3y
                FROM fund_rating
                WHERE fund_code IN ({})
                ORDER BY rating_date DESC
            """.format(','.join('?' * len(fund_codes))), fund_codes)

            for row in cursor.fetchall():
                code = row['fund_code']
                if code not in cache:  # 只取最新评级
                    cache[code] = {
                        'rating_1y': row['rating_1y'],
                        'rating_2y': row['rating_2y'],
                        'rating_3y': row['rating_3y']
                    }
            conn.close()
        except Exception as e:
            print(f"获取评级缓存失败：{e}")

        return cache

    def _get_basic_cache(self, fund_codes: List[str]) -> Dict[str, Dict[str, str]]:
        """
        从缓存获取基金基本信息（经理、公司）

        Args:
            fund_codes: 基金代码列表

        Returns:
            基本信息缓存 {fund_code: {manager, company, established_date}}
        """
        cache = {}
        try:
            conn = cache_db._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fund_code, manager, company, established_date
                FROM fund_basic
                WHERE fund_code IN ({})
            """.format(','.join('?' * len(fund_codes))), fund_codes)

            for row in cursor.fetchall():
                cache[row['fund_code']] = {
                    'manager': row['manager'] or 'N/A',
                    'company': row['company'] or 'N/A',
                    'established_date': row['established_date'] or 'N/A'
                }
            conn.close()
        except Exception as e:
            print(f"获取基本信息缓存失败：{e}")

        return cache

    def _get_performance_cache(self, fund_codes: List[str]) -> Dict[str, Dict[str, float]]:
        """
        从缓存获取业绩指标（最大回撤、波动率）

        Args:
            fund_codes: 基金代码列表

        Returns:
            业绩指标缓存 {fund_code: {max_drawdown, volatility}}
        """
        cache = {}
        try:
            conn = cache_db._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            for code in fund_codes:
                # 获取历史净值数据
                cursor.execute("""
                    SELECT unit_nav FROM fund_nav
                    WHERE fund_code = ?
                    ORDER BY nav_date DESC
                    LIMIT 252  -- 取最近一年数据
                """, (code,))

                rows = cursor.fetchall()
                if len(rows) >= 2:
                    navs = [row['unit_nav'] for row in rows if row['unit_nav']]
                    if len(navs) >= 2:
                        # 计算最大回撤
                        max_dd = 0
                        peak = navs[0]
                        for nav in navs:
                            if nav > peak:
                                peak = nav
                            dd = (peak - nav) / peak
                            if dd > max_dd:
                                max_dd = dd

                        # 计算波动率
                        returns = [(navs[i] - navs[i-1]) / navs[i-1] for i in range(1, len(navs))]
                        if returns:
                            avg_return = sum(returns) / len(returns)
                            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
                            volatility = (variance ** 0.5) * (252 ** 0.5)

                            cache[code] = {
                                'max_drawdown': round(max_dd * 100, 2),
                                'volatility': round(volatility * 100, 2)
                            }

            conn.close()
        except Exception as e:
            print(f"获取业绩指标缓存失败：{e}")

        return cache

    def _get_holdings_concentration(self, fund_codes: List[str]) -> Dict[str, float]:
        """
        从缓存获取持仓集中度（前十大重仓股占比）

        Args:
            fund_codes: 基金代码列表

        Returns:
            持仓集中度缓存 {fund_code: concentration_ratio}
        """
        cache = {}
        try:
            conn = cache_db._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            for code in fund_codes:
                # 获取最新持仓（按报告日期排序）
                cursor.execute("""
                    SELECT holding_ratio FROM fund_holdings
                    WHERE fund_code = ?
                    ORDER BY report_date DESC
                    LIMIT 10
                """, (code,))

                rows = cursor.fetchall()
                if rows:
                    # 计算前十大重仓股总占比
                    total_ratio = sum(row['holding_ratio'] for row in rows if row['holding_ratio'])
                    cache[code] = round(total_ratio, 2)
                else:
                    cache[code] = 'N/A'

            conn.close()
        except Exception as e:
            print(f"获取持仓集中度缓存失败：{e}")

        return cache

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
