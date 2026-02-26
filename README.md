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

## 数据库表结构

数据存储于 `~/.ai_find_fund/fund_cache.db`（SQLite）

### 1. fund_basic - 基金基本信息表

| 字段名 | 类型 | 说明 |
|:------:|:----:|:-----|
| `fund_code` | TEXT | **主键** - 基金代码（如：000001） |
| `fund_name` | TEXT | 基金名称 |
| `fund_type` | TEXT | 基金类型（混合型、债券型、股票型等） |
| `company` | TEXT | 基金管理人/基金公司 |
| `manager` | TEXT | 基金经理 |
| `established_date` | TEXT | 成立日期 |
| `net_asset_size` | TEXT | **净资产规模**（如："10.5 亿"） |
| `share_size` | TEXT | **份额规模**（如："9.8 亿份"） |
| `updated_at` | TIMESTAMP | 更新时间 |

### 2. fund_nav - 基金净值表

| 字段名 | 类型 | 说明 |
|:------:|:----:|:-----|
| `id` | INTEGER | **主键** - 自增 |
| `fund_code` | TEXT | 基金代码 |
| `nav_date` | DATE | 净值日期 |
| `unit_nav` | REAL | 单位净值 |
| `accumulated_nav` | REAL | 累计净值 |
| `daily_growth` | REAL | 日增长率 |
| `created_at` | TIMESTAMP | 创建时间 |

**唯一约束**: `(fund_code, nav_date)`

### 3. fund_holdings - 基金持仓表

| 字段名 | 类型 | 说明 |
|:------:|:----:|:-----|
| `id` | INTEGER | **主键** - 自增 |
| `fund_code` | TEXT | 基金代码 |
| `report_date` | DATE | 报告期 |
| `stock_code` | TEXT | 股票代码 |
| `stock_name` | TEXT | 股票名称 |
| `holding_ratio` | REAL | 占净值比例（%） |
| `holding_amount` | INTEGER | 持股数量 |
| `holding_value` | REAL | 持仓市值 |
| `stock_type` | TEXT | 股票类型 |
| `created_at` | TIMESTAMP | 创建时间 |

### 4. fund_rating - 基金评级表

| 字段名 | 类型 | 说明 |
|:------:|:----:|:-----|
| `id` | INTEGER | **主键** - 自增 |
| `fund_code` | TEXT | 基金代码 |
| `rating_date` | DATE | 评级日期 |
| `rating_agency` | TEXT | 评级机构 |
| `rating_1y` | INTEGER | 1 年期评级（1-5 星） |
| `rating_2y` | INTEGER | 2 年期评级 |
| `rating_3y` | INTEGER | 3 年期评级 |
| `created_at` | TIMESTAMP | 创建时间 |

### 5. update_log - 数据更新日志表

| 字段名 | 类型 | 说明 |
|:------:|:----:|:-----|
| `id` | INTEGER | **主键** - 自增 |
| `data_type` | TEXT | 数据类型（fund_list、daily_nav 等） |
| `updated_at` | TIMESTAMP | 更新时间 |
| `status` | TEXT | 状态（success/error） |
| `message` | TEXT | 更新消息/错误信息 |

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
