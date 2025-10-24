# DexScreener API 使用文档

本文档介绍如何使用 DexScreener 代币数据的 API 接口。

## 📋 目录

- [数据导入](#数据导入)
- [API 端点](#api-端点)
- [使用示例](#使用示例)
- [数据字段说明](#数据字段说明)

## 数据导入

### 1. 创建数据库表

```bash
python3 -c "
import asyncio
from src.storage.db_manager import DatabaseManager

async def init():
    db = DatabaseManager()
    await db.init_async_db()
    await db.close()

asyncio.run(init())
"
```

### 2. 导入 DexScreener 数据

```bash
python3 -m src.scripts.import_dexscreener_tokens dexscreener_tokens.json
```

导入脚本会：
- 解析 JSON 文件中的代币数据
- 自动提取所有字段（价格、交易量、流动性等）
- 批量插入到 `dexscreener_tokens` 表
- 支持更新已存在的记录

### 3. 去重代币数据

如果同一个代币有多个交易对，可以运行去重脚本，只保留流动性最大的交易对：

```bash
# 预览模式（不实际删除）
python3 -m src.scripts.deduplicate_tokens

# 执行删除
python3 -m src.scripts.deduplicate_tokens --execute
```

去重脚本会：
- 识别所有有多个交易对的代币
- 对每个代币，保留流动性（liquidity_usd）最大的交易对
- 删除其他低流动性的重复交易对
- 确保数据库中每个代币只有一条记录

## API 端点

### 1. 获取代币列表

**端点:** `GET /api/dexscreener/tokens`

**参数:**
- `page` - 页码（默认: 1）
- `page_size` - 每页数量（默认: 20，最大: 100）
- `chain_id` - 链ID过滤（如: bsc, eth）
- `dex_id` - DEX过滤（如: pancakeswap, uniswap）
- `min_liquidity` - 最小流动性（USD）
- `min_market_cap` - 最小市值（USD）
- `symbol` - 代币符号过滤
- `sort_by` - 排序字段（market_cap, liquidity_usd, volume_h24, price_change_h24）
- `sort_order` - 排序方向（asc, desc）

**示例:**
```bash
# 获取前20个代币（按市值降序）
curl "http://localhost:8888/api/dexscreener/tokens?page=1&page_size=20"

# 筛选 BSC 链上 PancakeSwap 的代币，市值 > 1M
curl "http://localhost:8888/api/dexscreener/tokens?chain_id=bsc&dex_id=pancakeswap&min_market_cap=1000000"

# 按24小时交易量排序
curl "http://localhost:8888/api/dexscreener/tokens?sort_by=volume_h24&sort_order=desc"
```

### 2. 获取交易对详情

**端点:** `GET /api/dexscreener/pairs/{pair_address}`

**参数:**
- `pair_address` - 交易对地址

**示例:**
```bash
curl "http://localhost:8888/api/dexscreener/pairs/0x1e40450F8E21BB68490D7D91Ab422888Fb3D60f1"
```

### 3. 搜索代币

**端点:** `GET /api/dexscreener/search`

**参数:**
- `q` - 搜索关键词（支持名称、符号、地址）
- `page` - 页码（默认: 1）
- `page_size` - 每页数量（默认: 20）

**示例:**
```bash
# 搜索 USDT
curl "http://localhost:8888/api/dexscreener/search?q=USDT"

# 搜索 Cake
curl "http://localhost:8888/api/dexscreener/search?q=CAKE&page_size=10"
```

## 使用示例

### Python 示例

```python
import requests

# 1. 获取市值前10的代币
response = requests.get(
    'http://localhost:8888/api/dexscreener/tokens',
    params={
        'page': 1,
        'page_size': 10,
        'sort_by': 'market_cap',
        'sort_order': 'desc'
    }
)
data = response.json()
print(f"总共 {data['total']} 个代币")
for token in data['data']:
    print(f"{token['base_token_symbol']}: ${token['market_cap']:,.2f}")

# 2. 搜索 USDT 相关代币
response = requests.get(
    'http://localhost:8888/api/dexscreener/search',
    params={'q': 'USDT', 'page_size': 5}
)
results = response.json()
print(f"\n找到 {results['total']} 个 USDT 相关代币")

# 3. 获取特定交易对详情
pair_address = "0x1e40450F8E21BB68490D7D91Ab422888Fb3D60f1"
response = requests.get(
    f'http://localhost:8888/api/dexscreener/pairs/{pair_address}'
)
pair_data = response.json()
print(f"\n交易对: {pair_data['base_token_symbol']}/{pair_data['quote_token_symbol']}")
print(f"价格: ${pair_data['price_usd']}")
print(f"24h交易量: ${pair_data['volume_h24']:,.2f}")
```

### JavaScript/TypeScript 示例

```typescript
// 1. 获取代币列表
async function getTokens() {
  const response = await fetch(
    'http://localhost:8888/api/dexscreener/tokens?page=1&page_size=20'
  );
  const data = await response.json();
  return data.data;
}

// 2. 搜索代币
async function searchToken(query: string) {
  const response = await fetch(
    `http://localhost:8888/api/dexscreener/search?q=${query}`
  );
  const data = await response.json();
  return data.data;
}

// 3. 获取交易对详情
async function getPairDetail(pairAddress: string) {
  const response = await fetch(
    `http://localhost:8888/api/dexscreener/pairs/${pairAddress}`
  );
  return await response.json();
}

// 使用示例
const tokens = await getTokens();
console.log(`获取到 ${tokens.length} 个代币`);

const usdtTokens = await searchToken('USDT');
console.log(`找到 ${usdtTokens.length} 个 USDT 相关代币`);
```

### cURL 示例

```bash
# 获取流动性最高的5个代币
curl -X GET "http://localhost:8888/api/dexscreener/tokens?sort_by=liquidity_usd&sort_order=desc&page_size=5" \
  -H "Accept: application/json" | jq '.data[] | {symbol: .base_token_symbol, liquidity: .liquidity_usd}'

# 获取24小时涨幅最大的代币
curl -X GET "http://localhost:8888/api/dexscreener/tokens?sort_by=price_change_h24&sort_order=desc&page_size=10" \
  -H "Accept: application/json" | jq '.data[] | {symbol: .base_token_symbol, change: .price_change_h24}'

# 筛选特定DEX和链
curl -X GET "http://localhost:8888/api/dexscreener/tokens?chain_id=bsc&dex_id=pancakeswap&min_liquidity=10000" \
  -H "Accept: application/json"
```

## 数据字段说明

### 响应数据结构

```json
{
  "total": 100,          // 总数量
  "page": 1,             // 当前页码
  "page_size": 20,       // 每页数量
  "data": [...]          // 代币数据数组
}
```

### 代币数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 数据库记录ID |
| `chain_id` | string | 链ID（如: bsc, eth） |
| `dex_id` | string | DEX ID（如: pancakeswap） |
| `pair_address` | string | 交易对地址 |
| `base_token_address` | string | 代币合约地址 |
| `base_token_name` | string | 代币名称 |
| `base_token_symbol` | string | 代币符号 |
| `quote_token_address` | string | 报价代币地址 |
| `quote_token_symbol` | string | 报价代币符号 |
| `price_native` | float | 原生代币价格 |
| `price_usd` | float | USD价格 |
| `volume_h24` | float | 24小时交易量 |
| `volume_h6` | float | 6小时交易量 |
| `volume_h1` | float | 1小时交易量 |
| `txns_h24_buys` | int | 24小时买入次数 |
| `txns_h24_sells` | int | 24小时卖出次数 |
| `price_change_h24` | float | 24小时价格变化(%) |
| `price_change_h6` | float | 6小时价格变化(%) |
| `price_change_h1` | float | 1小时价格变化(%) |
| `liquidity_usd` | float | 流动性(USD) |
| `market_cap` | float | 市值 |
| `fdv` | float | 完全稀释估值 |
| `dexscreener_url` | string | DexScreener链接 |
| `image_url` | string | 代币图标 |
| `website_url` | string | 官网 |
| `twitter_url` | string | Twitter |
| `telegram_url` | string | Telegram |
| `labels` | string | 标签 |
| `pair_created_at` | int | 交易对创建时间(毫秒时间戳) |
| `created_at` | datetime | 记录创建时间 |
| `updated_at` | datetime | 记录更新时间 |

## API 文档

启动 API 服务后，可以访问：

- **Swagger UI**: http://localhost:8888/docs
- **ReDoc**: http://localhost:8888/redoc

## 常见查询场景

### 1. 查找高流动性代币

```bash
curl "http://localhost:8888/api/dexscreener/tokens?min_liquidity=100000&sort_by=liquidity_usd&sort_order=desc"
```

### 2. 查找潜力币（低市值高交易量）

```bash
curl "http://localhost:8888/api/dexscreener/tokens?min_market_cap=100000&sort_by=volume_h24&sort_order=desc"
```

### 3. 查找价格快速上涨的代币

```bash
curl "http://localhost:8888/api/dexscreener/tokens?sort_by=price_change_h24&sort_order=desc&page_size=20"
```

### 4. 按DEX筛选

```bash
# PancakeSwap 代币
curl "http://localhost:8888/api/dexscreener/tokens?dex_id=pancakeswap"

# Uniswap 代币
curl "http://localhost:8888/api/dexscreener/tokens?dex_id=uniswap"
```

## 错误处理

API 使用标准 HTTP 状态码：

- `200` - 成功
- `404` - 资源未找到
- `500` - 服务器错误

错误响应格式：
```json
{
  "detail": "错误详情",
  "timestamp": "2025-10-20T09:21:13"
}
```

## 性能优化建议

1. **使用分页**: 避免一次请求过多数据
2. **添加过滤条件**: 减少返回的数据量
3. **缓存结果**: 对于不常变化的数据，可以在客户端缓存
4. **批量查询**: 需要多个代币数据时，优先使用列表接口而非多次调用详情接口

## 更新数据

要更新 DexScreener 数据，重新运行导入脚本即可：

```bash
# 如果有新的 JSON 文件
python3 -m src.scripts.import_dexscreener_tokens new_dexscreener_tokens.json
```

导入脚本会自动：
- 更新已存在的交易对数据
- 插入新的交易对数据
- 保留历史数据

---

**最后更新**: 2025-10-20
