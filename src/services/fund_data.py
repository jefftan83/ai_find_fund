"""基金数据服务（多源融合 + 缓存管理）"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.services.akshare_client import akshare_client
from src.services.sina_client import sina_client
from src.services.tushare_client import tushare_client
from src.services.jq_client import jq_client
from src.cache.db import cache_db
from src.utils.config import config


class FundDataService:
    """
    基金数据服务

    数据源降级策略：
    AKShare (主) → Tushare → 新浪财经 → 聚宽 → 本地缓存
    """

    def __init__(self):
        self.update_interval = config.data_update_interval

    # ========== 统一数据获取接口 ==========

    async def get_fund_list(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        获取基金列表

        Args:
            use_cache: 是否使用缓存

        Returns:
            基金列表
        """
        # 尝试从缓存获取
        if use_cache:
            last_update = cache_db.get_last_update_time("fund_list")
            if last_update and (datetime.now() - last_update).total_seconds() < self.update_interval * 3600:
                # 缓存有效，从数据库获取
                cursor = cache_db._get_connection()
                cursor.execute("SELECT fund_code, fund_name, fund_type FROM fund_basic")
                return [{"fund_code": row["fund_code"], "fund_name": row["fund_name"],
                        "fund_type": row["fund_type"]} for row in cursor.fetchall()]

        # 从 AKShare 获取
        try:
            fund_list = await akshare_client.get_fund_list()
            # 更新缓存
            for fund in fund_list:
                cache_db.save_fund_basic(fund["fund_code"], fund)
            cache_db.log_update("fund_list", "success", f"Updated {len(fund_list)} funds")
            return fund_list
        except Exception as e:
            print(f"AKShare 获取基金列表失败：{e}")

        # 降级：返回空列表或缓存数据
        return []

    async def get_daily_nav(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        获取当日净值

        Returns:
            净值列表
        """
        # 尝试从 AKShare 获取
        try:
            nav_list = await akshare_client.get_daily_nav()
            # 更新缓存
            for nav in nav_list:
                cache_db.save_fund_nav(nav["fund_code"], nav.get("nav_date", ""), nav)
            cache_db.log_update("daily_nav", "success", f"Updated {len(nav_list)} records")
            return nav_list
        except Exception as e:
            print(f"AKShare 获取每日净值失败：{e}")

        # 降级到新浪财经
        try:
            fund_list = await self.get_fund_list()
            # 批量获取（新浪支持批量）
            nav_list = await sina_client.get_fund_nav_batch([f["fund_code"] for f in fund_list[:100]])
            return nav_list
        except Exception as e:
            print(f"新浪财经获取净值失败：{e}")

        return []

    async def get_fund_nav(self, fund_code: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取单只基金最新净值

        Args:
            fund_code: 基金代码
            use_cache: 是否使用缓存

        Returns:
            净值数据
        """
        # 尝试从缓存获取最新净值
        if use_cache:
            latest = cache_db.get_latest_nav(fund_code)
            if latest:
                # 检查是否过期
                nav_date = latest.get("nav_date", "")
                if nav_date:
                    try:
                        nav_time = datetime.strptime(nav_date, "%Y-%m-%d")
                        if (datetime.now() - nav_time).days <= 1:
                            return latest
                    except:
                        return latest

        # 从 AKShare 获取历史数据
        try:
            history = await akshare_client.get_fund_history(fund_code)
            if history:
                # 保存到缓存
                for record in history:
                    cache_db.save_fund_nav(fund_code, record.get("nav_date", ""), record)
                return history[0]  # 返回最新的
        except Exception as e:
            print(f"AKShare 获取基金净值失败：{e}")

        # 降级到新浪财经
        try:
            nav = await sina_client.get_fund_nav(fund_code)
            if nav:
                cache_db.save_fund_nav(fund_code, nav.get("nav_date", ""), nav)
                return nav
        except Exception as e:
            print(f"新浪财经获取净值失败：{e}")

        # 返回缓存旧数据
        return cache_db.get_latest_nav(fund_code)

    async def get_fund_history(self, fund_code: str, days: int = 365) -> List[Dict[str, Any]]:
        """
        获取基金历史净值

        Args:
            fund_code: 基金代码
            days: 天数

        Returns:
            历史净值列表
        """
        # 从缓存获取
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        history = cache_db.get_fund_nav(fund_code, start_date=start_date)

        if history:
            return history

        # 从 AKShare 获取
        try:
            history = await akshare_client.get_fund_history(fund_code)
            for record in history:
                cache_db.save_fund_nav(fund_code, record.get("nav_date", ""), record)
            return history
        except Exception as e:
            print(f"获取历史数据失败：{e}")

        return []

    async def get_fund_basic_info(self, fund_code: str) -> Optional[Dict[str, Any]]:
        """
        获取基金基本信息

        Args:
            fund_code: 基金代码

        Returns:
            基本信息
        """
        # 从缓存获取
        basic = cache_db.get_fund_basic(fund_code)
        if basic:
            return basic

        # 从 AKShare 获取
        try:
            info = await akshare_client.get_fund_basic_info(fund_code)
            if info:
                cache_db.save_fund_basic(fund_code, info)
                return info
        except Exception as e:
            print(f"获取基金基本信息失败：{e}")

        return None

    async def get_fund_holdings(self, fund_code: str) -> List[Dict[str, Any]]:
        """
        获取基金持仓

        Args:
            fund_code: 基金代码

        Returns:
            持仓列表
        """
        # 从缓存获取
        holdings = cache_db.get_latest_holdings(fund_code)
        if holdings:
            return holdings

        # 从 AKShare 获取
        try:
            holdings = await akshare_client.get_fund_holdings(fund_code)
            if holdings:
                # 获取最新报告日期
                report_date = datetime.now().strftime("%Y-%m-%d")
                cache_db.save_fund_holdings(fund_code, report_date, holdings)
                return holdings
        except Exception as e:
            print(f"获取基金持仓失败：{e}")

        # 降级到 Tushare
        if config.tushare_token:
            try:
                holdings = await tushare_client.get_fund_portfolio(fund_code)
                if holdings:
                    return holdings
            except Exception as e:
                print(f"Tushare 获取持仓失败：{e}")

        return []

    async def get_fund_ranking(self, fund_type: str = "全部") -> List[Dict[str, Any]]:
        """
        获取基金排行

        Args:
            fund_type: 基金类型

        Returns:
            排行列表
        """
        # 从 AKShare 获取
        try:
            ranking = await akshare_client.get_fund_ranking(fund_type)
            return ranking
        except Exception as e:
            print(f"AKShare 获取排行失败：{e}")

        # 降级到聚宽
        if config.jq_username and config.jq_password:
            try:
                ranking = await jq_client.get_fund_ranking(fund_type)
                return ranking
            except Exception as e:
                print(f"聚宽获取排行失败：{e}")

        return []

    async def get_fund_rating(self, fund_code: str) -> Optional[Dict[str, Any]]:
        """
        获取基金评级

        Args:
            fund_code: 基金代码

        Returns:
            评级数据
        """
        # 从缓存获取
        rating = cache_db.get_latest_rating(fund_code)
        if rating:
            return rating

        # 从 AKShare 获取全部评级，然后筛选
        try:
            ratings = await akshare_client.get_fund_rating()
            for r in ratings:
                cache_db.save_fund_rating(
                    r["fund_code"],
                    datetime.now().strftime("%Y-%m-%d"),
                    r["rating_agency"],
                    {"1y": r["rating_1y"], "2y": r["rating_2y"], "3y": r["rating_3y"]}
                )
            # 返回指定基金的评级
            for r in ratings:
                if r["fund_code"] == fund_code:
                    return r
        except Exception as e:
            print(f"获取基金评级失败：{e}")

        return None

    # ========== 基金筛选和分析 ==========

    async def screen_funds(
        self,
        fund_type: str = None,
        min_return_1y: float = None,
        max_drawdown: float = None,
        min_rating: int = None
    ) -> List[Dict[str, Any]]:
        """
        筛选基金

        Args:
            fund_type: 基金类型
            min_return_1y: 最小年化收益率
            max_drawdown: 最大回撤
            min_rating: 最低评级

        Returns:
            符合条件的基金列表
        """
        # 获取排行数据
        ranking = await self.get_fund_ranking(fund_type or "全部")

        # 筛选
        result = []
        for fund in ranking:
            # 收益率筛选
            if min_return_1y is not None and fund.get("return_1y", 0) < min_return_1y:
                continue

            # 获取评级
            rating = await self.get_fund_rating(fund["fund_code"])
            if min_rating is not None:
                if rating and rating.get("rating_1y", 0) < min_rating:
                    continue

            result.append(fund)

        return result

    async def get_fund_analysis(self, fund_code: str) -> Dict[str, Any]:
        """
        获取基金综合分析

        Args:
            fund_code: 基金代码

        Returns:
            分析结果
        """
        # 并行获取各类数据
        nav_task = self.get_fund_nav(fund_code)
        basic_task = self.get_fund_basic_info(fund_code)
        holdings_task = self.get_fund_holdings(fund_code)
        rating_task = self.get_fund_rating(fund_code)
        history_task = self.get_fund_history(fund_code, days=365)

        nav, basic, holdings, rating, history = await asyncio.gather(
            nav_task, basic_task, holdings_task, rating_task, history_task,
            return_exceptions=True
        )

        # 计算指标
        performance = self._calculate_performance(history) if history and not isinstance(history, Exception) else {}

        return {
            "basic": basic if basic and not isinstance(basic, Exception) else {},
            "nav": nav if nav and not isinstance(nav, Exception) else {},
            "holdings": holdings if holdings and not isinstance(holdings, Exception) else [],
            "rating": rating if rating and not isinstance(rating, Exception) else {},
            "performance": performance
        }

    def _calculate_performance(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算业绩指标

        Args:
            history: 历史净值数据

        Returns:
            业绩指标
        """
        if not history:
            return {}

        # 按日期排序
        history = sorted(history, key=lambda x: x.get("nav_date", ""))

        if len(history) < 2:
            return {}

        # 计算收益率
        navs = [h.get("unit_nav", 0) for h in history if h.get("unit_nav")]
        if len(navs) < 2:
            return {}

        current_nav = navs[-1]
        start_nav = navs[0]

        return {
            "total_return": (current_nav - start_nav) / start_nav * 100 if start_nav else 0,
            "annualized_return": self._calc_annualized_return(navs),
            "volatility": self._calc_volatility(navs),
            "max_drawdown": self._calc_max_drawdown(navs)
        }

    def _calc_annualized_return(self, navs: List[float]) -> float:
        """计算年化收益率"""
        if len(navs) < 2:
            return 0
        total_return = (navs[-1] - navs[0]) / navs[0]
        years = len(navs) / 252  # 交易日
        if years <= 0:
            return 0
        return ((1 + total_return) ** (1 / years) - 1) * 100

    def _calc_volatility(self, navs: List[float]) -> float:
        """计算波动率"""
        if len(navs) < 2:
            return 0
        returns = [(navs[i] - navs[i-1]) / navs[i-1] for i in range(1, len(navs))]
        if not returns:
            return 0
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        return (variance ** 0.5) * (252 ** 0.5) * 100  # 年化波动率

    def _calc_max_drawdown(self, navs: List[float]) -> float:
        """计算最大回撤"""
        if len(navs) < 2:
            return 0
        max_dd = 0
        peak = navs[0]
        for nav in navs:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd * 100


# 全局服务实例
fund_data_service = FundDataService()
