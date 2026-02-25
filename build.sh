#!/bin/bash
# 打包脚本 - 生成单文件可执行程序

set -e

echo "🚀 开始打包基金推荐助手..."

# 清理旧的构建文件
echo "🧹 清理旧文件..."
rm -rf dist/ build/

# 获取系统类型
OS=$(uname -s)
echo "💻 检测到系统：$OS"

# 根据系统设置可执行文件名称
if [[ $OS == "Darwin" ]]; then
    APP_NAME="fund-advisor-macos"
elif [[ $OS == "Linux" ]]; then
    APP_NAME="fund-advisor-linux"
else
    APP_NAME="fund-advisor"
fi

# 运行 PyInstaller
echo "📦 打包中..."
pyinstaller \
    --onefile \
    --name "$APP_NAME" \
    --add-data "config.yaml.example:." \
    --hidden-import=akshare \
    --hidden-import=tushare \
    --hidden-import=jqdatasdk \
    --hidden-import=anthropic \
    --hidden-import=autogen_agentchat \
    --hidden-import=typer \
    --hidden-import=rich \
    --hidden-import=pandas \
    --hidden-import=yaml \
    src/main.py

echo "✅ 打包完成！"
echo ""
echo "📍 可执行文件位置：dist/$APP_NAME"
echo ""
echo "使用说明："
echo "  1. 复制配置文件：cp config.yaml.example config.yaml"
echo "  2. 编辑 config.yaml，填入 API Key"
echo "  3. 运行：./dist/$APP_NAME start"
