"""聚宽 (JoinQuant) 数据源客户端"""

from typing import List, Dict, Any, Optional
from src.utils.config import config


class JoinQuantClient:
    """聚宽基金数据客户端"""

    def __init__(self):
        self._jq = None
        self._username = config.jq_username
        self._password = config.jq_password

    def _get_client(self):
        """获取聚宽客户端"""
        if self._jq is None:
            if not self._username or not self._password:
                raise ValueError("聚宽账号密码未配置")
            from jqdatasdk import auth, get_fund_nav, get_price
            self._jq = {
                "auth": auth,
                "get_fund_nav": get_fund_nav,
                "get_price": get_price
            }
            self._jq["auth"](self._username, self._password)
        return self._jq

    async def get_fund_nav(self, fund_code: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """
        获取基金净值

        Args:
            fund_code: 基金代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            基金净值列表
        """
        try:
            jq = self._get_client()
            df = jq["get_fund_nav"](fund_code, start=start_date, end=end_date)

            result = []
            for _, row in df.iterrows():
                result.append({
                    "nav_date": str(row.get("date", ""))[:10] if row.get("date") else "",
                    "unit_nav": float(row.get("unit_nav", 0) or 0),
                    "accumulated_nav": float(row.get("accumulated_nav", 0) or 0),
                    "daily_growth": float(row.get("daily_growth", 0) or 0)
                })
            return result
        except Exception as e:
            raise Exception(f"聚宽获取基金净值失败：{str(e)}")

    async def get_fund_ranking(self, fund_type: str = None, order_by: str = "return_1y") -> List[Dict[str, Any]]:
        """
        获取基金排行

        Args:
            fund_type: 基金类型
            order_by: 排序字段

        Returns:
            基金排行列表
        """
        try:
            jq = self._get_client()
            from jqdatasdk import get_fund_rank

            df = get_fund_rank(order_by=order_by)
            result = []
            for _, row in df.iterrows():
                result.append({
                    "fund_code": str(row.get("code", "")),
                    "fund_name": str(row.get("name", "")),
                    "rank": int(row.get("rank", 0) or 0),
                    "return_1m": float(row.get("return_1m", 0) or 0),
                    "return_3m": float(row.get("return_3m", 0) or 0),
                    "return_6m": float(row.get("return_6m", 0) or 0),
                    "return_1y": float(row.get("return_1y", 0) or 0),
                    "return_3y": float(row.get("return_3y", 0) or 0)
                })
            return result
        except Exception as e:
            raise Exception(f"聚宽获取基金排行失败：{str(e)}")


# 全局客户端实例
jq_client = JoinQuantClient()
