# CentOS 快速部署检查清单

## 必备组件清单

### ✅ 第一步：系统依赖

```bash
# 1. Chrome 浏览器
google-chrome --version

# 2. Xvfb 虚拟显示（无头服务器必需）
xvfb-run --help

# 3. Python 3.8+
python3 --version

# 4. PostgreSQL 14+
psql --version
```

### ✅ 第二步：Python 包

```bash
# 必需包
pip3 list | grep -E "fastapi|uvicorn|asyncpg|apscheduler|undetected-chromedriver"

# 应该看到：
# fastapi             0.108.0
# uvicorn             0.25.0
# asyncpg             0.29.0
# apscheduler         3.10.4
# undetected-chromedriver  3.5.x
```

---

## 一键安装脚本（CentOS 7/8）

```bash
#!/bin/bash
# 保存为 quick_install.sh

# 安装 Chrome
cat <<EOF | sudo tee /etc/yum.repos.d/google-chrome.repo
[google-chrome]
name=google-chrome
baseurl=http://dl.google.com/linux/chrome/rpm/stable/x86_64
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
EOF
sudo yum install -y google-chrome-stable

# 安装 Xvfb
sudo yum install -y xorg-x11-server-Xvfb

# 安装 Python 依赖
pip3 install undetected-chromedriver

# 验证
echo "=== 验证安装 ==="
google-chrome --version && echo "✓ Chrome 已安装"
which xvfb-run && echo "✓ Xvfb 已安装"
python3 -c "import undetected_chromedriver; print('✓ undetected-chromedriver 已安装')"
```

---

## 快速验证测试

### 测试1: Chrome + Xvfb

```bash
# 这个命令应该成功运行
xvfb-run google-chrome --headless --disable-gpu --dump-dom https://www.google.com | head -5
```

### 测试2: 爬虫功能

```bash
cd /opt/blockchain-data

# 测试爬取（不保存数据库）
python3 << 'EOF'
import undetected_chromedriver as uc

options = uc.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = uc.Chrome(options=options)
driver.get('https://dexscreener.com')
print(f"✓ 成功访问 DexScreener, 标题: {driver.title}")
driver.quit()
EOF
```

### 测试3: 完整爬取流程

```bash
python3 << 'EOF'
import asyncio
from src.services.token_monitor_service import TokenMonitorService

async def test():
    print("开始测试爬取...")
    service = TokenMonitorService()
    result = await service.scrape_and_save_to_potential(
        count=10,
        top_n=3,
        headless=True
    )
    print(f"✓ 爬取成功: {result}")
    await service.close()

asyncio.run(test())
EOF
```

---

## 常见错误快速修复

### ❌ 错误1: Chrome not found

```bash
# 症状
selenium.common.exceptions.WebDriverException: Message: 'chromedriver' executable needs to be in PATH

# 修复
sudo yum install -y google-chrome-stable
google-chrome --version
```

### ❌ 错误2: Display error

```bash
# 症状
selenium.common.exceptions.WebDriverException: unknown error: DevToolsActivePort file doesn't exist

# 修复
sudo yum install -y xorg-x11-server-Xvfb

# 确保 scheduler_daemon.py 中 headless=True
```

### ❌ 错误3: Cloudflare blocking (爬取0个代币)

```bash
# 症状
日志显示: 获取到 0 个代币

# 检查
python3 -c "import undetected_chromedriver; print('OK')"

# 如果报错，安装：
pip3 install undetected-chromedriver

# 查看日志确认使用了 undetected-chromedriver
tail -f /tmp/blockchain-scheduler.log | grep "undetected"
```

### ❌ 错误4: Database connection refused

```bash
# 症状
psycopg2.OperationalError: could not connect to server

# 修复
sudo systemctl start postgresql-14
sudo systemctl enable postgresql-14
```

---

## 服务快速启动

### 方法1: 手动启动（测试用）

```bash
cd /opt/blockchain-data

# 启动 API
nohup python3 run_api.py > /tmp/api.log 2>&1 &

# 启动定时任务
nohup python3 scheduler_daemon.py > /tmp/scheduler.log 2>&1 &

# 查看日志
tail -f /tmp/api.log
tail -f /tmp/scheduler.log
```

### 方法2: 使用 systemd（生产环境）

```bash
# 启动
sudo systemctl start blockchain-api blockchain-scheduler

# 查看状态
sudo systemctl status blockchain-api
sudo systemctl status blockchain-scheduler

# 查看日志
sudo journalctl -u blockchain-scheduler -f
```

---

## 验证服务运行

### 1. 检查进程

```bash
ps aux | grep "run_api.py\|scheduler_daemon.py"

# 应该看到两个 python 进程
```

### 2. 检查 API

```bash
curl http://localhost:8888/health
# 返回: {"status":"healthy","timestamp":"..."}

curl http://localhost:8888/api/potential-tokens?limit=1
# 返回: {"total":X,"data":[...]}
```

### 3. 检查数据库

```bash
psql -U mac -d blockchain_data -c "SELECT COUNT(*) FROM potential_tokens;"
# 应该看到有数据
```

---

## 关键路径检查

### Chrome 路径

```bash
which google-chrome
# 应该是: /usr/bin/google-chrome

ls -la /usr/bin/google-chrome
# 应该有执行权限
```

### Python 包路径

```bash
python3 -c "import undetected_chromedriver; print(undetected_chromedriver.__file__)"
# 应该输出包的路径
```

### ChromeDriver 自动管理

`undetected-chromedriver` 会自动下载和管理 ChromeDriver，无需手动安装。

---

## 性能基准

**正常指标**:
- 爬取10个代币: ~20-30秒
- 监控3个代币: ~5-10秒
- API 响应时间: <100ms

**如果超出这些时间**:
```bash
# 检查网络
ping -c 3 dexscreener.com

# 检查 CPU
top

# 检查内存
free -h

# 检查磁盘 I/O
iostat
```

---

## 快速重启

```bash
# 停止所有
sudo systemctl stop blockchain-api blockchain-scheduler
# 或
pkill -f "run_api.py"
pkill -f "scheduler_daemon.py"

# 等待2秒
sleep 2

# 启动所有
sudo systemctl start blockchain-api blockchain-scheduler
# 或
cd /opt/blockchain-data && ./start_all.sh
```

---

## 日志位置

```bash
# API 日志
/tmp/blockchain-api.log
/var/log/blockchain-api.log

# Scheduler 日志
/tmp/blockchain-scheduler.log
/var/log/blockchain-scheduler.log

# 系统日志
sudo journalctl -u blockchain-api -f
sudo journalctl -u blockchain-scheduler -f
```

---

## 端口检查

```bash
# API 端口（8888）
lsof -i:8888

# 数据库端口（5432）
lsof -i:5432

# 如果端口被占用
sudo kill -9 $(lsof -ti:8888)
```

---

## 最小化部署命令

**假设你已经有 PostgreSQL 和 Python 3.8**:

```bash
# 1. 安装 Chrome + Xvfb
sudo yum install -y google-chrome-stable xorg-x11-server-Xvfb

# 2. 安装 Python 依赖
cd /opt/blockchain-data
pip3 install -r requirements.txt
pip3 install undetected-chromedriver

# 3. 配置环境
cp .env.example .env
vim .env  # 修改数据库连接

# 4. 初始化数据库
python3 -c "import asyncio; from src.storage.db_manager import DatabaseManager; asyncio.run(DatabaseManager().init_db())"

# 5. 启动服务
./start_all.sh

# 6. 验证
curl http://localhost:8888/health
```

**总耗时**: ~10-15分钟（取决于网络速度）

---

## 故障排查命令速查

```bash
# Chrome 测试
xvfb-run google-chrome --version

# 爬虫包测试
python3 -c "import undetected_chromedriver; print('OK')"

# 数据库测试
psql -U mac -d blockchain_data -c "SELECT 1"

# 服务测试
curl http://localhost:8888/health

# 日志查看
tail -f /tmp/blockchain-scheduler.log

# 进程查看
ps aux | grep python3

# 端口查看
lsof -i:8888
```

---

## 需要帮助？

查看完整文档: [CENTOS_DEPLOYMENT.md](CENTOS_DEPLOYMENT.md)
