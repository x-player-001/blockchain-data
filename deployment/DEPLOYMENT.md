# Blockchain Data 服务部署文档

## 架构概览

系统分为 **2个独立进程**：

1. **API 服务进程** (`run_api.py`)
   - FastAPI 应用
   - 提供 REST API 接口
   - 端口：8888

2. **定时任务守护进程** (`scheduler_daemon.py`)
   - 每10分钟爬取 DexScreener 首页数据
   - 每5分钟更新监控代币价格
   - 每10分钟更新潜力代币 AVE 数据

## 部署方式选择

### 方式一：使用 Systemd（推荐用于 Linux 服务器）

#### 1. 安装依赖

```bash
# 进入项目目录
cd /path/to/blockchain-data

# 安装 Python 依赖
pip3 install -r requirements.txt

# 安装 APScheduler（定时任务库）
pip3 install apscheduler
```

#### 2. 配置 Systemd 服务

```bash
# 复制服务配置文件到 systemd 目录
sudo cp deployment/blockchain-api.service /etc/systemd/system/
sudo cp deployment/blockchain-scheduler.service /etc/systemd/system/

# 修改服务文件中的路径和用户名
sudo vim /etc/systemd/system/blockchain-api.service
# 修改 User, WorkingDirectory, ExecStart 为实际路径

sudo vim /etc/systemd/system/blockchain-scheduler.service
# 修改 User, WorkingDirectory, ExecStart 为实际路径

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务（开机自启动）
sudo systemctl enable blockchain-api
sudo systemctl enable blockchain-scheduler

# 启动服务
sudo systemctl start blockchain-api
sudo systemctl start blockchain-scheduler

# 查看服务状态
sudo systemctl status blockchain-api
sudo systemctl status blockchain-scheduler
```

#### 3. 管理服务

```bash
# 查看日志
sudo journalctl -u blockchain-api -f
sudo journalctl -u blockchain-scheduler -f

# 重启服务
sudo systemctl restart blockchain-api
sudo systemctl restart blockchain-scheduler

# 停止服务
sudo systemctl stop blockchain-api
sudo systemctl stop blockchain-scheduler

# 查看服务状态
sudo systemctl status blockchain-api
sudo systemctl status blockchain-scheduler
```

---

### 方式二：使用 Supervisor（适用于所有平台）

#### 1. 安装 Supervisor

```bash
# Ubuntu/Debian
sudo apt-get install supervisor

# CentOS/RHEL
sudo yum install supervisor

# macOS
brew install supervisor

# 或使用 pip
pip3 install supervisor
```

#### 2. 配置 Supervisor

```bash
# 复制配置文件
sudo cp deployment/supervisor.conf /etc/supervisor/conf.d/blockchain.conf

# 修改配置文件中的路径
sudo vim /etc/supervisor/conf.d/blockchain.conf
# 修改 command, directory, user 为实际值

# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动所有服务
sudo supervisorctl start blockchain-services:*
```

#### 3. 管理服务

```bash
# 查看所有服务状态
sudo supervisorctl status

# 启动服务
sudo supervisorctl start blockchain-api
sudo supervisorctl start blockchain-scheduler

# 停止服务
sudo supervisorctl stop blockchain-api
sudo supervisorctl stop blockchain-scheduler

# 重启服务
sudo supervisorctl restart blockchain-api
sudo supervisorctl restart blockchain-scheduler

# 查看日志
tail -f /tmp/blockchain-api.log
tail -f /tmp/blockchain-scheduler.log
```

---

### 方式三：手动运行（开发/测试环境）

#### 1. 启动 API 服务

```bash
# 后台运行
nohup python3 run_api.py > /tmp/api.log 2>&1 &

# 或前台运行（测试用）
python3 run_api.py
```

#### 2. 启动定时任务守护进程

```bash
# 后台运行
nohup python3 scheduler_daemon.py > /tmp/scheduler.log 2>&1 &

# 或前台运行（测试用）
python3 scheduler_daemon.py
```

#### 3. 查看运行状态

```bash
# 查看进程
ps aux | grep "run_api.py\|scheduler_daemon.py"

# 查看日志
tail -f /tmp/api.log
tail -f /tmp/scheduler.log

# 停止服务
pkill -f "run_api.py"
pkill -f "scheduler_daemon.py"
```

---

## 环境变量配置

创建 `.env` 文件（如果需要）：

```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/blockchain_data

# API 配置
API_PORT=8888
API_HOST=0.0.0.0

# 爬虫配置
SCRAPE_INTERVAL_MINUTES=10
MONITOR_INTERVAL_MINUTES=5
```

---

## 监控和日志

### 日志文件位置

- **API 服务日志**: `/tmp/blockchain-api.log`
- **调度器日志**: `/tmp/blockchain-scheduler.log`
- **错误日志**: `/tmp/blockchain-*-error.log`

### 日志轮转（推荐）

创建 `/etc/logrotate.d/blockchain`:

```
/tmp/blockchain-*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 mac mac
    sharedscripts
    postrotate
        /bin/kill -HUP `cat /tmp/supervisord.pid 2>/dev/null` 2>/dev/null || true
    endscript
}
```

---

## 定时任务说明

### 任务调度表

| 任务 | 频率 | 功能 | 表 |
|------|------|------|------|
| 爬取 DexScreener | 每10分钟 | 获取涨幅榜 Top 10 | `potential_tokens` |
| 更新 AVE 数据 | 每10分钟 | 更新潜力代币详细数据 | `potential_tokens` |
| 监控价格 | 每5分钟 | 更新监控代币价格并触发报警 | `monitored_tokens`, `price_alerts` |

### 任务详情

#### 1. 爬取 DexScreener 任务
- **频率**: 10分钟
- **功能**: 爬取 BSC 链涨幅榜前10名代币
- **保存位置**: `potential_tokens` 表
- **无头模式**: 是（避免打开浏览器窗口）

#### 2. 更新 AVE 数据任务
- **频率**: 10分钟
- **功能**: 为 `potential_tokens` 表中未添加到监控的代币更新 AVE API 数据
- **数据**: LP锁仓、市值、交易量等60+字段

#### 3. 监控价格任务
- **频率**: 5分钟
- **功能**:
  - 更新所有监控代币的当前价格
  - 同步历史 ATH
  - 检查多级阈值（20%, 30%, 40%...90%）
  - 触发报警
- **报警逻辑**: 每个阈值只报警一次，避免重复

---

## API 接口列表

### 监控相关

- `GET /api/monitor/tokens` - 获取监控代币列表
- `GET /api/monitor/alerts` - 获取报警记录
- `POST /api/monitor/update-prices` - 手动触发价格更新
- `POST /api/monitor/add-from-potential` - 从潜力代币添加到监控

### 潜力代币

- `GET /api/potential-tokens` - 获取潜力代币列表
- `DELETE /api/potential-tokens/{id}` - 删除潜力代币

### 完整文档

访问 `http://localhost:8888/docs` 查看 Swagger UI 文档

---

## 故障排查

### API 服务无法启动

```bash
# 检查端口占用
lsof -i:8888

# 检查数据库连接
psql -U mac -d blockchain_data -c "SELECT 1"

# 查看错误日志
tail -f /tmp/blockchain-api-error.log
```

### 定时任务未执行

```bash
# 检查进程是否运行
ps aux | grep scheduler_daemon

# 查看调度器日志
tail -f /tmp/blockchain-scheduler.log

# 手动测试任务
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

### 爬虫失败（Cloudflare 拦截）

```bash
# 如果无头模式被拦截，可以临时关闭无头模式
# 修改 scheduler_daemon.py 中的 headless=False

# 或增加延迟和随机化
# 修改爬虫代码添加更多反检测措施
```

---

## 性能优化建议

1. **数据库连接池**: 已配置异步连接池（默认最大20个连接）
2. **API 并发**: 使用 uvicorn 的 workers 参数增加并发
   ```bash
   uvicorn src.api.app:app --host 0.0.0.0 --port 8888 --workers 4
   ```
3. **爬虫频率**: 根据服务器性能调整间隔时间
4. **日志级别**: 生产环境设置为 WARNING 减少 I/O

---

## 安全建议

1. **防火墙**: 只开放必要端口（8888）
2. **HTTPS**: 使用 Nginx 反向代理添加 SSL
3. **API 认证**: 添加 JWT 或 API Key 认证
4. **数据库**: 使用强密码，禁止远程 root 登录
5. **环境变量**: 敏感信息不要硬编码，使用环境变量

---

## 备份策略

### 数据库备份

```bash
# 每日备份脚本
#!/bin/bash
pg_dump -U mac blockchain_data > /backup/blockchain_$(date +%Y%m%d).sql

# 保留最近7天
find /backup -name "blockchain_*.sql" -mtime +7 -delete
```

### 添加到 crontab

```bash
crontab -e

# 每天凌晨2点备份
0 2 * * * /path/to/backup_script.sh
```

---

## 升级和维护

### 更新代码

```bash
cd /path/to/blockchain-data
git pull

# 重启服务（systemd）
sudo systemctl restart blockchain-api
sudo systemctl restart blockchain-scheduler

# 重启服务（supervisor）
sudo supervisorctl restart blockchain-services:*
```

### 数据库迁移

```bash
# 如果有表结构变更
python3 -c "from src.storage.db_manager import DatabaseManager; import asyncio; asyncio.run(DatabaseManager().init_db())"
```

---

## 快速启动脚本

创建 `start_all.sh`:

```bash
#!/bin/bash
set -e

echo "启动 Blockchain Data 服务..."

# 方式1: 使用 systemd
sudo systemctl start blockchain-api
sudo systemctl start blockchain-scheduler

# 方式2: 使用 supervisor
# sudo supervisorctl start blockchain-services:*

# 方式3: 手动启动
# nohup python3 run_api.py > /tmp/api.log 2>&1 &
# nohup python3 scheduler_daemon.py > /tmp/scheduler.log 2>&1 &

echo "服务已启动"
echo "API: http://localhost:8888"
echo "Docs: http://localhost:8888/docs"

# 查看状态
sudo systemctl status blockchain-api --no-pager
sudo systemctl status blockchain-scheduler --no-pager
```

创建 `stop_all.sh`:

```bash
#!/bin/bash
set -e

echo "停止 Blockchain Data 服务..."

# 方式1: 使用 systemd
sudo systemctl stop blockchain-api
sudo systemctl stop blockchain-scheduler

# 方式2: 使用 supervisor
# sudo supervisorctl stop blockchain-services:*

# 方式3: 手动停止
# pkill -f "run_api.py"
# pkill -f "scheduler_daemon.py"

echo "服务已停止"
```

---

## 联系和支持

如有问题，请查看日志文件或联系开发团队。
