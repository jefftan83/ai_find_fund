"""配置管理模块"""

import os
import yaml
from pathlib import Path
from typing import Optional


class Config:
    """配置管理类"""

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: dict = {}
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {}

    def save_config(self):
        """保存配置文件"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)

    def get(self, key: str, default=None):
        """获取配置项"""
        return self._config.get(key, default)

    def set(self, key: str, value):
        """设置配置项"""
        self._config[key] = value
        self.save_config()

    # LLM 配置
    @property
    def anthropic_api_key(self) -> Optional[str]:
        """获取 Anthropic API Key"""
        return os.getenv("ANTHROPIC_API_KEY") or self._config.get("anthropic_api_key")

    @property
    def anthropic_base_url(self) -> Optional[str]:
        """获取 Anthropic API 基础 URL"""
        return os.getenv("ANTHROPIC_BASE_URL") or self._config.get("anthropic_base_url")

    @property
    def claude_model(self) -> str:
        """获取 Claude 模型名称"""
        return self._config.get("claude_model", "qwen3.5-plus")

    # Tushare 配置
    @property
    def tushare_token(self) -> Optional[str]:
        """获取 Tushare Token"""
        return os.getenv("TUSHARE_TOKEN") or self._config.get("tushare_token")

    # 聚宽配置
    @property
    def jq_username(self) -> Optional[str]:
        """获取聚宽用户名"""
        return os.getenv("JQ_USERNAME") or self._config.get("jq_username")

    @property
    def jq_password(self) -> Optional[str]:
        """获取聚宽密码"""
        return os.getenv("JQ_PASSWORD") or self._config.get("jq_password")

    # 数据缓存配置
    @property
    def db_path(self) -> Path:
        """获取数据库路径"""
        db_path = self._config.get("db_path", "data/fund_cache.db")
        return Path(__file__).parent.parent.parent / db_path

    @property
    def data_update_interval(self) -> int:
        """获取数据更新间隔（小时）"""
        return self._config.get("data_update_interval", 24)


# 全局配置实例
config = Config()
