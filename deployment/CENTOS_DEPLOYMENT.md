# CentOS 服务器完整部署指南

本文档详细说明如何在 CentOS 服务器上部署区块链数据监控系统，包括爬虫环境配置。

## 目录

1. [系统要求](#系统要求)
2. [基础环境安装](#基础环境安装)
3. [Chrome 浏览器安装](#chrome-浏览器安装)
4. [Python 环境配置](#python-环境配置)
5. [数据库安装](#数据库安装)
6. [项目部署](#项目部署)
7. [服务配置](#服务配置)
8. [验证测试](#验证测试)
9. [故障排查](#故障排查)

---

## 系统要求

- **操作系统**: CentOS 7/8 或 RHEL 7/8
- **内存**: 至少 2GB RAM（推荐 4GB+）
- **磁盘**: 至少 10GB 可用空间
- **网络**: 能访问外网（DexScreener, AVE API）

---

## 基础环境安装

### 1. 更新系统

```bash
# CentOS 7
sudo yum update -y

# CentOS 8
sudo dnf update -y
```

### 2. 安装必要工具

```bash
# CentOS 7
sudo yum install -y wget curl git vim

# CentOS 8
sudo dnf install -y wget curl git vim
```

---

## Chrome 浏览器安装

**重要**: 爬虫需要 Chrome 浏览器和 ChromeDriver。

### 方法1: 使用 YUM 仓库（推荐）

```bash
# 添加 Google Chrome 仓库
cat <<EOF | sudo tee /etc/yum.repos.d/google-chrome.repo
[google-chrome]
name=google-chrome
baseurl=http://dl.google.com/linux/chrome/rpm/stable/x86_64
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
EOF

# 安装 Chrome
# CentOS 7
sudo yum install -y google-chrome-stable

# CentOS 8
sudo dnf install -y google-chrome-stable
```

### 方法2: 手动下载安装

```bash
# 下载 Chrome RPM 包
wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm

# 安装
sudo yum localinstall -y google-chrome-stable_current_x86_64.rpm
# 或 CentOS 8
sudo dnf localinstall -y google-chrome-stable_current_x86_64.rpm
```

### 3. 安装虚拟显示服务器（必需）

CentOS 服务器通常没有图形界面，需要 Xvfb 虚拟显示：

```bash
# CentOS 7
sudo yum install -y xorg-x11-server-Xvfb

# CentOS 8
sudo dnf install -y xorg-x11-server-Xvfb
```

### 4. 验证 Chrome 安装

```bash
google-chrome --version
# 输出示例: Google Chrome 120.0.6099.109
```

---

## Python 环境配置

### 1. 安装 Python 3.8+

```bash
# CentOS 7 需要安装 EPEL 仓库
sudo yum install -y epel-release
sudo yum install -y python38 python38-pip python38-devel

# CentOS 8
sudo dnf install -y python38 python38-pip python38-devel

# 设置 python3 为默认
sudo alternatives --set python /usr/bin/python3.8
sudo alternatives --set python3 /usr/bin/python3.8
```

### 2. 升级 pip

```bash
python3 -m pip install --upgrade pip
```

### 3. 安装系统依赖

```bash
# CentOS 7
sudo yum install -y gcc gcc-c++ make postgresql-devel

# CentOS 8
sudo dnf install -y gcc gcc-c++ make postgresql-devel
```

---

## 数据库安装

### 安装 PostgreSQL 14+

```bash
# CentOS 7/8 - 添加 PostgreSQL 官方仓库
sudo yum install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-$(rpm -E %{rhel})-x86_64/pgdg-redhat-repo-latest.noarch.rpm

# 禁用内置 PostgreSQL 模块（CentOS 8）
sudo dnf -qy module disable postgresql

# 安装 PostgreSQL 14
sudo yum install -y postgresql14-server postgresql14-contrib

# 初始化数据库
sudo /usr/pgsql-14/bin/postgresql-14-setup initdb

# 启动并设置开机自启
sudo systemctl enable postgresql-14
sudo systemctl start postgresql-14

# 检查状态
sudo systemctl status postgresql-14
```

### 配置 PostgreSQL

```bash
# 切换到 postgres 用户
sudo su - postgres

# 创建数据库和用户
psql -c "CREATE DATABASE blockchain_data;"
psql -c "CREATE USER mac WITH PASSWORD 'your_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE blockchain_data TO mac;"

# 退出
exit
```

### 修改认证配置（允许本地密码登录）

```bash
# 编辑 pg_hba.conf
sudo vim /var/lib/pgsql/14/data/pg_hba.conf

# 找到类似这一行：
# local   all             all                                     peer

# 修改为：
# local   all             all                                     md5

# 重启 PostgreSQL
sudo systemctl restart postgresql-14
```

---

## 项目部署

### 1. 克隆项目

```bash
cd /opt
sudo git clone https://github.com/your-repo/blockchain-data.git
sudo chown -R $USER:$USER blockchain-data
cd blockchain-data
```

### 2. 创建虚拟环境（可选但推荐）

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt

# 安装爬虫专用依赖
pip install undetected-chromedriver
```

### 4. 配置环境变量

```bash
# 创建 .env 文件
cat > .env << 'EOF'
DATABASE_URL=postgresql://mac:your_password@localhost:5432/blockchain_data
API_PORT=8888
API_HOST=0.0.0.0
EOF
```

### 5. 初始化数据库

```bash
python3 -c "
import asyncio
from src.storage.db_manager import DatabaseManager

async def init():
    db = DatabaseManager()
    await db.init_db()
    print('✓ 数据库初始化成功')

asyncio.run(init())
"
```

---

## 服务配置

### 方法1: 使用 Systemd（推荐）

#### 1. 修改服务配置文件

```bash
# 编辑 API 服务配置
sudo vim deployment/blockchain-api.service

# 修改以下内容：
# User=your_username
# WorkingDirectory=/opt/blockchain-data
# ExecStart=/usr/bin/python3 /opt/blockchain-data/run_api.py

# 或如果使用虚拟环境：
# ExecStart=/opt/blockchain-data/venv/bin/python /opt/blockchain-data/run_api.py
```

```bash
# 编辑 Scheduler 服务配置
sudo vim deployment/blockchain-scheduler.service

# 修改相同的内容
```

#### 2. 安装并启动服务

```bash
# 复制服务文件
sudo cp deployment/blockchain-api.service /etc/systemd/system/
sudo cp deployment/blockchain-scheduler.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务（开机自启动）
sudo systemctl enable blockchain-api
sudo systemctl enable blockchain-scheduler

# 启动服务
sudo systemctl start blockchain-api
sudo systemctl start blockchain-scheduler

# 查看状态
sudo systemctl status blockchain-api
sudo systemctl status blockchain-scheduler
```

### 方法2: 使用启动脚本

```bash
# 修改启动脚本路径
vim start_all.sh

# 启动所有服务
./start_all.sh
```

---

## 验证测试

### 1. 测试 Chrome 和 Xvfb

```bash
# 测试 Chrome
google-chrome --version

# 测试 Xvfb
xvfb-run google-chrome --version

# 测试 undetected-chromedriver
python3 -c "import undetected_chromedriver as uc; print('✓ undetected-chromedriver 可用')"
```

### 2. 测试爬虫（手动运行）

```bash
# 测试爬取功能
python3 << 'EOF'
import asyncio
from src.services.token_monitor_service import TokenMonitorService

async def test():
    service = TokenMonitorService()
    result = await service.scrape_and_save_to_potential(
        count=10,
        top_n=5,
        headless=True
    )
    print(f"✓ 爬取成功: {result}")
    await service.close()

asyncio.run(test())
EOF
```

### 3. 测试 API 接口

```bash
# 测试 API 服务
curl http://localhost:8888/health

# 测试获取潜力代币
curl http://localhost:8888/api/potential-tokens?limit=5
```

### 4. 检查定时任务日志

```bash
# 查看 Scheduler 日志
sudo journalctl -u blockchain-scheduler -f

# 或查看文件日志
tail -f /tmp/blockchain-scheduler.log
```

---

## 故障排查

### 问题1: Chrome 未找到

**错误**: `selenium.common.exceptions.WebDriverException: Message: 'chromedriver' executable needs to be in PATH`

**解决**:
```bash
# 检查 Chrome 是否安装
which google-chrome
google-chrome --version

# 如果没有安装，重新安装
sudo yum install -y google-chrome-stable
```

### 问题2: 显示错误

**错误**: `selenium.common.exceptions.WebDriverException: Message: unknown error: DevToolsActivePort file doesn't exist`

**解决**: 确保使用 Xvfb

```bash
# 修改 scheduler_daemon.py 确保 headless=True
# 或者安装 Xvfb
sudo yum install -y xorg-x11-server-Xvfb
```

### 问题3: Cloudflare 拦截（爬取到0个代币）

**解决**:
```bash
# 1. 确保安装了 undetected-chromedriver
pip install undetected-chromedriver

# 2. 检查日志中是否显示 "使用 undetected-chromedriver"
tail -f /tmp/blockchain-scheduler.log

# 3. 尝试非无头模式测试（临时）
# 修改 scheduler_daemon.py: headless=False
```

### 问题4: 数据库连接失败

**错误**: `could not connect to server: Connection refused`

**解决**:
```bash
# 检查 PostgreSQL 是否运行
sudo systemctl status postgresql-14

# 启动 PostgreSQL
sudo systemctl start postgresql-14

# 测试连接
psql -U mac -d blockchain_data -c "SELECT 1"
```

### 问题5: 权限问题

**错误**: `Permission denied`

**解决**:
```bash
# 给项目目录正确的权限
sudo chown -R your_username:your_username /opt/blockchain-data

# 给 Chrome 执行权限
sudo chmod +x /usr/bin/google-chrome
```

### 问题6: 端口被占用

**错误**: `Address already in use`

**解决**:
```bash
# 查找占用端口的进程
lsof -i:8888

# 停止旧进程
sudo systemctl stop blockchain-api

# 或强制杀死
sudo kill -9 $(lsof -ti:8888)
```

---

## 性能优化

### 1. 调整爬虫间隔

如果服务器性能较差，可以增加爬取间隔：

```python
# 修改 scheduler_daemon.py
scheduler.add_job(
    scrape_dexscreener_task,
    trigger=IntervalTrigger(minutes=15),  # 从10分钟改为15分钟
    ...
)
```

### 2. 日志轮转

```bash
# 安装 logrotate
sudo yum install -y logrotate

# 创建配置
sudo vim /etc/logrotate.d/blockchain

# 内容：
/tmp/blockchain-*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 your_username your_username
    sharedscripts
    postrotate
        systemctl reload blockchain-scheduler
    endscript
}
```

### 3. 数据库优化

```bash
# 编辑 PostgreSQL 配置
sudo vim /var/lib/pgsql/14/data/postgresql.conf

# 调整以下参数（根据服务器内存）
shared_buffers = 256MB          # 1/4 系统内存
effective_cache_size = 1GB      # 1/2 系统内存
maintenance_work_mem = 64MB

# 重启 PostgreSQL
sudo systemctl restart postgresql-14
```

---

## 防火墙配置

如果需要外部访问 API：

```bash
# CentOS 7
sudo firewall-cmd --permanent --add-port=8888/tcp
sudo firewall-cmd --reload

# CentOS 8
sudo firewall-cmd --permanent --add-port=8888/tcp
sudo firewall-cmd --reload

# 或使用 iptables
sudo iptables -A INPUT -p tcp --dport 8888 -j ACCEPT
sudo service iptables save
```

---

## 监控和维护

### 1. 查看服务状态

```bash
# 查看所有服务
sudo systemctl status blockchain-api blockchain-scheduler

# 查看日志
sudo journalctl -u blockchain-api -f
sudo journalctl -u blockchain-scheduler -f
```

### 2. 重启服务

```bash
# 重启 API 服务
sudo systemctl restart blockchain-api

# 重启定时任务
sudo systemctl restart blockchain-scheduler

# 重启所有
sudo systemctl restart blockchain-api blockchain-scheduler
```

### 3. 查看资源使用

```bash
# 查看进程
ps aux | grep python3

# 查看内存使用
free -h

# 查看磁盘使用
df -h

# 查看数据库大小
psql -U mac -d blockchain_data -c "SELECT pg_size_pretty(pg_database_size('blockchain_data'));"
```

---

## 完整安装脚本

保存为 `install_centos.sh`:

```bash
#!/bin/bash
set -e

echo "================================"
echo "CentOS 区块链监控系统安装脚本"
echo "================================"

# 1. 更新系统
echo "1. 更新系统..."
sudo yum update -y

# 2. 安装基础工具
echo "2. 安装基础工具..."
sudo yum install -y wget curl git vim gcc gcc-c++ make postgresql-devel epel-release

# 3. 安装 Chrome
echo "3. 安装 Chrome 浏览器..."
cat <<EOF | sudo tee /etc/yum.repos.d/google-chrome.repo
[google-chrome]
name=google-chrome
baseurl=http://dl.google.com/linux/chrome/rpm/stable/x86_64
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
EOF
sudo yum install -y google-chrome-stable

# 4. 安装 Xvfb
echo "4. 安装 Xvfb..."
sudo yum install -y xorg-x11-server-Xvfb

# 5. 安装 Python 3.8
echo "5. 安装 Python 3.8..."
sudo yum install -y python38 python38-pip python38-devel

# 6. 安装 PostgreSQL
echo "6. 安装 PostgreSQL 14..."
sudo yum install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-$(rpm -E %{rhel})-x86_64/pgdg-redhat-repo-latest.noarch.rpm
sudo yum install -y postgresql14-server postgresql14-contrib
sudo /usr/pgsql-14/bin/postgresql-14-setup initdb
sudo systemctl enable postgresql-14
sudo systemctl start postgresql-14

# 7. 克隆项目
echo "7. 克隆项目..."
cd /opt
if [ -d "blockchain-data" ]; then
    echo "项目目录已存在，跳过克隆"
else
    sudo git clone https://github.com/your-repo/blockchain-data.git
    sudo chown -R $USER:$USER blockchain-data
fi
cd blockchain-data

# 8. 安装 Python 依赖
echo "8. 安装 Python 依赖..."
pip3 install -r requirements.txt
pip3 install undetected-chromedriver

# 9. 验证安装
echo "9. 验证安装..."
google-chrome --version
python3 -c "import undetected_chromedriver as uc; print('✓ undetected-chromedriver 可用')"

echo ""
echo "================================"
echo "安装完成！"
echo "================================"
echo "下一步："
echo "1. 配置数据库（参考文档）"
echo "2. 修改 .env 文件"
echo "3. 初始化数据库"
echo "4. 启动服务"
```

使用方法：
```bash
chmod +x install_centos.sh
./install_centos.sh
```

---

## 总结

✅ **必须安装的组件**:
1. Chrome 浏览器
2. Xvfb 虚拟显示
3. Python 3.8+
4. PostgreSQL 14+
5. undetected-chromedriver

✅ **推荐配置**:
- 使用 systemd 管理服务
- 配置日志轮转
- 启用防火墙
- 配置数据库备份

✅ **服务架构**:
- API 服务: 端口 8888
- 定时任务: 每10分钟爬取，每5分钟监控
- 数据库: PostgreSQL

如有问题，参考 [故障排查](#故障排查) 章节。
