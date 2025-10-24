# BSC 链上代币数据抓取分析系统 - 开发指南

## 项目概述

本项目是一个基于 Python 的 BSC（Binance Smart Chain）链上代币数据抓取和分析系统，用于实时监控和分析市值超过 1M 的代币。

## 技术架构

### 核心技术栈

- **Python 3.9+**: 主要开发语言
- **Web3.py**: BSC 链交互
- **aiohttp**: 异步 HTTP 请求
- **pandas**: 数据分析和处理
- **SQLAlchemy**: ORM 数据库操作
- **PostgreSQL/SQLite**: 数据存储
- **APScheduler**: 定时任务调度
- **python-dotenv**: 环境变量管理

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        应用层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  CLI 工具   │  │  数据分析   │  │  导出报告   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                       业务逻辑层                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 数据收集器  │  │ 数据分析器  │  │ 筛选过滤器  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                       数据访问层                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 数据库管理  │  │ 缓存管理    │  │ API 客户端  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                       外部服务层                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │DexScreener  │  │GeckoTerminal│  │  BSC Node   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## 项目结构

```
blockchain-data/
├── src/
│   ├── __init__.py
│   ├── main.py                      # 主入口
│   │
│   ├── collectors/                  # 数据收集器模块
│   │   ├── __init__.py
│   │   ├── base_collector.py       # 基础收集器抽象类
│   │   ├── dex_collector.py        # DEX 数据收集器
│   │   ├── chain_collector.py      # 链上数据收集器
│   │   └── price_collector.py      # 价格数据收集器
│   │
│   ├── analyzers/                   # 数据分析模块
│   │   ├── __init__.py
│   │   ├── market_analyzer.py      # 市值分析
│   │   ├── liquidity_analyzer.py   # 流动性分析
│   │   └── trend_analyzer.py       # 趋势分析
│   │
│   ├── filters/                     # 数据过滤模块
│   │   ├── __init__.py
│   │   ├── market_cap_filter.py    # 市值过滤器
│   │   └── volume_filter.py        # 交易量过滤器
│   │
│   ├── storage/                     # 数据存储模块
│   │   ├── __init__.py
│   │   ├── db_manager.py           # 数据库管理
│   │   ├── models.py               # 数据模型
│   │   └── cache_manager.py        # 缓存管理
│   │
│   ├── api_clients/                 # API 客户端模块
│   │   ├── __init__.py
│   │   ├── dexscreener_client.py   # DexScreener API
│   │   ├── geckoterminal_client.py # GeckoTerminal API
│   │   └── bscscan_client.py       # BSCScan API
│   │
│   ├── utils/                       # 工具函数模块
│   │   ├── __init__.py
│   │   ├── logger.py               # 日志工具
│   │   ├── config.py               # 配置管理
│   │   └── helpers.py              # 辅助函数
│   │
│   └── scheduler/                   # 任务调度模块
│       ├── __init__.py
│       └── task_scheduler.py       # 定时任务
│
├── config/
│   ├── config.yaml                  # 配置文件
│   └── logging.yaml                 # 日志配置
│
├── data/                            # 数据目录
│   ├── cache/                       # 缓存数据
│   └── exports/                     # 导出数据
│
├── tests/                           # 测试目录
│   ├── __init__.py
│   ├── test_collectors.py
│   └── test_analyzers.py
│
├── scripts/                         # 脚本目录
│   ├── setup_db.py                 # 数据库初始化
│   └── export_data.py              # 数据导出
│
├── .env.example                     # 环境变量示例
├── .gitignore
├── requirements.txt                 # 依赖包
├── README.md                        # 项目说明
├── DEVELOPMENT_GUIDE.md            # 开发指南（本文档）
└── setup.py                         # 安装配置
```

## 数据模型设计

### Token 表（代币基本信息）

```python
Token:
  - id: UUID (主键)
  - address: String (合约地址，唯一索引)
  - name: String (代币名称)
  - symbol: String (代币符号)
  - decimals: Integer (小数位数)
  - total_supply: BigInteger (总供应量)
  - created_at: DateTime
  - updated_at: DateTime
```

### TokenMetrics 表（代币指标）

```python
TokenMetrics:
  - id: UUID (主键)
  - token_id: UUID (外键)
  - timestamp: DateTime (索引)
  - price_usd: Decimal (美元价格)
  - market_cap: Decimal (市值)
  - liquidity_usd: Decimal (流动性)
  - volume_24h: Decimal (24小时交易量)
  - price_change_24h: Decimal (24小时价格变化%)
  - holders_count: Integer (持有者数量)
  - transactions_24h: Integer (24小时交易次数)
```

### TokenPair 表（交易对信息）

```python
TokenPair:
  - id: UUID (主键)
  - token_id: UUID (外键)
  - dex_name: String (DEX名称，如 PancakeSwap)
  - pair_address: String (交易对地址)
  - base_token: String (基础代币，如 WBNB)
  - liquidity_usd: Decimal (流动性)
  - volume_24h: Decimal (24小时交易量)
  - created_at: DateTime
```

## 核心功能模块说明

### 1. 数据收集器（Collectors）

#### DexScreener Collector
- 功能：从 DexScreener API 获取代币数据
- API 端点：
  - `https://api.dexscreener.com/latest/dex/search?q={chain}`
  - `https://api.dexscreener.com/latest/dex/tokens/{tokenAddress}`
- 数据：价格、市值、流动性、24h交易量

#### GeckoTerminal Collector
- 功能：从 GeckoTerminal API 获取代币数据
- API 端点：
  - `https://api.geckoterminal.com/api/v2/networks/bsc/tokens`
  - `https://api.geckoterminal.com/api/v2/networks/bsc/tokens/{address}`
- 数据：价格、市值、交易对信息

#### Chain Collector
- 功能：直接从 BSC 链读取数据
- 使用 Web3.py 调用合约方法
- 数据：总供应量、持有者余额、合约验证状态

### 2. 数据分析器（Analyzers）

#### Market Analyzer
- 市值排名
- 市值增长率
- 市值分布统计

#### Liquidity Analyzer
- 流动性健康度评分
- 流动性/市值比率
- 流动性集中度

#### Trend Analyzer
- 价格趋势识别
- 交易量趋势
- 异常检测

### 3. 数据过滤器（Filters）

#### Market Cap Filter
- 筛选市值 > 1M 的代币
- 支持自定义市值范围
- 支持多条件组合过滤

#### Volume Filter
- 按24h交易量过滤
- 流动性阈值过滤
- 活跃度过滤

## API 使用说明

### DexScreener API

**优点：**
- 免费无需 API key
- 数据更新快（实时）
- 覆盖多个 DEX

**限制：**
- 请求频率限制：300 请求/分钟

**示例请求：**
```python
import aiohttp

async def get_token_data(token_address):
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

### GeckoTerminal API

**优点：**
- 免费无需 API key
- 数据结构清晰
- 支持分页和筛选

**限制：**
- 请求频率限制：30 请求/分钟

**示例请求：**
```python
async def get_bsc_tokens(page=1):
    url = f"https://api.geckoterminal.com/api/v2/networks/bsc/tokens?page={page}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

### BSCScan API

**优点：**
- 官方 API，数据权威
- 支持合约源码查询
- 支持持有者信息

**限制：**
- 需要免费 API key
- 请求频率限制：5 请求/秒

**获取 API Key：**
1. 访问 https://bscscan.com/apis
2. 注册账号
3. 创建 API key

## 开发流程

### Phase 1: 基础设施搭建（第1-2天）
- [x] 项目结构初始化
- [ ] 配置管理系统
- [ ] 日志系统
- [ ] 数据库模型设计
- [ ] 数据库初始化脚本

### Phase 2: 数据收集实现（第3-5天）
- [ ] API 客户端基础类
- [ ] DexScreener 客户端
- [ ] GeckoTerminal 客户端
- [ ] 数据收集器实现
- [ ] 错误处理和重试机制

### Phase 3: 数据存储（第6-7天）
- [ ] 数据库管理器
- [ ] 缓存管理器
- [ ] 数据持久化逻辑
- [ ] 数据更新策略

### Phase 4: 数据分析（第8-10天）
- [ ] 市值分析器
- [ ] 流动性分析器
- [ ] 趋势分析器
- [ ] 数据可视化

### Phase 5: 任务调度（第11-12天）
- [ ] 定时任务调度器
- [ ] 数据更新任务
- [ ] 监控告警

### Phase 6: 测试和优化（第13-14天）
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能优化
- [ ] 文档完善

## 环境配置

### 必需的环境变量

```bash
# BSC 节点配置
BSC_RPC_URL=https://bsc-dataseed.binance.org/

# API Keys
BSCSCAN_API_KEY=your_api_key_here

# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/blockchain_data
# 或使用 SQLite（开发环境）
# DATABASE_URL=sqlite:///data/blockchain_data.db

# 缓存配置
REDIS_URL=redis://localhost:6379/0  # 可选

# 应用配置
LOG_LEVEL=INFO
UPDATE_INTERVAL=300  # 秒
MIN_MARKET_CAP=1000000  # 美元
```

### 依赖安装

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

## 使用示例

### 基本使用

```python
from src.main import BlockchainDataApp

# 初始化应用
app = BlockchainDataApp()

# 启动数据收集
await app.start_collection()

# 获取市值 > 1M 的代币
tokens = await app.get_tokens_by_market_cap(min_cap=1_000_000)

# 分析代币
analysis = await app.analyze_token(token_address)
```

### CLI 使用

```bash
# 启动数据收集服务
python -m src.main collect --interval 300

# 查询代币
python -m src.main query --min-market-cap 1000000

# 导出数据
python -m src.main export --format csv --output data/exports/tokens.csv

# 分析代币
python -m src.main analyze --address 0x...
```

## 性能优化建议

### 1. 并发请求
- 使用 `aiohttp` 进行异步 HTTP 请求
- 使用 `asyncio.gather()` 批量处理
- 控制并发数量，避免触发 API 限制

### 2. 缓存策略
- 使用 Redis 缓存热点数据
- 设置合理的过期时间（如 5 分钟）
- 缓存 API 响应，减少重复请求

### 3. 数据库优化
- 为常用查询字段添加索引
- 使用数据库连接池
- 批量插入/更新数据

### 4. 错误处理
- 实现指数退避重试策略
- 记录失败请求，后续补偿
- 监控 API 限制，动态调整请求频率

## 监控和日志

### 日志级别
- DEBUG: 详细的调试信息
- INFO: 常规操作信息
- WARNING: 警告信息（如 API 限制）
- ERROR: 错误信息
- CRITICAL: 严重错误

### 监控指标
- API 请求成功率
- 数据更新延迟
- 数据库查询性能
- 内存和 CPU 使用率

## 安全注意事项

1. **API Key 安全**
   - 不要将 API key 提交到代码仓库
   - 使用环境变量或密钥管理服务

2. **数据验证**
   - 验证 API 返回的数据格式
   - 防止 SQL 注入

3. **速率限制**
   - 遵守 API 提供商的速率限制
   - 实现客户端限流

## 常见问题

### Q1: 如何处理 API 限制？
A: 实现请求队列和速率限制器，使用缓存减少重复请求。

### Q2: 数据更新频率多少合适？
A: 建议 5-10 分钟更新一次，市值变化不会太频繁。

### Q3: 如何保证数据准确性？
A: 从多个数据源获取并交叉验证，记录数据来源和时间戳。

### Q4: 数据库选择 PostgreSQL 还是 SQLite？
A: 开发环境用 SQLite，生产环境用 PostgreSQL。

## 扩展功能建议

1. **价格预警系统**
   - 价格突破提醒
   - 市值变化提醒

2. **历史数据分析**
   - 价格走势图
   - 市值排名变化

3. **智能筛选**
   - 新币发现
   - 异常交易检测

4. **API 服务**
   - 提供 REST API
   - WebSocket 实时推送

5. **Web 仪表板**
   - 数据可视化
   - 实时监控面板

## 参考资源

- [Web3.py 文档](https://web3py.readthedocs.io/)
- [DexScreener API 文档](https://docs.dexscreener.com/)
- [GeckoTerminal API 文档](https://www.geckoterminal.com/docs/api)
- [BSCScan API 文档](https://docs.bscscan.com/)
- [Pandas 文档](https://pandas.pydata.org/docs/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交���改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License

---

**最后更新**: 2025-10-12
**文档版本**: 1.0.0
