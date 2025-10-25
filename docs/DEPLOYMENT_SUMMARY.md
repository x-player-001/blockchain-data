# 部署总结

## 架构说明

系统分为 **2个独立进程**：

### 进程 1: API 服务 (`run_api.py`)
- **功能**: 提供 REST API 接口
- **端口**: 8888
- **接口**: 查询监控代币、潜力代币、报警记录等
- **文档**: http://localhost:8888/docs

### 进程 2: 定时任务守护进程 (`scheduler_daemon.py`)
- **功能**: 自动化任务调度
- **任务1**: 每10分钟爬取 DexScreener 首页
  - 爬取 BSC 链涨幅榜
  - 保存前10名到 `potential_tokens` 表
  - 无头模式运行（避免打开浏览器）

- **任务2**: 每5分钟监控代币价格
  - 更新所有监控代币的价格和历史ATH
  - 检查多级阈值（20%, 30%, 40%...90%）
  - 触发报警并插入 `price_alerts` 表

---

## 快速启动

### 方法1: 使用启动脚本（推荐）

```bash
# 启动所有服务
./start_all.sh

# 停止所有服务
./stop_all.sh
```

### 方法2: 手动启动

```bash
# 启动 API 服务
nohup python3 run_api.py > /tmp/blockchain-api.log 2>&1 &

# 启动定时任务
nohup python3 scheduler_daemon.py > /tmp/blockchain-scheduler.log 2>&1 &
```

### 方法3: 使用 systemd（生产环境）

```bash
# 复制服务配置
sudo cp deployment/blockchain-api.service /etc/systemd/system/
sudo cp deployment/blockchain-scheduler.service /etc/systemd/system/

# 启用并启动服务
sudo systemctl enable blockchain-api blockchain-scheduler
sudo systemctl start blockchain-api blockchain-scheduler

# 查看状态
sudo systemctl status blockchain-api
sudo systemctl status blockchain-scheduler
```

---

## 监控和日志

### 查看日志

```bash
# API 日志
tail -f /tmp/blockchain-api.log

# 定时任务日志
tail -f /tmp/blockchain-scheduler.log

# 错误日志
tail -f /tmp/blockchain-api-error.log
tail -f /tmp/blockchain-scheduler-error.log
```

### 检查运行状态

```bash
# 查看进程
ps aux | grep "run_api.py\|scheduler_daemon.py"

# 查看端口占用
lsof -i:8888
```

---

## 数据流程图

```
┌──────────────────────────────────────────────────────────────┐
│  定时任务1: 爬取 DexScreener（每10分钟）                      │
└──────────────────────────────────────────────────────────────┘
  DexScreener BSC 涨幅榜
        ↓
  爬取100个代币，按24h涨幅排序
        ↓
  保存前10名到 potential_tokens 表


┌──────────────────────────────────────────────────────────────┐
│  手动操作: 前端筛选并添加监控                                  │
└──────────────────────────────────────────────────────────────┘
  调用 POST /api/monitor/add-from-potential
        ↓
  从 potential_tokens 复制到 monitored_tokens 表
  记录 entry_price_usd, status='active'
  调用 AVE API 获取详细数据（60+字段）


┌──────────────────────────────────────────────────────────────┐
│  定时任务2: 监控价格（每5分钟）                                │
└──────────────────────────────────────────────────────────────┘
  查询 monitored_tokens (status != 'stopped')
        ↓
  调用 AVE API 获取最新价格和历史ATH
        ↓
  计算从ATH的跌幅
        ↓
  检查多级阈值（20%, 30%, 40%...90%）
        ↓
  如果达到新阈值 → 插入 price_alerts 表
                 → 更新 status='alerted'
```

---

## 多级阈值报警说明

### 阈值设计

- **基础阈值**: 由用户设置（如20%）
- **自动添加**: 30%, 40%, 50%, 60%, 70%, 80%, 90%
- **报警规则**: 每个阈值只报警一次，避免重复

### 严重程度分级

| 跌幅 | 严重程度 |
|------|---------|
| ≥ 70% | critical |
| ≥ 50% | high |
| ≥ 30% | medium |
| < 30% | low |

### 示例

```
代币: 高手
入场价: $0.00100
历史ATH: $0.00200

监控过程:
1. 跌到 $0.00160 (20%跌幅) → 触发第1次报警 ✅
2. 跌到 $0.00150 (25%跌幅) → 不报警（未达到30%阈值）
3. 跌到 $0.00140 (30%跌幅) → 触发第2次报警 ✅
4. 跌到 $0.00120 (40%跌幅) → 触发第3次报警 ✅
5. 跌到 $0.00110 (45%跌幅) → 不报警（未达到50%阈值）
```

---

## API 接口列表

### 监控管理

```bash
# 获取监控代币列表
GET /api/monitor/tokens?limit=100&status=alerted

# 获取报警记录
GET /api/monitor/alerts?limit=50&severity=high

# 手动触发价格更新
POST /api/monitor/update-prices

# 从潜力代币添加到监控
POST /api/monitor/add-from-potential
{
  "potential_token_id": "uuid",
  "drop_threshold_percent": 20
}
```

### 潜力代币

```bash
# 获取潜力代币列表（爬取的涨幅榜）
GET /api/potential-tokens?limit=100&only_not_added=false

# 删除潜力代币
DELETE /api/potential-tokens/{id}
```

---

## 故障排查

### 1. API 服务无法启动

```bash
# 检查端口占用
lsof -i:8888
kill -9 <PID>

# 检查数据库
psql -U mac -d blockchain_data -c "SELECT 1"

# 查看错误日志
tail -f /tmp/blockchain-api-error.log
```

### 2. 定时任务未执行

```bash
# 检查进程
ps aux | grep scheduler_daemon

# 查看日志
tail -f /tmp/blockchain-scheduler.log

# 手动测试监控任务
python3 << 'EOF'
import asyncio
from src.services.token_monitor_service import TokenMonitorService

async def test():
    service = TokenMonitorService()
    result = await service.update_monitored_prices()
    print(result)
    await service.close()

asyncio.run(test())
EOF
```

### 3. 爬虫被 Cloudflare 拦截

```bash
# 方法1: 关闭无头模式（临时）
# 修改 scheduler_daemon.py 第53行: headless=False

# 方法2: 手动运行非无头模式爬取
python3 scrape_potential_non_headless.py
```

---

## 性能和安全建议

### 性能优化

1. **API 并发**: 增加 uvicorn workers
   ```bash
   uvicorn src.api.app:app --host 0.0.0.0 --port 8888 --workers 4
   ```

2. **数据库索引**: 已为常用查询字段添加索引

3. **爬虫间隔**: 根据服务器性能调整（默认10分钟）

### 安全建议

1. **防火墙**: 只开放必要端口
2. **HTTPS**: 使用 Nginx 反向代理
3. **API 认证**: 添加 JWT 或 API Key
4. **数据库**: 使用强密码，限制远程访问

---

## 备份和维护

### 数据库备份

```bash
# 手动备份
pg_dump -U mac blockchain_data > backup_$(date +%Y%m%d).sql

# 定时备份（添加到 crontab）
0 2 * * * pg_dump -U mac blockchain_data > /backup/blockchain_$(date +\%Y\%m\%d).sql
```

### 升级代码

```bash
cd /path/to/blockchain-data
git pull
./stop_all.sh
./start_all.sh
```

---

## 联系支持

如有问题，请：
1. 查看日志文件
2. 检查 [完整部署文档](deployment/DEPLOYMENT.md)
3. 联系开发团队
