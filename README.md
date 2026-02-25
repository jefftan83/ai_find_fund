# 基金推荐助手 (Fund Advisor)

多 Agent CLI 基金推荐程序，通过对话为您推荐合适的基金组合。

## 功能特点

- 🤖 **多 Agent 架构**：需求分析、风险评估、基金推荐三个专业 Agent 协作
- 📊 **多层次数据源**：AKShare（主）+ Tushare + 新浪财经 + 聚宽（备用）
- 💾 **本地缓存**：SQLite 缓存，减少 API 调用
- 🎯 **个性化推荐**：根据您的投资目标和风险承受能力推荐基金
- 💻 **命令行界面**：简洁美观的 TUI 交互

## 安装

### 1. 克隆项目

```bash
cd ai_find_fund
```

### 2. 安装依赖

```bash
pip install -e .
```

### 3. 配置 API Key

复制配置文件并编辑：

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml`，填入 Anthropic API Key：

```yaml
anthropic_api_key: "sk-ant-..."
```

或者设置环境变量：

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## 使用方法

### 启动程序

```bash
fund-advisor start
```

或：

```bash
python -m src.main start
```

### 查看配置状态

```bash
fund-advisor config-status
```

### 查看版本

```bash
fund-advisor version
```

## 对话流程

1. **需求分析**：了解投资金额、期限、目标等
2. **风险评估**：评估风险承受能力，给出风险等级
3. **基金推荐**：根据画像推荐 3-5 只基金

## 风险等级说明

| 等级 | 特点 | 推荐基金类型 |
|------|------|-------------|
| 保守型 | 不能接受本金损失 | 货币基金、短债基金 |
| 稳健型 | 能承受 5-10% 波动 | 债券基金、固收 +、平衡混合 |
| 积极型 | 能承受 10-20% 波动 | 偏股混合、指数增强 |
| 激进型 | 能承受 20% 以上波动 | 股票型、行业主题基金 |

## 数据源

- **主数据源**：AKShare（天天基金/东方财富数据）
- **备用 1**：Tushare（需注册）
- **备用 2**：新浪财经（实时行情）
- **备用 3**：聚宽（需注册）

## 打包发布

### macOS / Linux

```bash
pyinstaller --onefile --name fund-advisor src/main.py
```

### Windows

```bash
pyinstaller --onefile --name fund-advisor src\main.py
```

打包后的可执行文件在 `dist/` 目录中。

## 项目结构

```
ai_find_fund/
├── src/
│   ├── main.py              # CLI 入口
│   ├── agents/
│   │   ├── manager.py       # 群聊管理器
│   │   ├── requirement.py   # 需求分析 Agent
│   │   ├── risk.py          # 风险评估 Agent
│   │   └── fund_expert.py   # 基金专家 Agent
│   ├── services/
│   │   ├── fund_data.py     # 数据服务（多源融合）
│   │   ├── akshare_client.py
│   │   ├── tushare_client.py
│   │   ├── sina_client.py
│   │   └── jq_client.py
│   ├── cache/
│   │   └── db.py            # SQLite 缓存
│   └── utils/
│       ├── config.py        # 配置管理
│       └── llm.py           # Claude API 封装
├── config.yaml.example      # 配置示例
├── pyproject.toml           # 项目配置
└── README.md
```

## 开发

```bash
# 开发模式安装
pip install -e ".[dev]"

# 运行测试
python -m pytest
```

## 注意事项

⚠️ **投资有风险，入市需谨慎**

本程序仅提供基金推荐参考，不构成投资建议。投资前请：
- 仔细阅读基金合同、招募说明书
- 了解基金的风险收益特征
- 根据自身情况做出独立判断

## License

MIT
