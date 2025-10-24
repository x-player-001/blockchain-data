# 爬取更新逻辑说明

## 功能概述

每10分钟爬取 DexScreener 涨幅榜，对于已存在的代币，智能更新数据库字段，只保留最高涨幅记录。

## 更新策略

### 情况1: 代币不存在
- **操作**: 创建新记录
- **保存字段**:
  - `scraped_price_usd`: 爬取时价格
  - `price_change_24h_at_scrape`: 24h涨幅
  - `market_cap_at_scrape`: 市值
  - `liquidity_at_scrape`: 流动性
  - `volume_24h_at_scrape`: 24h交易量
  - `scraped_timestamp`: 爬取时间

### 情况2: 代币已存在 + 新涨幅 > 原涨幅
- **操作**: 更新所有爬取字段
- **更新字段**: 所有 `*_at_scrape` 字段
- **日志**: `🔄 Updated {symbol}: 涨幅从 X% → Y%`

### 情况3: 代币已存在 + 新涨幅 <= 原涨幅
- **操作**: 跳过更新，保留原记录
- **原因**: 保持最高涨幅记录，追踪代币的历史最高表现
- **日志**: `⏭️  {symbol} 涨幅未提高 (当前: X%, 最高: Y%)`

## 代码实现

### 核心逻辑 ([token_monitor_service.py](src/services/token_monitor_service.py#L859-L885))

```python
# 检查代币是否已存在
existing = await session.execute(
    select(PotentialToken).where(
        PotentialToken.pair_address == pair_address
    )
).scalar_one_or_none()

if existing:
    old_change = existing.price_change_24h_at_scrape or 0

    # 涨幅比较
    if price_change_24h > old_change:
        # 更新所有字段
        existing.scraped_price_usd = price_usd
        existing.scraped_timestamp = datetime.utcnow()
        existing.market_cap_at_scrape = market_cap
        existing.liquidity_at_scrape = liquidity_usd
        existing.volume_24h_at_scrape = volume_24h
        existing.price_change_24h_at_scrape = price_change_24h

        logger.info(f"🔄 Updated {symbol}: {old_change}% → {price_change_24h}%")
    else:
        # 跳过更新
        logger.info(f"⏭️  {symbol} 涨幅未提高")
else:
    # 创建新记录
    potential_token = PotentialToken(...)
    session.add(potential_token)
```

## 测试验证

### 测试脚本: [test_scrape_update.py](test_scrape_update.py)

```bash
python3 test_scrape_update.py
```

### 测试结果

```
【步骤2】模拟爬取更高涨幅数据
  数据库涨幅: 50.00%
  爬取涨幅: 100.0%
  ✅ 涨幅更高，已更新: 50.00% → 100.0%

【步骤4】模拟爬取更低涨幅数据
  数据库涨幅: 100.00%
  爬取涨幅: 80.0%
  ⏭️  涨幅未提高（80.0% <= 100.00%），跳过更新
```

## 使用场景示例

### 场景1: 代币持续上涨

```
时间      爬取涨幅    数据库涨幅    操作
10:00     100%        -           创建记录 (100%)
10:10     150%        100%        更新 → 150%
10:20     200%        150%        更新 → 200%
10:30     180%        200%        跳过（未超过200%）
10:40     250%        200%        更新 → 250%
```

**结果**: 数据库始终保存最高涨幅 250%

### 场景2: 代币涨幅回落

```
时间      爬取涨幅    数据库涨幅    操作
10:00     500%        -           创建记录 (500%)
10:10     300%        500%        跳过（未超过500%）
10:20     200%        500%        跳过（未超过500%）
10:30     150%        500%        跳过（未超过500%）
```

**结果**: 数据库保留峰值涨幅 500%，追踪历史最佳表现

## 优势

1. **追踪历史最高表现**: 保留代币的峰值涨幅数据
2. **减少无效更新**: 涨幅回落时不更新，节省数据库写入
3. **完整记录**: 每次涨幅突破都会更新所有相关字段
4. **可追溯**: `scraped_timestamp` 记录最高涨幅的时间

## 定时任务配置

### Scheduler Daemon ([scheduler_daemon.py](scheduler_daemon.py))

```python
# 每10分钟爬取一次
scheduler.add_job(
    scrape_dexscreener_task,
    trigger=IntervalTrigger(minutes=10),
    id='scrape_dexscreener',
    name='爬取DexScreener首页',
    max_instances=1,
    coalesce=True
)
```

### 任务函数

```python
async def scrape_dexscreener_task():
    result = await monitor_service.scrape_and_save_to_potential(
        count=100,      # 爬取100个代币
        top_n=10,       # 取前10名涨幅榜
        headless=True   # 无头模式
    )

    logger.info(
        f"爬取完成：共爬取 {result['scraped']} 个代币，"
        f"保存 {result['saved']} 个到数据库"
    )
```

## 数据流程

```
┌─────────────────────────────────────────────────────────┐
│ 定时任务: 每10分钟爬取 DexScreener                        │
└─────────────────────────────────────────────────────────┘
                    ↓
        爬取 BSC 链涨幅榜 Top 10
                    ↓
    ┌───────────────┴───────────────┐
    │                               │
代币不存在                      代币已存在
    │                               │
创建新记录                   比较涨幅
(涨幅 X%)                        │
    │                    ┌─────────┴─────────┐
    │                    │                   │
    │             新涨幅 > 原涨幅      新涨幅 <= 原涨幅
    │                    │                   │
    │              更新所有字段           跳过更新
    │              (涨幅 Y%)            (保留原涨幅 Z%)
    │                    │                   │
    └────────────────────┴───────────────────┘
                    ↓
          potential_tokens 表
       （保存历史最高涨幅记录）
```

## API 接口

### 获取潜力代币列表

```bash
GET /api/potential-tokens?limit=100

# 响应示例
{
  "total": 9,
  "data": [
    {
      "token_symbol": "比心",
      "scraped_price_usd": 0.001318,
      "price_change_24h_at_scrape": 975.0,  // 历史最高涨幅
      "scraped_timestamp": "2025-10-23T01:38:03",
      "market_cap_at_scrape": 5000000.0,
      "is_added_to_monitoring": 0
    }
  ]
}
```

## 监控和日志

### 日志示例

```
[INFO] 【爬取潜力币种】保存到 potential_tokens 表
[INFO] ✅ Added NEWTOKEN to potential_tokens (+500.0%)
[INFO] 🔄 Updated 比心: 涨幅从 900.0% → 975.0% (+75.0%)
[INFO] ⏭️  GENESIS 涨幅未提高 (当前: 800.0%, 最高: 837.0%)
[INFO] ✅ Saved to potential_tokens: 8 added/updated, 2 skipped
```

### 查看定时任务日志

```bash
tail -f /tmp/blockchain-scheduler.log
```

## 注意事项

1. **涨幅基准**: 以 DexScreener 的 24h 涨幅为准
2. **唯一标识**: 使用 `pair_address` 作为唯一标识
3. **时间戳**: `scraped_timestamp` 记录最后一次涨幅突破的时间
4. **数据一致性**: 更新时所有 `*_at_scrape` 字段同步更新

## 相关文件

- 核心逻辑: [src/services/token_monitor_service.py#L790-L922](src/services/token_monitor_service.py#L790-L922)
- 定时任务: [scheduler_daemon.py](scheduler_daemon.py)
- 测试脚本: [test_scrape_update.py](test_scrape_update.py)
- 数据模型: [src/storage/models.py](src/storage/models.py)
