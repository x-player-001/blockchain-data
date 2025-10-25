# 功能实现状态

## ✅ 已完成

### 1. 数据库层
- ✅ 创建 `scraper_config` 表
- ✅ 添加 `permanently_deleted` 字段到 `monitored_tokens` 和 `potential_tokens`
- ✅ 创建数据库迁移脚本 `migrations/add_scraper_config_and_permanently_deleted.sql`

### 2. API 路由
- ✅ `GET /api/scraper/config` - 获取爬虫配置
- ✅ `PUT /api/scraper/config` - 更新爬虫配置
- ✅ `POST /api/monitor/add-by-pair` - 通过 pair 地址添加监控
- ✅ `DELETE /api/monitor/tokens/{token_id}/permanent` - 彻底删除监控代币
- ✅ `DELETE /api/potential-tokens/{token_id}/permanent` - 彻底删除潜力代币

## 🔄 待实现

### 3. 服务层方法（src/services/token_monitor_service.py）

需要添加以下方法：

#### 方法1: `add_monitoring_by_pair()`
```python
async def add_monitoring_by_pair(
    self,
    pair_address: str,
    chain: str,
    drop_threshold: float = 20.0,
    alert_thresholds: Optional[List[float]] = None
) -> dict:
    """
    通过 pair 地址添加监控代币

    流程：
    1. 调用 AVE API 获取 pair 详细信息
    2. 提取代币信息（symbol, name, price等）
    3. 检查是否已存在监控
    4. 创建 MonitoredToken 记录
    """
    # 1. 调用 AVE API
    pair_data = await self.ave_api.get_pair_details(pair_address, chain)
    if not pair_data:
        raise ValueError(f"无法获取 pair {pair_address} 的信息")

    # 2. 提取信息
    token_address = pair_data.get('token_address')
    token_symbol = pair_data.get('token_symbol')
    token_name = pair_data.get('token_name')
    current_price = pair_data.get('price_usd')

    # 3. 检查是否已存在
    async with self.db.get_session() as session:
        existing = await session.execute(
            select(MonitoredToken).where(
                MonitoredToken.pair_address == pair_address,
                MonitoredToken.permanently_deleted == 0
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("该代币已在监控列表中")

        # 4. 创建记录
        monitored_token = MonitoredToken(
            token_address=token_address,
            token_symbol=token_symbol,
            token_name=token_name,
            chain=chain,
            pair_address=pair_address,
            entry_price_usd=current_price,
            peak_price_usd=current_price,
            current_price_usd=current_price,
            drop_threshold_percent=drop_threshold,
            alert_thresholds=alert_thresholds or [70, 80, 90],
            # ... 填充其他 AVE API 数据
        )
        session.add(monitored_token)
        await session.commit()

    return {"success": True, "message": "已添加到监控"}
```

#### 方法2: `permanently_delete_monitored_token()`
```python
async def permanently_delete_monitored_token(self, token_id: str) -> dict:
    """彻底删除监控代币（设置 permanently_deleted=1）"""
    async with self.db.get_session() as session:
        result = await session.execute(
            select(MonitoredToken).where(MonitoredToken.id == token_id)
        )
        token = result.scalar_one_or_none()

        if not token:
            raise ValueError(f"未找到ID为 {token_id} 的监控代币")

        token.permanently_deleted = 1
        token.deleted_at = datetime.utcnow()
        await session.commit()

    return {"success": True, "message": "已彻底删除"}
```

#### 方法3: `permanently_delete_potential_token()`
```python
async def permanently_delete_potential_token(self, token_id: str) -> dict:
    """彻底删除潜力代币（设置 permanently_deleted=1）"""
    async with self.db.get_session() as session:
        result = await session.execute(
            select(PotentialToken).where(PotentialToken.id == token_id)
        )
        token = result.scalar_one_or_none()

        if not token:
            raise ValueError(f"未找到ID为 {token_id} 的潜力代币")

        token.permanently_deleted = 1
        token.deleted_at = datetime.utcnow()
        await session.commit()

    return {"success": True, "message": "已彻底删除"}
```

### 4. 修改现有查询方法，过滤 permanently_deleted

需要在以下方法中添加过滤条件 `.where(permanently_deleted == 0)`：

- `get_monitored_tokens()` - 第520行
- `get_potential_tokens()` - 第650行
- `get_deleted_monitored_tokens()` - 需要修改，也要过滤 permanently_deleted
- `get_deleted_potential_tokens()` - 需要修改，也要过滤 permanently_deleted

示例：
```python
# 修改前
result = await session.execute(
    select(MonitoredToken).where(MonitoredToken.deleted_at == null)
)

# 修改后
result = await session.execute(
    select(MonitoredToken).where(
        MonitoredToken.deleted_at == null,
        MonitoredToken.permanently_deleted == 0  # 新增
    )
)
```

### 5. 修改 scheduler 读取配置

在 `scheduler_daemon.py` 的 `scrape_dexscreener_task()` 函数中：

```python
async def scrape_dexscreener_task():
    # 1. 从数据库读取配置
    from src.storage.models import ScraperConfig
    from src.storage.db_manager import DatabaseManager
    from sqlalchemy import select

    db = DatabaseManager()
    async with db.get_session() as session:
        result = await session.execute(select(ScraperConfig).limit(1))
        config = result.scalar_one_or_none()

    if not config or config.enabled == 0:
        logger.info("爬虫已禁用，跳过本次爬取")
        schedule_next_scrape()  # 仍然调度下次
        return

    # 2. 使用配置中的参数
    chains = config.enabled_chains
    count_per_chain = config.count_per_chain
    top_n = config.top_n_per_chain
    use_chrome = bool(config.use_undetected_chrome)

    # 3. 执行爬取
    scraper = MultiChainScraper()
    result = await scraper.scrape_and_save_multi_chain(
        chains=chains,
        count_per_chain=count_per_chain,
        top_n_per_chain=top_n,
        use_undetected_chrome=use_chrome
    )

    # 4. 调度下次任务（使用配置中的间隔）
    global next_scrape_interval_min, next_scrape_interval_max
    next_scrape_interval_min = config.scrape_interval_min
    next_scrape_interval_max = config.scrape_interval_max
    schedule_next_scrape()
```

修改 `schedule_next_scrape()` 使用全局配置变量：
```python
def schedule_next_scrape():
    # 使用配置的间隔范围
    next_run_minutes = random.uniform(
        next_scrape_interval_min,
        next_scrape_interval_max
    )
    # ... 其余逻辑
```

## 📋 部署步骤

### 1. 在服务器上运行迁移
```bash
cd ~/blockchain-data
git pull origin main

# 运行迁移
psql -U mac -d blockchain_data -f migrations/add_scraper_config_and_permanently_deleted.sql
```

### 2. 重启服务
```bash
# 停止旧服务
pkill -f scheduler_daemon
pkill -f run_api

# 启动新服务
nohup python scheduler_daemon.py --use-undetected-chrome > /tmp/scheduler.log 2>&1 &
nohup python run_api.py > /tmp/api.log 2>&1 &
```

### 3. 测试API

```bash
# 获取爬虫配置
curl http://localhost:8888/api/scraper/config

# 更新配置
curl -X PUT "http://localhost:8888/api/scraper/config?top_n_per_chain=20&scrape_interval_min=10&scrape_interval_max=20"

# 手动添加监控（通过pair地址）
curl -X POST "http://localhost:8888/api/monitor/add-by-pair?pair_address=0x123...&chain=bsc"

# 彻底删除代币
curl -X DELETE "http://localhost:8888/api/monitor/tokens/{token_id}/permanent"
```

## 🎯 剩余工作量估计

- 服务层方法实现: 30-45分钟
- 修改查询过滤: 15-20分钟
- 修改scheduler读取配置: 20-30分钟
- 测试: 15-20分钟

**总计**: 约1.5-2小时

## 📝 注意事项

1. `add_monitoring_by_pair()` 需要调用 AVE API，确保 API key 有效
2. 所有查询都要过滤 `permanently_deleted = 0`
3. Scheduler 第一次运行时如果配置不存在，使用硬编码的默认值
4. 数据库迁移前先备份
