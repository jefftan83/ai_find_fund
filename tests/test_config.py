"""
配置管理模块测试
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.utils.config import Config


class TestConfig:
    """Config 类测试"""

    def test_default_config_load(self):
        """CFG-001: 默认配置加载"""
        config = Config()
        assert config is not None
        # 默认模型应该是 qwen3.5-plus
        assert config.claude_model == "qwen3.5-plus"

    def test_custom_config_file(self):
        """CFG-002: 自定义配置文件加载"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("anthropic_api_key: test-key-123\n")
            f.write("claude_model: custom-model\n")
            f.name

        try:
            config = Config(Path(f.name))
            assert config.anthropic_api_key == "test-key-123"
            assert config.claude_model == "custom-model"
        finally:
            os.unlink(f.name)

    def test_config_file_not_exists(self):
        """CFG-003: 配置文件不存在"""
        config = Config(Path("/non/existent/path/config.yaml"))
        assert config._config == {}
        assert config.anthropic_api_key is None

    def test_api_key_from_env(self):
        """CFG-004: API Key 从环境变量读取"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key-456"}):
            config = Config()
            assert config.anthropic_api_key == "env-key-456"

    def test_api_key_from_config(self):
        """CFG-005: API Key 从配置文件读取"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("anthropic_api_key: config-key-789\n")
            f.name

        try:
            # 确保环境变量未设置
            with patch.dict(os.environ, {}, clear=True):
                config = Config(Path(f.name))
                assert config.anthropic_api_key == "config-key-789"
        finally:
            os.unlink(f.name)

    def test_save_config(self):
        """CFG-006: 配置保存"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.yaml"
            config = Config(config_path)
            config.set("test_key", "test_value")

            # 验证文件被创建
            assert config_path.exists()

            # 验证内容
            new_config = Config(config_path)
            assert new_config.get("test_key") == "test_value"

    def test_get_nonexistent_key(self):
        """CFG-007: 获取不存在的配置项"""
        config = Config()
        assert config.get("nonexistent_key") is None
        assert config.get("nonexistent_key", "default") == "default"

    def test_db_path_resolution(self):
        """CFG-008: 数据库路径解析"""
        config = Config()
        db_path = config.db_path
        # 应该返回绝对路径
        assert db_path.is_absolute()
        assert db_path.name == "fund_cache.db"

    def test_tushare_token_env(self):
        """CFG-009: Tushare Token 从环境变量读取"""
        with patch.dict(os.environ, {"TUSHARE_TOKEN": "tushare-test-token"}):
            config = Config()
            assert config.tushare_token == "tushare-test-token"

    def test_jq_credentials_env(self):
        """CFG-010: 聚宽账号从环境变量读取"""
        with patch.dict(os.environ, {
            "JQ_USERNAME": "jq_user",
            "JQ_PASSWORD": "jq_pass"
        }):
            config = Config()
            assert config.jq_username == "jq_user"
            assert config.jq_password == "jq_pass"

    def test_data_update_interval(self):
        """CFG-011: 数据更新间隔"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("data_update_interval: 48\n")
            f.name

        try:
            config = Config(Path(f.name))
            assert config.data_update_interval == 48
        finally:
            os.unlink(f.name)

    def test_base_url_config(self):
        """CFG-012: API Base URL 配置"""
        # 使用一个不存在的配置文件路径，避免读取默认的 config.yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.yaml"
            with open(config_path, 'w') as f:
                f.write('anthropic_base_url: "https://custom-api.com"\n')
                f.write('anthropic_api_key: test-key\n')

            # 使用临时文件创建 Config，并清除环境变量
            with patch.dict(os.environ, {}, clear=True):
                config = Config(config_path)
                assert config.anthropic_base_url == "https://custom-api.com"

    def test_base_url_env(self):
        """CFG-013: Base URL 从环境变量读取"""
        with patch.dict(os.environ, {"ANTHROPIC_BASE_URL": "https://env-api.com"}):
            config = Config()
            assert config.anthropic_base_url == "https://env-api.com"
