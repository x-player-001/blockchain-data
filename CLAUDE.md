# 区块链数据采集系统说明

## 项目概述

本项目是一个区块链代币数据采集和分析系统，主要从 DexScreener 爬取 BSC 和 Solana 链上的代币信息，并提供筛选、存储、监控等功能。

## 数据采集流程

### 1. 爬取方式

系统支持两种爬取方式：

#### undetected-chromedriver（推荐）
- 使用真实浏览器模拟人类行为
- 能够绕过 Cloudflare 防护
- 适合本地开发和测试
- 文件：`src/services/dexscreener_service.py` - `scrape_with_undetected_chrome()`

#### cloudscraper（服务器推荐）
- 无需启动浏览器，资源占用少
- 速度快，适合定时任务
- 支持自动重试机制
- 文件：`src/services/dexscreener_service.py` - `scrape_with_cloudscraper()`

### 2. 数据解析规则

#### BSC 链代币结构
DexScreener 对 BSC 代币使用两种不同的 HTML 结构：

**正常结构**（符号 ≠ 名称）：
```
parts[3] = 代币名称
parts[5] = 基础代币（如 WBNB）
parts[6] = 代币符号
```

**简化结构**（符号 = 名称）：
```
parts[3] = 代币符号（同时也是名称）
parts[5] = 基础代币
parts[6] = 代币名称
parts[7] = $ （价格符号）
```

系统通过检查 `parts[6] == '$'` 来判断使用哪种结构。

#### Solana 链代币结构
Solana 链支持多种 DEX 类型标记：
- CPMM, CLMM, DLMM, DYN, DYN2
- wp, v2, v3

解析时需要识别 DEX 类型并相应调整字段位置。

### 3. 字段解析

#### 价格变化百分比
支持两种格式：

1. **4个连续百分比**（5m, 1h, 6h, 24h）
   - 标准格式，包含 5 分钟涨幅

2. **3个连续百分比**（1h, 6h, 24h）
   - 当 5 分钟数据缺失时（显示为 "-"）
   - 系统会查找 3 个连续的百分比值

#### 代币年龄（Age）
格式：`数字 + 单位`

支持的单位：
- `h` = 小时 (hours)
- `d` = 天 (days)
- `mo` = 月 (months)
- `m` = 月 (months)
- `y` = 年 (years)

示例：
- `17h` → 0.708 天
- `1d` → 1.0 天
- `3mo` → 90.0 天
- `1y` → 365.0 天

正则表达式：`r'^(\d+)(mo|h|d|m|y)$'`

注意：`mo` 必须在 `m` 之前匹配，避免误识别。

存储两个字段：
- `age`: 原始格式字符串（如 "17h"）
- `age_days`: 转换为天数的浮点数（用于筛选）

## 数据筛选逻辑

### 筛选条件

代币必须同时满足以下条件才会被导入数据库：

1. **市值**：`market_cap >= min_market_cap`
   - 默认：$500,000

2. **流动性**：`liquidity_usd >= min_liquidity`
   - 默认：$50,000

3. **代币年龄**：`age_days <= max_age_days`
   - 默认：1 天（24 小时内创建的新币）

4. **24小时涨幅**：必须有数据（`price_change_24h is not None`）

### 筛选流程

```python
# 1. 过滤掉没有24h涨幅的代币
tokens_with_change = [t for t in tokens if t.get('price_change_24h') is not None]

# 2. 应用筛选条件
for token in tokens_with_change:
    if market_cap < min_market_cap:
        continue  # 过滤市值不足
    if liquidity < min_liquidity:
        continue  # 过滤流动性不足
    if age_days > max_age_days:
        continue  # 过滤代币太老

    # 通过所有筛选条件
    filtered_tokens.append(token)
```

## 数据存储

### 数据库表结构

#### trading_pairs（交易对表）
主要字段：
- `pair_address`: 交易对地址（唯一标识）
- `token_symbol`: 代币符号
- `token_name`: 代币名称
- `chain`: 链名称（bsc/solana）
- `price_usd`: 价格（美元）
- `price_change_24h`: 24小时涨跌幅
- `market_cap`: 市值
- `liquidity_usd`: 流动性
- `volume_24h`: 24小时交易量
- `age`: 代币年龄（原始格式）
- `age_days`: 代币年龄（天数）
- `is_active`: 是否活跃
- `created_at`: 创建时间
- `updated_at`: 更新时间

#### klines（K线数据表）
存储历史价格数据：
- `pair_address`: 关联交易对
- `timeframe`: 时间周期（1m, 5m, 15m, 1h, 4h, 1d）
- `timestamp`: 时间戳
- `open`, `high`, `low`, `close`: OHLC 价格
- `volume`: 交易量

### 去重机制

使用 `pair_address` 作为唯一标识：
- 新数据：插入数据库
- 已存在：更新价格、涨幅等动态字段
- 保留：`created_at` 时间戳不变

## 定时任务

### 调度器（scheduler_daemon.py）

系统使用 APScheduler 运行定时任务：

1. **代币数据采集**
   - 间隔：每 30 分钟
   - 任务：爬取新代币 → 筛选 → 导入数据库

2. **K线数据更新**
   - 间隔：每 5 分钟（1m K线）
   - 间隔：每 1 小时（1h, 4h, 1d K线）
   - 任务：为活跃交易对更新 K线数据

3. **监控告警**
   - 实时监控活跃代币价格变化
   - 达到阈值时发送 Telegram 通知

## API 接口

### 主要端点

- `GET /api/pairs` - 获取交易对列表（支持筛选）
- `GET /api/pairs/{pair_address}` - 获取单个交易对详情
- `GET /api/pairs/{pair_address}/klines` - 获取 K线数据
- `POST /api/scraper/run` - 手动触发爬取任务
- `GET /api/scraper/config` - 获取爬虫配置
- `PUT /api/scraper/config` - 更新爬虫配置

详见：`src/routes/` 目录

## 解析修复历史

### 修复记录

以下是已修复的数据解析问题：

#### 1. 月份格式支持（2025-10-27）
**问题**：无法识别 "5mo" 这样的月份格式
**修复**：正则表达式从 `r'^(\d+)([hdmy])$'` 改为 `r'^(\d+)(mo|h|d|m|y)$'`
**效果**：缺失年龄数据从 39 个减少到 1 个

#### 2. 3个百分比格式支持（2025-10-27）
**问题**：当 5 分钟涨幅显示为 "-" 时，只有 3 个百分比值（1h, 6h, 24h）
**修复**：添加对 3 个连续百分比的识别逻辑
**效果**：缺失 24h 涨幅从 13 个减少到 6 个

#### 3. BSC 简化结构支持（2025-10-27）
**问题**：当代币符号等于名称时，DexScreener 使用不同的 HTML 结构，导致符号被解析为 "$"
**修复**：通过检查 `parts[6] == '$'` 来识别简化结构
**效果**：4 个代币（quq, AICell, BNB48 Club Token, Aster）符号正确显示

## 测试

测试脚本位于 `tests/` 目录：

- `test_scraper_filter.py` - 测试爬虫和筛选逻辑
- `test_scraper_save_html.py` - 保存 HTML 用于调试

运行测试：
```bash
python3 tests/test_scraper_filter.py
```

## 配置文件

### .env
```bash
# 数据库配置
DATABASE_URL=postgresql://user:pass@localhost:5432/blockchain_data

# Telegram 通知
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# 爬虫配置
SCRAPER_MIN_MARKET_CAP=500000
SCRAPER_MIN_LIQUIDITY=50000
SCRAPER_MAX_AGE_DAYS=1
```

## 技术栈

- **后端**：Python + FastAPI
- **数据库**：PostgreSQL + TimescaleDB
- **爬虫**：undetected-chromedriver / cloudscraper
- **解析**：BeautifulSoup4
- **调度**：APScheduler
- **通知**：python-telegram-bot

## 文档结构

- `README.md` - 项目基本说明
- `CLAUDE.md` - 本文档（开发说明）
- `SCRAPER_SETUP.md` - 爬虫环境搭建
- `SCRAPE_UPDATE_LOGIC.md` - 数据更新逻辑
- `docs/` - 详细文档目录

## 相关文件

- 爬虫服务：`src/services/dexscreener_service.py`
- 数据库模型：`src/models/trading_pair.py`
- API 路由：`src/routes/`
- 调度器：`scheduler_daemon.py`
- 测试脚本：`tests/`

---

最后更新：2025-10-27
