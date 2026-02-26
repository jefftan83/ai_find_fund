"""AKShare 数据源客户端"""

import asyncio
from typing import List, Dict, Any, Optional
from src.cache.db import cache_db


class AKShareClient:
    """AKShare 基金数据客户端"""

    def __init__(self):
        self._akshare = None

    def _get_akshare(self):
        """延迟导入 akshare"""
        if self._akshare is None:
            import akshare as ak
            self._akshare = ak
        return self._akshare

    async def get_fund_list(self) -> List[Dict[str, Any]]:
        """
        获取所有基金列表

        Returns:
            基金列表，每项包含：fund_code, fund_name, fund_type
        """
        ak = self._get_akshare()
        try:
            # 获取开放式基金列表
            df = ak.fund_name_em()
            result = []
            for _, row in df.iterrows():
                result.append({
                    "fund_code": str(row.get("基金代码", "")),
                    "fund_name": str(row.get("基金名称", "")),
                    "fund_type": str(row.get("基金类型", ""))
                })
            return result
        except Exception as e:
            raise Exception(f"AKShare 获取基金列表失败：{str(e)}")

    async def get_daily_nav(self) -> List[Dict[str, Any]]:
        """
        获取所有开放式基金当日净值

        Returns:
            基金净值列表
        """
        ak = self._get_akshare()
        try:
            df = ak.fund_open_fund_daily_em()
            result = []
            for _, row in df.iterrows():
                result.append({
                    "fund_code": str(row.get("基金代码", "")),
                    "fund_name": str(row.get("基金名称", "")),
                    "fund_type": str(row.get("基金类型", "")),
                    "unit_nav": float(row.get("单位净值", 0) or 0),
                    "accumulated_nav": float(row.get("累计净值", 0) or 0),
                    "daily_growth": float(row.get("日增长率", 0) or 0),
                    "nav_date": str(row.get("净值日期", ""))
                })
            return result
        except Exception as e:
            raise Exception(f"AKShare 获取每日净值失败：{str(e)}")

    async def get_fund_history(self, fund_code: str) -> List[Dict[str, Any]]:
        """
        获取基金历史净值

        Args:
            fund_code: 基金代码

        Returns:
            历史净值列表
        """
        ak = self._get_akshare()
        try:
            df = ak.fund_open_fund_info_em(symbol=fund_code)
            result = []
            for _, row in df.iterrows():
                result.append({
                    "nav_date": str(row.get("净值日期", "")),
                    "unit_nav": float(row.get("单位净值", 0) or 0),
                    "accumulated_nav": float(row.get("累计净值", 0) or 0),
                    "daily_growth": float(row.get("日增长率", 0) or 0)
                })
            return result
        except Exception as e:
            raise Exception(f"AKShare 获取基金历史数据失败：{str(e)}")

    async def get_fund_ranking(self, fund_type: str = "全部") -> List[Dict[str, Any]]:
        """
        获取基金排行

        Args:
            fund_type: 基金类型（全部/股票型/混合型/债券型等）

        Returns:
            基金排行列表
        """
        ak = self._get_akshare()
        try:
            df = ak.fund_open_fund_rank_em(symbol=fund_type)
            result = []
            for _, row in df.iterrows():
                # 使用 iloc 按位置访问，避免中文字段名访问问题
                # 列顺序：0-序号，1-基金代码，2-基金简称，8-近 1 月，9-近 3 月，10-近 6 月，11-近 1 年，13-近 3 年，14-今年来
                result.append({
                    "fund_code": str(row.iloc[1]),
                    "fund_name": str(row.iloc[2]),
                    "rank": int(row.iloc[0] or 0),
                    "return_1m": float(row.iloc[8] or 0),
                    "return_3m": float(row.iloc[9] or 0),
                    "return_6m": float(row.iloc[10] or 0),
                    "return_1y": float(row.iloc[11] or 0),
                    "return_3y": float(row.iloc[13] or 0),
                    "return_ytd": float(row.iloc[14] or 0)
                })
            return result
        except Exception as e:
            raise Exception(f"AKShare 获取基金排行失败：{str(e)}")

    async def get_fund_holdings(self, fund_code: str) -> List[Dict[str, Any]]:
        """
        获取基金持仓

        Args:
            fund_code: 基金代码

        Returns:
            持仓列表
        """
        ak = self._get_akshare()
        try:
            df = ak.fund_portfolio_hold_em(symbol=fund_code)
            result = []
            for _, row in df.iterrows():
                result.append({
                    "stock_code": str(row.get("股票代码", "")),
                    "stock_name": str(row.get("股票名称", "")),
                    "holding_ratio": float(row.get("占净值比例", 0) or 0),
                    "holding_amount": int(row.get("持股数", 0) or 0),
                    "holding_value": float(row.get("持仓市值", 0) or 0),
                    "stock_type": str(row.get("股票品种", ""))
                })
            return result
        except Exception as e:
            raise Exception(f"AKShare 获取基金持仓失败：{str(e)}")

    async def get_fund_rating(self) -> List[Dict[str, Any]]:
        """
        获取基金评级

        Returns:
            评级列表
        """
        ak = self._get_akshare()
        try:
            df = ak.fund_rating_all()
            result = []
            for _, row in df.iterrows():
                result.append({
                    "fund_code": str(row.get("基金代码", "")),
                    "fund_name": str(row.get("基金名称", "")),
                    "rating_agency": "综合评级",
                    "rating_1y": int(row.get("近 1 年评级", 0) or 0),
                    "rating_2y": int(row.get("近 2 年评级", 0) or 0),
                    "rating_3y": int(row.get("近 3 年评级", 0) or 0)
                })
            return result
        except Exception as e:
            raise Exception(f"AKShare 获取基金评级失败：{str(e)}")

    async def get_fund_basic_info(self, fund_code: str) -> Dict[str, Any]:
        """
        获取基金基本信息

        Args:
            fund_code: 基金代码

        Returns:
            基金基本信息
        """
        ak = self._get_akshare()
        try:
            df = ak.fund_overview_em(symbol=fund_code)
            if df.empty:
                return {}

            row = df.iloc[0]
            return {
                "fund_code": fund_code,
                "fund_name": str(row.get("基金名称", "")),
                "fund_type": str(row.get("基金类型", "")),
                "company": str(row.get("基金公司", "")),
                "manager": str(row.get("基金经理", "")),
                "established_date": str(row.get("成立日期", ""))
            }
        except Exception as e:
            raise Exception(f"AKShare 获取基金基本信息失败：{str(e)}")


# 全局客户端实例
akshare_client = AKShareClient()
