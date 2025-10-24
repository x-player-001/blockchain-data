# Blockchain Data API 文档

## 概述

这是一个基于 FastAPI 的 REST API 服务，用于查询 BSC 区块链上的代币和市场数据。

## 快速开始

### 启动服务

```bash
python run_api.py
```

服务将在 `http://localhost:8888` 启动。

### 访问文档

- **Swagger UI**: http://localhost:8888/docs
- **ReDoc**: http://localhost:8888/redoc

## API 端点

### 1. 获取代币列表

**GET** `/api/tokens`

获取分页的代币列表，支持多种过滤条件。

**查询参数:**
- `page` (int): 页码，从1开始，默认值：1
- `page_size` (int): 每页数量，范围1-100，默认值：20
- `data_source` (string, 可选): 数据来源过滤（如 "ave", "legacy"）
- `min_market_cap` (float, 可选): 最小市值（美元）
- `symbol` (string, 可选): 代币符号过滤

**示例请求:**
```bash
curl "http://localhost:8888/api/tokens?page=1&page_size=10"
curl "http://localhost:8888/api/tokens?data_source=ave&page_size=20"
```

**响应示例:**
```json
{
  "total": 152,
  "page": 1,
  "page_size": 10,
  "data": [
    {
      "id": "uuid",
      "address": "0x55d398326f99059ff775485246999027b3197955",
      "name": "Binance-Peg BSC-USD",
      "symbol": "USDT",
      "decimals": 18,
      "total_supply": "6784993699",
      "data_source": "ave",
      "created_at": "2025-10-13T03:17:24.070598",
      "updated_at": "2025-10-16T05:25:07.305915"
    }
  ]
}
```

### 2. 获取代币详情

**GET** `/api/tokens/{address}`

根据合约地址获取单个代币的详细信息。

**路径参数:**
- `address` (string): 代币合约地址

**示例请求:**
```bash
curl "http://localhost:8888/api/tokens/0x55d398326f99059ff775485246999027b3197955"
```

**响应示例:**
```json
{
  "id": "uuid",
  "address": "0x55d398326f99059ff775485246999027b3197955",
  "name": "Binance-Peg BSC-USD",
  "symbol": "USDT",
  "decimals": 18,
  "total_supply": "6784993699",
  "data_source": "ave",
  "created_at": "2025-10-13T03:17:24.070598",
  "updated_at": "2025-10-16T05:25:07.305915"
}
```

### 3. 获取 OHLCV（K线）数据

**GET** `/api/tokens/{address}/ohlcv`

获取指定代币的 OHLCV（开高低收量）历史数据。

**路径参数:**
- `address` (string): 代币合约地址

**查询参数:**
- `interval` (string, 可选): 时间间隔，如 "1h", "4h", "day"，默认值："1d"
- `limit` (int): 返回的K线数量，范围1-1000，默认值：100

**示例请求:**
```bash
curl "http://localhost:8888/api/tokens/0x55d398326f99059ff775485246999027b3197955/ohlcv?limit=10&interval=day"
```

**响应示例:**
```json
[
  {
    "token_id": "uuid",
    "token_address": "0x55d398326f99059ff775485246999027b3197955",
    "timestamp": "2025-10-11T08:00:00",
    "open_price": 1.00808787580772,
    "high_price": 1.02435096363721,
    "low_price": 0.986847570808808,
    "close_price": 1.00119158485889,
    "volume": 1352083040.96,
    "interval": "day"
  }
]
```

### 4. 搜索代币

**GET** `/api/search`

按名称、符号或地址搜索代币。

**查询参数:**
- `q` (string, 必需): 搜索关键词
- `page` (int): 页码，默认值：1
- `page_size` (int): 每页数量，默认值：20

**示例请求:**
```bash
curl "http://localhost:8888/api/search?q=USDT"
curl "http://localhost:8888/api/search?q=0x55d398"
```

**响应示例:**
```json
{
  "total": 8,
  "page": 1,
  "page_size": 20,
  "data": [
    {
      "id": "uuid",
      "address": "0x55d398326f99059ff775485246999027b3197955",
      "name": "Binance-Peg BSC-USD",
      "symbol": "USDT",
      "decimals": 18,
      "total_supply": "6784993699",
      "data_source": "ave",
      "created_at": "2025-10-13T03:17:24.070598",
      "updated_at": "2025-10-16T05:25:07.305915"
    }
  ]
}
```

### 5. 获取统计信息

**GET** `/api/stats`

获取数据库的统计信息，包括各数据源的代币数量和 OHLCV 记录数。

**示例请求:**
```bash
curl "http://localhost:8888/api/stats"
```

**响应示例:**
```json
{
  "total_tokens": 152,
  "total_ohlcv": 309,
  "sources": [
    {
      "source": "ave",
      "token_count": 91,
      "ohlcv_count": 199
    }
  ],
  "updated_at": "2025-10-18T10:15:55.628366"
}
```

### 6. 健康检查

**GET** `/health`

检查 API 服务是否正常运行。

**示例请求:**
```bash
curl "http://localhost:8888/health"
```

**响应示例:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-18T10:00:00.000000"
}
```

## 错误响应

所有端点在出错时返回统一的错误格式：

```json
{
  "detail": "错误描述信息"
}
```

常见 HTTP 状态码：
- `200` - 成功
- `404` - 未找到资源
- `422` - 请求参数验证失败
- `500` - 服务器内部错误

## CORS 配置

API 默认允许所有来源的跨域请求。在生产环境中，建议在 [app.py](src/api/app.py) 中配置具体的允许域名。

## 技术栈

- **FastAPI**: 现代化的 Python Web 框架
- **Uvicorn**: ASGI 服务器
- **SQLAlchemy**: ORM 数据库操作
- **PostgreSQL**: 数据库
- **Pydantic**: 数据验证和序列化

## 项目结构

```
src/api/
├── __init__.py
├── app.py          # FastAPI 应用主文件
├── schemas.py      # Pydantic 数据模型
└── services.py     # 业务逻辑和数据库查询

run_api.py          # API 服务启动脚本
```

## 开发建议

### 前端集成示例

**JavaScript/TypeScript:**
```javascript
// 获取代币列表
const response = await fetch('http://localhost:8888/api/tokens?page=1&page_size=20');
const data = await response.json();
console.log(data.data); // 代币数组

// 搜索代币
const searchResponse = await fetch('http://localhost:8888/api/search?q=USDT');
const searchData = await searchResponse.json();

// 获取 K线数据
const ohlcvResponse = await fetch(
  'http://localhost:8888/api/tokens/0x55d398326f99059ff775485246999027b3197955/ohlcv?interval=day&limit=30'
);
const ohlcvData = await ohlcvResponse.json();
```

**Python:**
```python
import requests

# 获取代币列表
response = requests.get('http://localhost:8888/api/tokens', params={
    'page': 1,
    'page_size': 20,
    'data_source': 'ave'
})
tokens = response.json()

# 获取统计信息
stats = requests.get('http://localhost:8888/api/stats').json()
print(f"总代币数: {stats['total_tokens']}")
```

## 性能优化建议

1. **缓存**: 考虑使用 Redis 缓存常用查询结果
2. **分页**: 始终使用分页参数，避免一次性获取大量数据
3. **索引**: 数据库已在常用字段上建立索引（address, timestamp等）
4. **连接池**: SQLAlchemy 自动管理数据库连接池

## 后续扩展

可以考虑添加的功能：
- 认证和授权（API Key）
- 速率限制
- WebSocket 实时数据推送
- 更多数据源集成
- 数据聚合和分析端点
- 导出功能（CSV, JSON）

## 支持

如有问题，请查看：
- Swagger 文档: http://localhost:8888/docs
- ReDoc 文档: http://localhost:8888/redoc
