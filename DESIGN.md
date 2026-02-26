# 基金推荐系统设计文档

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                │
│                     CLI (Typer + Rich)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Agent 层                                │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │Requirement  │ → │    Risk     │ → │   FundExpert        │   │
│  │需求分析 Agent │   │ 风险评估 Agent│   │   基金推荐 Agent       │   │
│  └─────────────┘   └─────────────┘   └─────────────────────┘   │
│                    GroupChatManager 协调                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         服务层                                  │
│                    FundDataService                              │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │  AKShare    │   │   Tushare   │   │      Sina/JQ        │   │
│  │  (主数据源)  │   │  (降级 1)    │   │    (降级 2/3)        │   │
│  └─────────────┘   └─────────────┘   └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         缓存层                                  │
│                    SQLite (fund_cache.db)                       │
│  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌─────────┐ ┌─────────┐  │
│  │fund_basic│ │fund_nav│ │holdings  │ │rating   │ │update_  │  │
│  │          │ │        │ │          │ │         │ │log      │  │
│  └──────────┘ └────────┘ └──────────┘ └─────────┘ └─────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 数据库表结构

数据库文件：`~/.ai_find_fund/fund_cache.db`

### 2.1 fund_basic - 基金基本信息表

**用途**: 存储基金的基本信息

| 字段名 | 类型 | 约束 | 说明 |
|:------:|:----:|:-----|:-----|
| `fund_code` | TEXT | PRIMARY KEY | 基金代码（如：000001） |
| `fund_name` | TEXT | | 基金名称 |
| `fund_type` | TEXT | | 基金类型（混合型、债券型、股票型等） |
| `company` | TEXT | | 基金管理人/基金公司 |
| `manager` | TEXT | | 基金经理 |
| `established_date` | TEXT | | 成立日期 |
| `net_asset_size` | TEXT | | 净资产规模（如："10.5 亿"） |
| `share_size` | TEXT | | 份额规模（如："9.8 亿份"） |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**示例数据**:
```
fund_code  | fund_name    | fund_type | company      | net_asset_size
000001     | 华夏成长混合  | 混合型     | 华夏基金      | 10.5 亿
```

---

### 2.2 fund_nav - 基金净值表

**用途**: 存储基金每日净值数据

| 字段名 | 类型 | 约束 | 说明 |
|:------:|:----:|:-----|:-----|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| `fund_code` | TEXT | NOT NULL | 基金代码 |
| `nav_date` | DATE | NOT NULL | 净值日期 |
| `unit_nav` | REAL | | 单位净值 |
| `accumulated_nav` | REAL | | 累计净值 |
| `daily_growth` | REAL | | 日增长率（%） |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**唯一约束**: `UNIQUE(fund_code, nav_date)`

**索引**: `idx_nav_code_date ON (fund_code, nav_date)`

**示例数据**:
```
fund_code | nav_date   | unit_nav | accumulated_nav | daily_growth
000001    | 2025-02-25 | 1.234    | 2.345           | 0.015
```

---

### 2.3 fund_holdings - 基金持仓表

**用途**: 存储基金季度持仓明细

| 字段名 | 类型 | 约束 | 说明 |
|:------:|:----:|:-----|:-----|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| `fund_code` | TEXT | NOT NULL | 基金代码 |
| `report_date` | DATE | NOT NULL | 报告期（如：2025-03-31） |
| `stock_code` | TEXT | | 股票代码 |
| `stock_name` | TEXT | | 股票名称 |
| `holding_ratio` | REAL | | 占净值比例（%） |
| `holding_amount` | INTEGER | | 持股数量 |
| `holding_value` | REAL | | 持仓市值（元） |
| `stock_type` | TEXT | | 股票类型 |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引**: `idx_holdings_code ON (fund_code)`

**示例数据**:
```
fund_code | report_date | stock_code | stock_name | holding_ratio
000001    | 2025-03-31  | 600001     | 浦发银行    | 5.5
```

---

### 2.4 fund_rating - 基金评级表

**用途**: 存储第三方机构基金评级

| 字段名 | 类型 | 约束 | 说明 |
|:------:|:----:|:-----|:-----|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| `fund_code` | TEXT | NOT NULL | 基金代码 |
| `rating_date` | DATE | NOT NULL | 评级日期 |
| `rating_agency` | TEXT | | 评级机构（上海证券、招商证券等） |
| `rating_1y` | INTEGER | | 1 年期评级（1-5 星） |
| `rating_2y` | INTEGER | | 2 年期评级（1-5 星） |
| `rating_3y` | INTEGER | | 3 年期评级（1-5 星） |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引**: `idx_rating_code ON (fund_code)`

**示例数据**:
```
fund_code | rating_date | rating_agency | rating_1y | rating_3y
000001    | 2025-02-24  | 上海证券       | 5         | 5
```

---

### 2.5 update_log - 数据更新日志表

**用途**: 记录数据更新历史

| 字段名 | 类型 | 约束 | 说明 |
|:------:|:----:|:-----|:-----|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| `data_type` | TEXT | NOT NULL | 数据类型（fund_list、daily_nav 等） |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |
| `status` | TEXT | | 状态（success/error） |
| `message` | TEXT | | 更新消息/错误信息 |

**示例数据**:
```
data_type   | updated_at          | status  | message
fund_list   | 2025-02-25 10:00:00 | success | Updated 10000 funds
daily_nav   | 2025-02-25 10:05:00 | error   | API timeout
```

---

## 3. ER 图

```
┌─────────────────┐
│   fund_basic    │
│─────────────────│
│ fund_code (PK)  │◄────┐
│ fund_name       │     │
│ fund_type       │     │
│ company         │     │
│ manager         │     │
│ established_date│     │
│ net_asset_size  │     │
│ share_size      │     │
│ updated_at      │     │
└─────────────────┘     │
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────────┐ ┌─────────────┐ ┌──────────────┐
│   fund_nav    │ │fund_holdings│ │ fund_rating  │
│───────────────│ │─────────────│ │──────────────│
│ id (PK)       │ │ id (PK)     │ │ id (PK)      │
│ fund_code     │ │ fund_code   │ │ fund_code    │
│ nav_date      │ │ report_date │ │ rating_date  │
│ unit_nav      │ │ stock_code  │ │ rating_agency│
│ accumulated_  │ │ stock_name  │ │ rating_1y    │
│ daily_growth  │ │ holding_    │ │ rating_2y    │
│ created_at    │ │ created_at  │ │ rating_3y    │
│ [UNIQUE]      │ │             │ │ created_at   │
└───────────────┘ └─────────────┘ └──────────────┘

┌─────────────────┐
│   update_log    │
│─────────────────│
│ id (PK)         │
│ data_type       │
│ updated_at      │
│ status          │
│ message         │
└─────────────────┘
```

---

## 4. 数据源降级策略

```
┌──────────────────────────────────────────────────────────┐
│                     用户请求数据                          │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   1. AKShare    │ ──────→ 失败 ────┐
                 │   (主数据源)     │                │
                 └─────────────────┘                │
                          │                         ▼
                          │                ┌─────────────────┐
                          │                │   2. Tushare    │ ──→ 失败 ──┐
                          │                │   (需 API Token) │            │
                          │                └─────────────────┘            │
                          │                         │                     ▼
                          │                         │            ┌─────────────────┐
                          │                         │            │   3. 新浪财经    │ ─→ 失败 ─→ 返回缓存
                          │                         │            │   (实时行情)    │
                          │                         │            └─────────────────┘
                          ▼                         ▼
                 ┌─────────────────────────────────────────┐
                 │           成功 → 写入缓存 → 返回         │
                 └─────────────────────────────────────────┘
```

---

## 5. Agent 协作流程

```
用户输入
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│                    GroupChatManager                         │
│                                                             │
│  当前阶段：requirement → risk → recommendation → complete   │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ RequirementAgent│  │   RiskAgent     │  │ FundExpertAgent │
│─────────────────│  │─────────────────│  │─────────────────│
│ - 投资金额      │  │ - 风险测评      │  │ - 基金筛选      │
│ - 投资期限      │  │ - 风险等级      │  │ - 组合配置      │
│ - 投资目标      │  │ - 基金类型推荐  │  │ - 推荐生成      │
│ - 投资经验      │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  fund_data_svc  │
                    │  (数据服务层)    │
                    └─────────────────┘
```

---

## 6. 缓存策略

### 6.1 缓存有效期

| 数据类型 | 缓存有效期 | 说明 |
|:--------:|:----------:|:-----|
| fund_list | 24 小时 | 基金列表更新频率低 |
| daily_nav | 24 小时 | 每日净值 T+1 更新 |
| fund_basic | 7 天 | 基金基本信息相对稳定 |
| fund_holdings | 30 天 | 季度持仓报告 |
| fund_rating | 7 天 | 评级月度更新 |

### 6.2 缓存清理

- 净值数据：保留 365 天
- 持仓数据：保留最近 4 期
- 评级数据：保留最近 12 期

---

## 7. API 接口

### 7.1 FundDataService

```python
class FundDataService:
    # 获取基金列表
    async def get_fund_list(use_cache: bool = True) -> List[Dict]

    # 获取当日净值
    async def get_daily_nav(use_cache: bool = True) -> List[Dict]

    # 获取单只基金净值
    async def get_fund_nav(fund_code: str, use_cache: bool = True) -> Dict

    # 获取历史净值
    async def get_fund_history(fund_code: str, days: int = 365) -> List[Dict]

    # 获取基金排行
    async def get_fund_ranking(fund_type: str = "全部") -> List[Dict]

    # 获取持仓
    async def get_fund_holdings(fund_code: str) -> List[Dict]

    # 获取评级
    async def get_fund_rating(fund_code: str) -> Dict

    # 基金筛选
    async def screen_funds(min_return_1y: float = None, ...) -> List[Dict]

    # 综合分析
    async def get_fund_analysis(fund_code: str) -> Dict
```

---

## 8. 配置项

```yaml
# config.yaml
anthropic_api_key: "sk-ant-..."  # LLM API Key
tushare_token: "..."             # Tushare Token (可选)
db_path: "~/.ai_find_fund/fund_cache.db"
data_update_interval: 24         # 缓存有效期（小时）
```

---

## 9. 版本历史

| 版本 | 日期 | 变更内容 |
|:----:|:----:|:---------|
| v0.1.0 | 2025-02 | 初始版本，多 Agent 架构 + AKShare 数据源 |
| v0.1.1 | 2025-02 | 新增基金规模数据、data_loader 工具 |
