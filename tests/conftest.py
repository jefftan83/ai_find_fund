"""测试配置文件"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 全局 pytest 配置
pytest_plugins = [
    "pytest_asyncio",
]

# 配置 asyncio 模式
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test."
    )
