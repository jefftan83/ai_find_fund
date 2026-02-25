"""Tushare 数据源客户端"""

import os
from typing import List, Dict, Any, Optional
from src.utils.config import config


class TushareClient:
    """Tushare 基金数据客户端"""

    def __init__(self):
        self._ts = None
        self._pro = None
        self._token = config.tushare_token

    def _get_pro(self):
        """获取 Tushare Pro 客户端"""
        if self._pro is None:
            if not self._token:
                raise ValueError("Tushare Token 未配置")
            import tushare as ts
            self._ts = ts
            ts.set_token(self._token)
            self._pro = ts.pro_api()
        return self._pro

    async def get_fund_basic(self, fund_code: str = None) -> List[Dict[str, Any]]:
        """
        获取基金基本信息

        Args:
            fund_code: 基金代码，可选

        Returns:
            基金基本信息列表
        """
        try:
            pro = self._get_pro()
            df = pro.fund_basic(ts_code=fund_code) if fund_code else pro.fund_basic()

            result = []
            for _, row in df.iterrows():
                result.append({
                    "fund_code": str(row.get("ts_code", "")).split(".")[0] if row.get("ts_code") else "",
                    "fund_name": str(row.get("name", "")),
                    "fund_type": str(row.get("category", "")),
                    "company": str(row.get("mngmt_comp", "")),
                    "manager": str(row.get("manager", "")),
                    "established_date": str(row.get("found_date", "")),
                    "total_share": float(row.get("total_share", 0) or 0),
                    "net_asset": float(row.get("net_asset", 0) or 0)
                })
            return result
        except Exception as e:
            raise Exception(f"Tushare 获取基金基本信息失败：{str(e)}")

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
            pro = self._get_pro()
            ts_code = f"{fund_code}.OF"
            df = pro.fund_nav(ts_code=ts_code, start_date=start_date, end_date=end_date)

            result = []
            for _, row in df.iterrows():
                result.append({
                    "nav_date": str(row.get("ann_date", "")),
                    "unit_nav": float(row.get("unit_nav", 0) or 0),
                    "accumulated_nav": float(row.get("accum_nav", 0) or 0),
                    "daily_growth": float(row.get("nav_chg", 0) or 0)
                })
            return result
        except Exception as e:
            raise Exception(f"Tushare 获取基金净值失败：{str(e)}")

    async def get_fund_portfolio(self, fund_code: str, report_date: str = None) -> List[Dict[str, Any]]:
        """
        获取基金持仓

        Args:
            fund_code: 基金代码
            report_date: 报告日期

        Returns:
            基金持仓列表
        """
        try:
            pro = self._get_pro()
            ts_code = f"{fund_code}.OF"
            df = pro.fund_portfolio(ts_code=ts_code, ann_date=report_date)

            result = []
            for _, row in df.iterrows():
                result.append({
                    "stock_code": str(row.get("ts_code", "")).split(".")[0] if row.get("ts_code") else "",
                    "stock_name": str(row.get("name", "")),
                    "holding_ratio": float(row.get("weight", 0) or 0),
                    "holding_amount": int(row.get("amount", 0) or 0),
                    "holding_value": float(row.get("mkv", 0) or 0),
                    "stock_type": "股票"
                })
            return result
        except Exception as e:
            raise Exception(f"Tushare 获取基金持仓失败：{str(e)}")

    async def get_fund_rating(self) -> List[Dict[str, Any]]:
        """
        获取基金评级

        Returns:
            评级列表
        """
        try:
            pro = self._get_pro()
            df = pro.fund_rating()

            result = []
            for _, row in df.iterrows():
                result.append({
                    "fund_code": str(row.get("ts_code", "")).split(".")[0] if row.get("ts_code") else "",
                    "fund_name": str(row.get("name", "")),
                    "rating_agency": "上海证券",
                    "rating_1y": int(row.get("rating_1y", 0) or 0),
                    "rating_2y": int(row.get("rating_2y", 0) or 0),
                    "rating_3y": int(row.get("rating_3y", 0) or 0)
                })
            return result
        except Exception as e:
            raise Exception(f"Tushare 获取基金评级失败：{str(e)}")


# 全局客户端实例
tushare_client = TushareClient()
