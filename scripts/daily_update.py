#!/usr/bin/env python3
"""
基金数据每日自动更新脚本

整合所有数据更新需求，根据配置的频率自动执行：
- 每日：当日净值
- 每周：基金规模（缺失数据）
- 每月：基金评级、持仓

使用方法：
    python3 scripts/daily_update.py

配置：
    编辑脚本顶部的 CONFIG 配置项
"""

import asyncio
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ==================== 配置区域 ====================

CONFIG = {
    # 数据文件路径
    "data_dir": "/Users/tanjingfeng/Desktop/ai_find_fund/data",
    "state_file": "/Users/tanjingfeng/Desktop/ai_find_fund/data/update_state.json",

    # 更新频率配置（天数）
    "nav_update_interval": 1,        # 净值：每日更新
    "size_update_interval": 7,       # 规模：每周更新
    "rating_update_interval": 30,    # 评级：每月更新
    "holdings_update_interval": 30,  # 持仓：每月更新

    # 更新数量限制（0=全部）
    "nav_limit": 0,           # 0=更新全部基金净值
    "size_limit": 100,        # 0=全部，推荐 100（只更新缺失的前 N 只）
    "rating_limit": 500,      # 每次更新评级的基金数量
    "holdings_limit": 100,    # 每次更新持仓的基金数量

    # 通知配置
    "log_file": "/tmp/fund_update.log",
    "verbose": True,          # 是否显示详细日志
}

# ==================== 不要修改以下代码 ====================

from src.cache.db import cache_db
from scripts.data_loader import (
    load_daily_nav,
    load_fund_ratings,
    load_fund_holdings,
)


class UpdateStateManager:
    """更新状态管理器"""

    def __init__(self, state_file):
        self.state_file = Path(state_file)
        self.state = self._load_state()

    def _load_state(self):
        """加载状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "last_nav_update": None,
            "last_size_update": None,
            "last_rating_update": None,
            "last_holdings_update": None,
            "total_updates": 0,
        }

    def save_state(self):
        """保存状态"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def should_update(self, key, interval_days):
        """检查是否应该更新"""
        last_update = self.state.get(f"last_{key}_update")
        if last_update is None:
            return True

        last_time = datetime.fromisoformat(last_update)
        return (datetime.now() - last_time).days >= interval_days

    def mark_updated(self, key):
        """标记为已更新"""
        self.state[f"last_{key}_update"] = datetime.now().isoformat()
        self.state["total_updates"] = self.state.get("total_updates", 0) + 1
        self.save_state()


class FundDataUpdater:
    """基金数据更新器"""

    def __init__(self, config):
        self.config = config
        self.state = UpdateStateManager(config["state_file"])
        self.log_lines = []

    def log(self, message, verbose=True):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        self.log_lines.append(log_line)
        if verbose:
            print(log_line)

    def save_log(self):
        """保存日志到文件"""
        log_path = Path(self.config["log_file"])
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, 'a') as f:
            for line in self.log_lines:
                f.write(line + "\n")

    async def update_nav(self):
        """更新净值数据"""
        if not self.state.should_update("nav", self.config["nav_update_interval"]):
            self.log("⏭️  跳过：当日净值（今日已更新）", self.config["verbose"])
            return

        self.log("📊 开始更新：当日净值...", self.config["verbose"])
        try:
            count = await load_daily_nav()
            self.state.mark_updated("nav")
            self.log(f"✅ 完成：更新净值 {count} 条", self.config["verbose"])
        except Exception as e:
            self.log(f"❌ 失败：更新净值 - {e}", self.config["verbose"])

    async def update_size(self):
        """更新规模数据"""
        if not self.state.should_update("size", self.config["size_update_interval"]):
            self.log("⏭️  跳过：基金规模（本周已更新）", self.config["verbose"])
            return

        self.log("💰 开始更新：基金规模（缺失数据）...", self.config["verbose"])
        try:
            # 动态导入 load_missing_size
            from scripts.load_missing_size import load_missing_fund_size
            await load_missing_fund_size()
            self.state.mark_updated("size")
            self.log("✅ 完成：基金规模更新", self.config["verbose"])
        except Exception as e:
            self.log(f"❌ 失败：更新规模 - {e}", self.config["verbose"])

    async def update_ratings(self):
        """更新评级数据"""
        if not self.state.should_update("rating", self.config["rating_update_interval"]):
            self.log("⏭️  跳过：基金评级（本月已更新）", self.config["verbose"])
            return

        self.log("⭐ 开始更新：基金评级...", self.config["verbose"])
        try:
            await load_fund_ratings()
            self.state.mark_updated("rating")
            self.log("✅ 完成：基金评级更新", self.config["verbose"])
        except Exception as e:
            self.log(f"❌ 失败：更新评级 - {e}", self.config["verbose"])

    async def update_holdings(self):
        """更新持仓数据"""
        if not self.state.should_update("holdings", self.config["holdings_update_interval"]):
            self.log("⏭️  跳过：基金持仓（本月已更新）", self.config["verbose"])
            return

        self.log("📋 开始更新：基金持仓...", self.config["verbose"])
        try:
            await load_fund_holdings(limit=self.config["holdings_limit"])
            self.state.mark_updated("holdings")
            self.log("✅ 完成：基金持仓更新", self.config["verbose"])
        except Exception as e:
            self.log(f"❌ 失败：更新持仓 - {e}", self.config["verbose"])

    async def run_all(self):
        """执行所有更新任务"""
        self.log("=" * 60, self.config["verbose"])
        self.log("🚀 基金数据每日更新开始", self.config["verbose"])
        self.log("=" * 60, self.config["verbose"])

        start_time = datetime.now()

        # 按顺序执行更新任务
        await self.update_nav()       # 每日
        await self.update_size()      # 每周
        await self.update_ratings()   # 每月
        await self.update_holdings()  # 每月

        elapsed = (datetime.now() - start_time).total_seconds()

        self.log("=" * 60, self.config["verbose"])
        self.log(f"✅ 全部更新完成！耗时：{elapsed:.1f}秒", self.config["verbose"])
        self.log("=" * 60, self.config["verbose"])

        # 显示下次更新时间
        self._show_next_update()

        # 保存日志
        self.save_log()

    def _show_next_update(self):
        """显示下次更新时间"""
        now = datetime.now()

        next_nav = datetime.fromisoformat(self.state.state.get("last_nav_update", now.isoformat())) + timedelta(days=self.config["nav_update_interval"])
        next_size = datetime.fromisoformat(self.state.state.get("last_size_update", now.isoformat())) + timedelta(days=self.config["size_update_interval"])
        next_rating = datetime.fromisoformat(self.state.state.get("last_rating_update", now.isoformat())) + timedelta(days=self.config["rating_update_interval"])
        next_holdings = datetime.fromisoformat(self.state.state.get("last_holdings_update", now.isoformat())) + timedelta(days=self.config["holdings_update_interval"])

        self.log("\n📅 下次更新计划:", self.config["verbose"])
        self.log(f"   • 当日净值：{next_nav.strftime('%Y-%m-%d %H:%M')} (每{self.config['nav_update_interval']}天)", self.config["verbose"])
        self.log(f"   • 基金规模：{next_size.strftime('%Y-%m-%d %H:%M')} (每{self.config['size_update_interval']}天)", self.config["verbose"])
        self.log(f"   • 基金评级：{next_rating.strftime('%Y-%m-%d %H:%M')} (每{self.config['rating_update_interval']}天)", self.config["verbose"])
        self.log(f"   • 基金持仓：{next_holdings.strftime('%Y-%m-%d %H:%M')} (每{self.config['holdings_update_interval']}天)", self.config["verbose"])


async def main():
    """主函数"""
    updater = FundDataUpdater(CONFIG)
    await updater.run_all()


if __name__ == '__main__':
    asyncio.run(main())
