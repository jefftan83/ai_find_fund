"""新浪财经数据源客户端"""

import httpx
from typing import List, Dict, Any, Optional
import re


class SinaClient:
    """新浪财经基金数据客户端"""

    BASE_URL = "http://hq.sinajs.cn"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.close()

    async def get_fund_nav(self, fund_code: str) -> Optional[Dict[str, Any]]:
        """
        获取基金净值（实时）

        Args:
            fund_code: 基金代码

        Returns:
            基金净值数据
        """
        client = await self._get_client()
        try:
            # 新浪财经基金接口
            url = f"{self.BASE_URL}/fund={fund_code}"
            response = await client.get(url)
            response.raise_for_status()

            # 解析返回数据（JavaScript 变量格式）
            # var hq_str_FUND_000001="基金名称，单位净值，累计净值，..."
            content = response.text
            match = re.search(r'="([^"]+)"', content)
            if match:
                values = match.group(1).split(",")
                if len(values) >= 5:
                    return {
                        "fund_code": fund_code,
                        "fund_name": values[0],
                        "unit_nav": float(values[1]) if values[1] else 0,
                        "accumulated_nav": float(values[2]) if values[2] else 0,
                        "previous_nav": float(values[3]) if values[3] else 0,
                        "nav_date": values[4] if values[4] else ""
                    }
            return None
        except Exception as e:
            raise Exception(f"新浪财经获取基金净值失败：{str(e)}")

    async def get_fund_nav_batch(self, fund_codes: List[str]) -> List[Dict[str, Any]]:
        """
        批量获取基金净值

        Args:
            fund_codes: 基金代码列表

        Returns:
            基金净值列表
        """
        client = await self._get_client()
        results = []

        # 新浪财经支持批量查询
        symbols = "_".join([f"fund_{code}" for code in fund_codes])
        try:
            url = f"{self.BASE_URL}/{symbols}"
            response = await client.get(url)
            response.raise_for_status()

            # 解析多行返回
            for line in response.text.split("\n"):
                match = re.search(r'fund_(\d+)="([^"]+)"', line)
                if match:
                    fund_code = match.group(1)
                    values = match.group(2).split(",")
                    if len(values) >= 5:
                        results.append({
                            "fund_code": fund_code,
                            "fund_name": values[0],
                            "unit_nav": float(values[1]) if values[1] else 0,
                            "accumulated_nav": float(values[2]) if values[2] else 0,
                            "previous_nav": float(values[3]) if values[3] else 0,
                            "nav_date": values[4] if values[4] else ""
                        })

            return results
        except Exception as e:
            raise Exception(f"新浪财经批量获取基金净值失败：{str(e)}")

    async def get_fund_history(self, fund_code: str, year: int = None) -> List[Dict[str, Any]]:
        """
        获取基金历史净值

        Args:
            fund_code: 基金代码
            year: 年份（默认去年）

        Returns:
            历史净值列表
        """
        client = await self._get_client()
        import datetime
        if year is None:
            year = datetime.datetime.now().year - 1

        try:
            # 新浪财经历史数据接口
            url = f"http://api.finance.sina.com.cn/fundkline/{fund_code}_{year}.csv"
            response = await client.get(url)
            response.raise_for_status()

            # 解析 CSV 数据
            lines = response.text.strip().split("\n")
            results = []
            for line in lines[1:]:  # 跳过表头
                parts = line.split(",")
                if len(parts) >= 7:
                    results.append({
                        "nav_date": parts[0],
                        "unit_nav": float(parts[1]) if parts[1] else 0,
                        "accumulated_nav": float(parts[2]) if parts[2] else 0,
                        "daily_growth": float(parts[6]) if parts[6] else 0
                    })
            return results
        except Exception as e:
            # 如果历史数据获取失败，返回空列表
            return []


# 全局客户端实例
sina_client = SinaClient()
