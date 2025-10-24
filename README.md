# BSC 链上代币数据抓取分析系统

一个基于 Python 的 BSC（Binance Smart Chain）链上代币数据抓取和分析系统，用于实时监控和分析市值超过 1M 的代币。

## 功能特性

- 从多个数据源（AVE API、DexScreener、GeckoTerminal）抓取代币数据
- 自动筛选市值超过指定阈值的代币
- 存储历史数据用于趋势分析（PostgreSQL + TimescaleDB）
- 市场数据分析和报告生成
- **REST API 服务** - 为前端提供数据查询接口
- 美观的命令行界面（CLI）
- 异步高性能数据收集
- 支持 API 速率限制和自动重试

## 项目结构

```
blockchain-data/
├── src/
│   ├── api/                   # REST API 服务
│   │   ├── app.py             # FastAPI 应用
│   │   ├── schemas.py         # 数据模型
│   │   └── services.py        # 业务逻辑
│   ├── api_clients/           # 外部API客户端（AVE、DexScreener等）
│   ├── collectors/            # 数据收集器
│   ├── analyzers/             # 数据分析器
│   ├── filters/               # 数据过滤器
│   ├── storage/               # 数据存储（PostgreSQL）
│   ├── utils/                 # 工具函数
│   └── main.py                # CLI主程序入口
├── docs/                      # 📚 文档目录
│   ├── API_README.md          # API使用文档
│   ├── POSTGRESQL_SETUP.md    # 数据库配置指南
│   ├── DEVELOPMENT_GUIDE.md   # 开发指南
│   └── ...                    # 其他文档
├── run_api.py                 # API服务启动脚本
├── .env                       # 环境变量配置
├── requirements.txt           # 依赖包
└── README.md                  # 项目说明
```

## 📚 文档导航

- **[API 使用文档](docs/API_README.md)** - REST API 接口说明和使用示例
- **[PostgreSQL 配置指南](docs/POSTGRESQL_SETUP.md)** - 数据库安装和配置
- **[开发指南](docs/DEVELOPMENT_GUIDE.md)** - 开发环境搭建和代码规范
- **[Navicat 连接指南](docs/NAVICAT_CONNECTION_GUIDE.md)** - 数据库可视化工具使用
- **[项目总结](docs/PROJECT_SUMMARY.md)** - 项目架构和技术栈
- **[变更日志](docs/CHANGES.md)** - 版本更新记录

## 快速开始

### 1. 环境要求

- Python 3.9 或更高版本
- PostgreSQL 14+ (推荐使用 TimescaleDB 扩展)
- pip 包管理器

### 2. 安装

```bash
# 克隆或进入项目目录
cd blockchain-data

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置数据库

参考 [PostgreSQL 配置指南](docs/POSTGRESQL_SETUP.md) 安装和配置 PostgreSQL。

```bash
# 创建数据库
createdb blockchain_data

# 配置 .env 文件
DATABASE_URL=postgresql://username@localhost:5432/blockchain_data
AVE_API_KEY=your_ave_api_key_here
```

### 4. 运行

#### 启动 API 服务

```bash
# 启动 REST API 服务器
python run_api.py

# 访问 API 文档
# Swagger UI: http://localhost:8888/docs
# ReDoc: http://localhost:8888/redoc
```

#### 使用 CLI 收集数据

```bash
# 从 AVE API 收集代币数据
python -m src.main collect-ave-tokens --min-market-cap 1000000

# 收集 OHLCV（K线）数据
python -m src.main collect-ave-ohlcv

# 对比数据源
python -m src.main compare-sources
```

## 命令详解

### collect - 收集代币数据

从 DEX 聚合器收集代币数据并保存到数据库。

```bash
# 基本用法
python -m src.main collect

# 指定最小市值（例如：500万美元）
python -m src.main collect --min-market-cap 5000000

# 只收集数据，不保存到数据库
python -m src.main collect --no-save
```

### query - 查询代币

从数据库查询符合条件的代币并显示。

```bash
# 查询所有代币
python -m src.main query

# 查询市值大于 500 万的代币
python -m src.main query --min-market-cap 5000000

# 只显示前 10 个结果
python -m src.main query --limit 10

# 组合使用
python -m src.main query --min-market-cap 10000000 --limit 20
```

### analyze - 市场分析

分析市场数据并生成报告。

```bash
# 分析所有代币
python -m src.main analyze

# 分析市值大于 100 万的代币
python -m src.main analyze --min-market-cap 1000000
```

报告包括：
- 代币总数和总市值
- 市值分布统计
- 市值前 10 的代币
- 24 小时涨幅/跌幅前 5 的代币
- 交易量前 10 的代币

### health - 健康检查

检查所有数据源的可用性。

```bash
python -m src.main health
```

### init-db - 初始化数据库

创建数据库表结构。

```bash
python -m src.main init-db
```

## 使用示例

### 示例 1: 每日市场监控

```bash
# 1. 收集最新数据
python -m src.main collect

# 2. 查看市值前 20 的代币
python -m src.main query --limit 20

# 3. 生成市场分析报告
python -m src.main analyze
```

### 示例 2: 筛选高市值代币

```bash
# 只关注市值超过 1000 万的代币
python -m src.main collect --min-market-cap 10000000
python -m src.main query --min-market-cap 10000000
python -m src.main analyze --min-market-cap 10000000
```

### 示例 3: 定时任务

可以使用 cron（Linux/Mac）或任务计划程序（Windows）设置定时收集：

```bash
# crontab 示例：每 5 分钟收集一次数据
*/5 * * * * cd /path/to/blockchain-data && /path/to/venv/bin/python -m src.main collect
```

## 配置说明

### 环境变量

在 `.env` 文件中配置：

```bash
# BSC 节点（使用公共节点即可）
BSC_RPC_URL=https://bsc-dataseed.binance.org/

# BSCScan API Key（可选，用于获取更详细的链上数据）
BSCSCAN_API_KEY=your_api_key_here

# 数据库（开发环境使用 SQLite）
DATABASE_URL=sqlite:///data/blockchain_data.db
# 生产环境建议使用 PostgreSQL
# DATABASE_URL=postgresql://user:password@localhost:5432/blockchain_data

# 应用配置
LOG_LEVEL=INFO                # 日志级别
UPDATE_INTERVAL=300           # 更新间隔（秒）
MIN_MARKET_CAP=1000000        # 最小市值（美元）
MAX_CONCURRENT_REQUESTS=10    # 最大并发请求数

# API 速率限制（每分钟请求数）
DEXSCREENER_RATE_LIMIT=300
GECKOTERMINAL_RATE_LIMIT=30
```

## 数据源

本系统从以下数据源获取数据：

1. **AVE API** (主要数据源)
   - 需要 API Key
   - 支持 50+ 区块链（包括 BSC）
   - 提供代币、OHLCV、实时价格等数据
   - 支持按市值、TVL 过滤
   - 文档：https://ave-cloud.gitbook.io/data-api

2. **DexScreener API**
   - 免费，无需 API key
   - 实时数据，更新频率高
   - 限制：300 请求/分钟

3. **GeckoTerminal API**
   - 免费，无需 API key
   - 数据结构清晰，支持分页
   - 限制：30 请求/分钟

## 数据模型

系统存储以下数据：

### Token（代币基本信息）
- 合约地址
- 代币名称和符号
- 小数位数
- 总供应量

### TokenMetrics（代币指标，时间序列）
- 美元价格
- 市值
- 流动性
- 24 小时交易量
- 24 小时价格变化
- 持有者数量

### TokenPair（交易对信息）
- DEX 名称
- 交易对地址
- 基础代币（WBNB/BUSD）
- 流动性和交易量

## 常见问题

### Q: 数据更新频率是多少？

A: 手动运行 `collect` 命令时会抓取最新数据。建议设置定时任务，每 5-10 分钟更新一次。

### Q: 如何处理 API 限制？

A: 系统内置了速率限制器和自动重试机制。如果遇到限制，会自动等待并重试。

### Q: 数据准确性如何保证？

A: 系统从多个数据源获取数据并进行交叉验证。优先选择流动性最高的交易对数据。

### Q: 如何导出数据？

A: 目前可以通过查询命令查看数据。后续版本会添加 CSV/JSON 导出功能。

### Q: 支持其他链吗？

A: 当前版本只支持 BSC 链。代码结构支持扩展，可以添加其他 EVM 兼容链。

## 性能优化建议

1. **使用 PostgreSQL**：生产环境建议使用 PostgreSQL 替代 SQLite
2. **启用 Redis 缓存**：减少重复 API 请求
3. **调整并发数**：根据网络情况调整 `MAX_CONCURRENT_REQUESTS`
4. **数据清理**：定期清理历史数据，保留最近 30 天的数据

## API 服务

本项目提供完整的 REST API 服务，详见 **[API 使用文档](docs/API_README.md)**

### 主要端点

- `GET /api/tokens` - 获取代币列表（分页、过滤）
- `GET /api/tokens/{address}` - 获取代币详情
- `GET /api/tokens/{address}/ohlcv` - 获取 K线数据
- `GET /api/search` - 搜索代币
- `GET /api/stats` - 获取统计信息

### 示例

```bash
# 获取代币列表
curl "http://localhost:8888/api/tokens?page=1&page_size=20"

# 搜索 USDT
curl "http://localhost:8888/api/search?q=USDT"

# 获取 K线数据
curl "http://localhost:8888/api/tokens/0x55d398326f99059ff775485246999027b3197955/ohlcv?interval=day&limit=30"
```

## 扩展功能建议

- ✅ REST API 服务（已完成）
- 价格预警（价格/市值突破提醒）
- Web 仪表板
- Telegram Bot 集成
- 更多技术指标分析
- 历史数据趋势图表

## 故障排除

### 无法连接数据源

```bash
# 检查网络连接
python -m src.main health

# 查看详细日志
LOG_LEVEL=DEBUG python -m src.main collect
```

### 数据库错误

```bash
# 重新初始化数据库
python -m src.main init-db
```

### 依赖安装问题

```bash
# 升级 pip
pip install --upgrade pip

# 重新安装依赖
pip install -r requirements.txt --force-reinstall
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 技术栈

### 后端
- **Python 3.13** - 主要编程语言
- **FastAPI** - REST API 框架
- **SQLAlchemy 2.0** - ORM 数据库操作
- **PostgreSQL 14+** - 主数据库
- **TimescaleDB** - 时序数据扩展
- **asyncpg** - 异步 PostgreSQL 驱动

### 数据源
- **AVE API** - 主要数据源
- **DexScreener API** - DEX 数据
- **GeckoTerminal API** - 代币市场数据

### 工具
- **Click** - CLI 框架
- **Rich** - 终端美化输出
- **Pydantic** - 数据验证
- **aiohttp** - 异步 HTTP 客户端

## 联系方式

如有问题，请查看 [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) 获取更详细的技术文档。

---

**最后更新**: 2025-10-18
