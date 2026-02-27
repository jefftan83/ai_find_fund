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
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                          │
│                    │  CriticAgent    │                          │
│                    │   验证器 Agent   │                          │
│                    │  (验证推荐质量)  │                          │
│                    └─────────────────┘                          │
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

## 8. Agent 详细设计（v0.2 增强版）

### 8.1 FundExpertAgent - 基金专家 Agent

**职责**: 根据用户画像和风险等级，推荐 3-5 只最适合的基金

#### System Prompt 设计（Chain of Thought 推理框架）

```
你是一位持牌基金投资分析师，擅长基于多维度数据生成个性化基金推荐。

## 分析框架（必须按步骤思考）

### 步骤 1：用户情况综合分析
- 投资金额决定单次配置的最小单位（如 10 万以下避免过度分散）
- 投资期限决定流动性要求（短期避免高波动，长期可承受波动换取收益）
- 投资目标决定风险偏好（保值/稳健/进取）
- 投资经验决定解释深度（新手需要更多教育性说明）
- 风险等级决定资产配置上限

### 步骤 2：基金筛选与排序
对每只候选基金进行多维度评分（1-5 分）：
1. 业绩稳定性：近 1 年、近 3 年收益是否一致性好
2. 风险控制：最大回撤、波动率是否在可接受范围
3. 规模适宜性：2 亿 < 规模 < 100 亿为最佳
4. 评级背书：是否有 3 星以上评级
5. 经理稳定性：经理任职时长是否超过 3 年

### 步骤 3：配置比例计算
根据用户风险等级和投资期限，动态计算配置比例：
- 保守型：债券基金 70-90%
- 稳健型：混合基金 40-60% + 债券基金 30-50%
- 积极型：偏股混合 50-70% + 债券 20-40%
- 激进型：股票型 60-80% + 偏股混合 20-40%

### 步骤 4：风险披露生成
针对每只推荐基金，明确指出：
- 最大可能回撤幅度
- 最坏情景下的损失
- 流动性风险（如有）
```

#### 输出格式（XML 结构化）

```xml
<analysis>
用户综合分析：[投资金额、期限、目标、经验、风险等级的综合影响分析]
</analysis>

<fund_evaluation>
| 基金代码 | 综合评分 | 优势 | 劣势 | 适配度 |
|---------|---------|------|------|-------|
| 000001  | 4.2     | 业绩稳定，规模适中 | 经理任职短 | 高    |
</fund_evaluation>

<recommendation>
<fund>
  <code>000001</code>
  <name>华夏成长混合</name>
  <allocation>30%</allocation>
  <rationale>[推荐理由，必须引用具体数据支撑]</rationale>
  <risk_warning>[具体风险，如"近 3 年最大回撤 -25%"]</risk_warning>
  <confidence>high/medium/low</confidence>
</fund>
</recommendation>

<disclaimer>
本推荐基于历史数据分析，不构成投资建议。投资有风险，入市需谨慎。
</disclaimer>
```

#### 数据维度（13+ 项）

| 数据类别 | 字段 | 获取方式 |
|:--------:|:-----|:---------|
| 收益率序列 | 近 1/3/6 月，近 1/3 年，今年来 | 排行榜缓存 |
| 基金规模 | 净资产规模、份额规模 | SQLite 缓存 |
| 基金评级 | rating_1y/2y/3y | SQLite 缓存 |
| 基金经理 | manager | SQLite 缓存 |
| 基金公司 | company | SQLite 缓存 |
| 风险指标 | 最大回撤、波动率 | 本地计算（最近 252 日净值） |
| 持仓集中度 | 前十大重仓股占比 | SQLite 缓存 |

#### LLM 调用参数

| 参数 | 值 | 说明 |
|:----:|:---|:-----|
| `max_tokens` | 3000 | 容纳完整推理过程 |
| `temperature` | 0.3 | 降低随机性，提高一致性 |

---

### 8.2 CriticAgent - 验证器 Agent

**职责**: 检查 FundExpertAgent 推荐的合理性和合规性

#### 验证维度

| 验证项 | 权重 | 检查内容 |
|:------:|:----:|:---------|
| XML 格式 | 20 分 | 标签正确闭合，必需标签存在 |
| 配置比例 | 25 分 | 总和必须为 100%（允许 1% 误差） |
| 风险披露 | 20 分 | 每只基金必须有具体风险警告 |
| 风险匹配 | 25 分 | 推荐符合用户风险等级 |
| 免责声明 | 10 分 | 必须包含免责声明 |

#### 风险等级匹配规则

| 风险等级 | 允许基金类型 | 禁止类型 | 特殊要求 |
|:--------:|:-----------|:--------|:---------|
| 保守型 | 债券型、货币型、固收 + | 股票型、行业主题、创业板、科创板 | - |
| 稳健型 | 债券型、混合型、固收 +、指数型 | - | - |
| 积极型 | 混合型、股票型、指数型、债券型 | - | - |
| 激进型 | 股票型、混合型、指数型、行业型 | - | 必须包含股票型基金 |

#### 重试机制

```
生成推荐 → 验证 → 通过 → 返回
              ↓
           不通过（<60 分）
              ↓
         生成改进建议
              ↓
         重新生成（最多 2 次）
              ↓
         再次验证 → 返回（带警告）
```

#### 验证结果示例

```python
ValidationResult(
    passed=True,
    score=95,
    feedback=["配置比例总和验证通过", "风险披露完整"]
)
```

---

### 8.3 GroupChatManager - 群聊管理器

**职责**: 协调多 Agent 对话流程，集成验证器

#### 对话阶段

| 阶段 | 负责 Agent | 输出 |
|:----|:----------|:-----|
| requirement | RequirementAgent | 用户画像（投资金额、期限、目标、经验） |
| risk | RiskAgent | 风险等级（保守型/稳健型/积极型/激进型） |
| recommendation | FundExpertAgent | 基金推荐（XML 格式） |
| validation | CriticAgent | 验证结果（得分/反馈） |
| complete | - | 完成 |

#### 验证流程集成

```python
async def _generate_and_validate_recommendation(self, retry_count: int = 0) -> str:
    """生成并验证推荐（支持重试）"""
    # 1. 生成推荐
    recommendation = await self.fund_expert_agent.generate_recommendation()

    # 2. 验证推荐
    validation = self.critic_agent.validate(recommendation, profile, risk_level)

    # 3. 验证失败则重新生成（最多 2 次）
    if not validation.passed and retry_count < 2:
        feedback = self.critic_agent.generate_improvement_suggestions(validation)
        return await self._regenerate_with_feedback(feedback, retry_count + 1)

    # 4. 返回结果
    return recommendation + f"\n\n【验证通过】得分：{validation.score:.0f}/100"
```

---

## 9. 风险等级动态筛选策略

### 筛选条件配置

| 风险等级 | 基金类型 | 最大回撤 | 波动率 | 最低评级 | 规模要求 |
|:--------:|:--------|:--------:|:------:|:--------:|:--------|
| 保守型 | 债券型 | <5% | <3% | 3 星 | 2-500 亿 |
| 稳健型 | 混合型 | <10% | <8% | 3 星 | 2-500 亿 |
| 积极型 | 混合型 | <20% | <15% | 2 星 | 2-500 亿 |
| 激进型 | 股票型 | <50% | <30% | 无要求 | 2-500 亿 |

### 筛选流程

```
1. 获取基金排行榜（按基金类型）
       ↓
2. 批量获取缓存数据（规模、评级、风险指标）
       ↓
3. 应用筛选条件：
   - 近 1 年收益 > 0
   - 最大回撤 < 阈值
   - 波动率 < 阈值
   - 评级 >= 最低要求
   - 2 亿 < 规模 < 500 亿
       ↓
4. 按近 1 年收益排序，取前 50 只
       ↓
5. 异步预加载规模数据（后台任务）
```

---

## 10. 版本历史

| 版本 | 日期 | 变更内容 |
|:----:|:----:|:---------|
| v0.1.0 | 2025-02 | 初始版本，多 Agent 架构 + AKShare 数据源 |
| v0.1.1 | 2025-02 | 新增基金规模数据、data_loader 工具 |
| v0.2.0 | 2026-02 | **性能增强版**：<br>• Chain of Thought 推理框架<br>• XML 结构化输出<br>• Critic Agent 验证器<br>• 风险等级动态筛选<br>• 数据维度从 7 项扩展到 13+ 项<br>• 降低 temperature 提高一致性 |
