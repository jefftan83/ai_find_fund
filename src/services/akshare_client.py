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
                # 使用 iloc 按位置访问，避免中文字段名访问问题
                # 列顺序：0-基金代码，1-拼音缩写，2-基金简称，3-基金类型，4-拼音全称
                result.append({
                    "fund_code": str(row.iloc[0]),
                    "fund_name": str(row.iloc[2]),
                    "fund_type": str(row.iloc[3])
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
        import re
        try:
            df = ak.fund_open_fund_daily_em()
            result = []
            for _, row in df.iterrows():
                # 使用 iloc 按位置访问
                # 列顺序：0-基金代码，1-基金简称，2-当日单位净值，3-当日累计净值，4-上日单位净值，5-上日累计净值，6-日增长值，7-日增长率
                # 从列名解析日期（如：2026-02-25-单位净值）
                nav_date = ""
                col_name = str(df.columns[2])  # '2026-02-25-单位净值'
                match = re.match(r'(\d{4}-\d{2}-\d{2})-(.*)', col_name)
                if match:
                    nav_date = match.group(1)

                result.append({
                    "fund_code": str(row.iloc[0]),
                    "fund_name": str(row.iloc[1]),
                    "fund_type": "",  # 此接口不返回基金类型
                    "unit_nav": float(row.iloc[2] or 0),
                    "accumulated_nav": float(row.iloc[3] or 0),
                    "daily_growth": float(row.iloc[7] or 0),
                    "nav_date": nav_date
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
                # 使用 iloc 按位置访问
                # 列顺序：0-净值日期，1-单位净值，2-累计净值，3-日增长率
                result.append({
                    "nav_date": str(row.iloc[0]),
                    "unit_nav": float(row.iloc[1] or 0),
                    "accumulated_nav": float(row.iloc[2] or 0),
                    "daily_growth": float(row.iloc[3] or 0)
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
                import math
                # 处理 NaN 值
                return_3y = row.iloc[13]
                if isinstance(return_3y, float) and math.isnan(return_3y):
                    return_3y = 0  # 成立不足 3 年的基金，近 3 年收益设为 0

                result.append({
                    "fund_code": str(row.iloc[1]),
                    "fund_name": str(row.iloc[2]),
                    "rank": int(row.iloc[0] or 0),
                    "return_1m": float(row.iloc[8] or 0),
                    "return_3m": float(row.iloc[9] or 0),
                    "return_6m": float(row.iloc[10] or 0),
                    "return_1y": float(row.iloc[11] or 0),
                    "return_3y": float(return_3y),
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
                # 使用 iloc 按位置访问
                # 列顺序：0-序号，1-股票代码，2-股票名称，3-占净值比例，4-持股数，5-持仓市值，6-季度
                result.append({
                    "stock_code": str(row.iloc[1]),
                    "stock_name": str(row.iloc[2]),
                    "holding_ratio": float(row.iloc[3] or 0),
                    "holding_amount": int(row.iloc[4] or 0),
                    "holding_value": float(row.iloc[5] or 0),
                    "stock_type": ""  # 此接口不返回股票品种
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
            import math
            for _, row in df.iterrows():
                # 使用 iloc 按位置访问
                # 列顺序：0-代码，1-简称，2-基金经理，3-基金公司，4-5 星评级家数，5-上海证券，6-招商证券，7-济安金信，8-晨星评级
                # 处理 NaN 值
                rating_1y = row.iloc[5]
                rating_2y = row.iloc[6]
                rating_3y = row.iloc[7]

                result.append({
                    "fund_code": str(row.iloc[0]),
                    "fund_name": str(row.iloc[1]),
                    "rating_agency": "综合评级",
                    "rating_1y": 0 if (isinstance(rating_1y, float) and math.isnan(rating_1y)) else int(rating_1y or 0),
                    "rating_2y": 0 if (isinstance(rating_2y, float) and math.isnan(rating_2y)) else int(rating_2y or 0),
                    "rating_3y": 0 if (isinstance(rating_3y, float) and math.isnan(rating_3y)) else int(rating_3y or 0)
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
            # 使用 iloc 按位置访问
            # 列顺序：0-基金全称，1-基金简称，2-基金代码，3-基金类型，4-发行日期，5-成立日期/规模，6-净资产规模，7-份额规模，8-基金管理人，9-基金托管人，10-基金经理人
            return {
                "fund_code": fund_code,
                "fund_name": str(row.iloc[1]),
                "fund_type": str(row.iloc[3]),
                "company": str(row.iloc[8]),  # 基金管理人
                "manager": str(row.iloc[10]),  # 基金经理人
                "established_date": str(row.iloc[5]).split(' / ')[0] if row.iloc[5] else "",  # 成立日期
                "net_asset_size": str(row.iloc[6]) if row.iloc[6] else "",  # 净资产规模
                "share_size": str(row.iloc[7]) if row.iloc[7] else ""  # 份额规模
            }
        except Exception as e:
            raise Exception(f"AKShare 获取基金基本信息失败：{str(e)}")

    async def get_fund_size(self, fund_code: str) -> Dict[str, str]:
        """
        获取基金规模（净资产和份额）

        Args:
            fund_code: 基金代码

        Returns:
            规模信息：net_asset_size, share_size
        """
        ak = self._get_akshare()
        try:
            df = ak.fund_overview_em(symbol=fund_code)
            if df.empty:
                return {}

            row = df.iloc[0]
            return {
                "net_asset_size": str(row.iloc[6]) if row.iloc[6] else "",  # 净资产规模
                "share_size": str(row.iloc[7]) if row.iloc[7] else ""  # 份额规模
            }
        except Exception as e:
            print(f"AKShare 获取基金规模失败：{str(e)}")
            return {}


# 全局客户端实例
akshare_client = AKShareClient()
