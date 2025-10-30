#!/bin/bash
set -e

echo "=========================================="
echo "Blockchain Data 项目环境一键配置"
echo "系统: Ubuntu 24.04 LTS"
echo "注意: 请先安装 git 并克隆项目代码"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}错误: 请使用 root 权限运行此脚本${NC}"
    echo "使用: sudo bash setup_ubuntu.sh"
    exit 1
fi

# 获取项目路径
read -p "请输入项目路径 [默认: /root/blockchain-data]: " PROJECT_DIR
PROJECT_DIR=${PROJECT_DIR:-/root/blockchain-data}

if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}错误: 项目目录不存在: $PROJECT_DIR${NC}"
    echo "请先使用 git clone 克隆项目代码"
    exit 1
fi

# 获取配置
read -p "请输入数据库密码 [默认: blockchain123]: " DB_PASSWORD
DB_PASSWORD=${DB_PASSWORD:-blockchain123}

read -p "请输入 API 端口 [默认: 18763]: " API_PORT
API_PORT=${API_PORT:-18763}

echo ""
echo -e "${GREEN}开始安装...${NC}"
echo ""

# ==========================================
# 1. 更新包列表
# ==========================================
echo -e "${GREEN}[1/7] 更新包列表...${NC}"
apt update

# ==========================================
# 2. 安装基础工具
# ==========================================
echo -e "${GREEN}[2/7] 安装基础工具...${NC}"
apt install -y --no-upgrade \
    wget curl vim \
    build-essential \
    software-properties-common \
    ca-certificates \
    gnupg \
    lsb-release

# ==========================================
# 3. 安装 Python 3.11+
# ==========================================
echo -e "${GREEN}[3/7] 安装 Python 3.11...${NC}"
apt install -y --no-upgrade python3 python3-pip python3-venv python3-dev

# 验证版本
PYTHON_VERSION=$(python3 --version)
echo "Python 版本: $PYTHON_VERSION"

# 升级 pip（Ubuntu 24.04 需要 --break-system-packages）
python3 -m pip install --upgrade pip --break-system-packages

# ==========================================
# 4. 安装 Node.js 20 LTS
# ==========================================
echo -e "${GREEN}[4/7] 安装 Node.js 20 LTS...${NC}"

# 添加 NodeSource 仓库
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -

# 安装 Node.js
apt install -y --no-upgrade nodejs

# 验证安装
NODE_VERSION=$(node --version)
NPM_VERSION=$(npm --version)
echo "Node.js 版本: $NODE_VERSION"
echo "npm 版本: $NPM_VERSION"

echo -e "${GREEN}Node.js 安装完成${NC}"

# ==========================================
# 5. 安装 PostgreSQL 16
# ==========================================
echo -e "${GREEN}[5/7] 安装 PostgreSQL 16...${NC}"

# 添加 PostgreSQL 官方源
sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
apt update

# 安装 PostgreSQL
apt install -y --no-upgrade postgresql-16 postgresql-contrib-16

# 启动服务
systemctl enable postgresql
systemctl start postgresql

echo -e "${GREEN}PostgreSQL 安装完成${NC}"

# ==========================================
# 6. 创建数据库和用户
# ==========================================
echo -e "${GREEN}[6/7] 创建数据库...${NC}"

sudo -u postgres psql <<EOF
-- 创建数据库
CREATE DATABASE blockchain_data;

-- 创建用户
CREATE USER blockchain_user WITH PASSWORD '$DB_PASSWORD';

-- 授权
GRANT ALL PRIVILEGES ON DATABASE blockchain_data TO blockchain_user;

-- 授予模式权限
\c blockchain_data
GRANT ALL ON SCHEMA public TO blockchain_user;
ALTER DATABASE blockchain_data OWNER TO blockchain_user;

\q
EOF

echo -e "${GREEN}数据库创建完成${NC}"

# 配置 PostgreSQL 允许密码登录
PG_HBA_FILE="/etc/postgresql/16/main/pg_hba.conf"
if grep -q "host.*all.*all.*127.0.0.1/32.*md5" "$PG_HBA_FILE"; then
    echo "PostgreSQL 认证配置已存在"
else
    echo "配置 PostgreSQL 认证..."
    cat >> "$PG_HBA_FILE" <<EOF

# Blockchain Data 项目
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
EOF
    systemctl restart postgresql
fi

# ==========================================
# 7. 安装 Google Chrome
# ==========================================
echo -e "${GREEN}[7/7] 安装 Google Chrome...${NC}"

wget -q -O /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt install -y --no-upgrade /tmp/google-chrome-stable_current_amd64.deb
rm /tmp/google-chrome-stable_current_amd64.deb

# 验证安装
google-chrome --version

echo -e "${GREEN}Chrome 安装完成${NC}"

# ==========================================
# 8. 安装 Python 依赖
# ==========================================
echo -e "${GREEN}[8/9] 安装 Python 依赖...${NC}"

cd "$PROJECT_DIR"
python3 -m pip install -r requirements.txt --break-system-packages

echo -e "${GREEN}依赖安装完成${NC}"

# ==========================================
# 9. 创建配置文件
# ==========================================
echo -e "${GREEN}[9/9] 创建配置文件...${NC}"

# 创建 .env 文件
cat > "$PROJECT_DIR/.env" <<EOF
# 数据库配置
DATABASE_URL=postgresql://blockchain_user:${DB_PASSWORD}@127.0.0.1:5432/blockchain_data

# API 配置
API_PORT=${API_PORT}
API_HOST=0.0.0.0

# API Keys（需要手动填写）
AVE_API_KEY=your_ave_api_key_here
BSCSCAN_API_KEY=your_bscscan_api_key_here

# 日志级别
LOG_LEVEL=INFO

# 爬虫配置
USE_UNDETECTED_CHROME=true

# BSC RPC
BSC_RPC_URL=https://bsc-dataseed.binance.org/

# 缓存配置
USE_REDIS=false

# 应用配置
UPDATE_INTERVAL=300
MIN_MARKET_CAP=1000000
MAX_CONCURRENT_REQUESTS=10

# 速率限制
DEXSCREENER_RATE_LIMIT=300
GECKOTERMINAL_RATE_LIMIT=30
BSCSCAN_RATE_LIMIT=5
EOF

echo -e "${GREEN}配置文件创建完成${NC}"

# 初始化数据库表
echo ""
echo "初始化数据库表..."
cd "$PROJECT_DIR"
python3 -c "import asyncio; from src.storage.db_manager import DatabaseManager; asyncio.run(DatabaseManager().init_db())" || {
    echo -e "${YELLOW}警告: 数据库初始化失败，请手动运行${NC}"
}

# ==========================================
# 完成
# ==========================================
echo ""
echo -e "${GREEN}=========================================="
echo "安装完成！"
echo "==========================================${NC}"
echo ""
echo "配置信息:"
echo "  数据库: blockchain_data"
echo "  用户: blockchain_user"
echo "  密码: $DB_PASSWORD"
echo "  API 端口: $API_PORT"
echo "  项目目录: $PROJECT_DIR"
echo "  Node.js: $NODE_VERSION"
echo "  Python: $PYTHON_VERSION"
echo ""
echo "下一步操作:"
echo ""
echo "1. 编辑 .env 文件，填入 API keys:"
echo "   vim $PROJECT_DIR/.env"
echo ""
echo "2. 启动 API 服务:"
echo "   cd $PROJECT_DIR"
echo "   python3 run_api.py"
echo ""
echo "3. 启动定时任务:"
echo "   python3 scheduler_daemon.py"
echo ""
echo "4. 测试 API:"
echo "   curl http://localhost:$API_PORT/docs"
echo ""
echo -e "${YELLOW}注意: 请修改 .env 文件中的 AVE_API_KEY!${NC}"
echo ""
echo "=========================================="
