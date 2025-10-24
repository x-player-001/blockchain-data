#!/bin/bash
set -e

echo "=================================================="
echo "配置服务器环境（root 用户 + /root/blockchain-data）"
echo "=================================================="
echo ""

# 检查当前路径
if [ ! -f "run_api.py" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    echo "   cd /root/blockchain-data && bash configure_for_server.sh"
    exit 1
fi

# 1. 修改 systemd 服务配置
echo "1. 修改 systemd 服务配置..."

# 修改 API 服务
sed -i 's/User=mac/User=root/g' deployment/blockchain-api.service
sed -i 's|/Users/mac/Documents/code/blockchain-data|/root/blockchain-data|g' deployment/blockchain-api.service

# 修改 Scheduler 服务
sed -i 's/User=mac/User=root/g' deployment/blockchain-scheduler.service
sed -i 's|/Users/mac/Documents/code/blockchain-data|/root/blockchain-data|g' deployment/blockchain-scheduler.service

echo "   ✓ 服务配置已修改"

# 2. 修改 start_all.sh 脚本路径
echo ""
echo "2. 修改启动脚本路径..."
sed -i 's|/Users/mac/Documents/code/blockchain-data|/root/blockchain-data|g' start_all.sh
echo "   ✓ 启动脚本已修改"

# 3. 修改 stop_all.sh 脚本路径
sed -i 's|/Users/mac/Documents/code/blockchain-data|/root/blockchain-data|g' stop_all.sh
echo "   ✓ 停止脚本已修改"

# 4. 检查 .env 文件
echo ""
echo "3. 检查环境变量配置..."
if [ ! -f ".env" ]; then
    echo "   ⚠️  没有找到 .env 文件，创建模板..."
    cat > .env << 'EOF'
# 数据库配置（必须修改）
DATABASE_URL=postgresql://blockchain_user:your_password@localhost:5432/blockchain_data

# 日志级别
LOG_LEVEL=INFO

# API 端口
API_PORT=8888
EOF
    echo "   ✓ 已创建 .env 模板文件"
    echo "   ⚠️  请编辑 .env 文件，修改数据库连接信息："
    echo "      vim .env"
else
    echo "   ✓ .env 文件已存在"
fi

# 5. 验证修改
echo ""
echo "4. 验证配置修改..."
echo ""
echo "【blockchain-api.service】"
grep -E "User=|WorkingDirectory=|ExecStart=" deployment/blockchain-api.service | sed 's/^/   /'
echo ""
echo "【blockchain-scheduler.service】"
grep -E "User=|WorkingDirectory=|ExecStart=" deployment/blockchain-scheduler.service | sed 's/^/   /'

echo ""
echo "=================================================="
echo "配置完成！"
echo "=================================================="
echo ""
echo "下一步操作："
echo ""
echo "1. 修改数据库配置（如果还没改）："
echo "   vim .env"
echo ""
echo "2. 创建数据库："
echo "   sudo -u postgres psql -c \"CREATE DATABASE blockchain_data;\""
echo "   sudo -u postgres psql -c \"CREATE USER blockchain_user WITH PASSWORD 'your_password';\""
echo "   sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE blockchain_data TO blockchain_user;\""
echo ""
echo "3. 初始化数据库表："
echo "   python3 -c 'import asyncio; from src.storage.db_manager import DatabaseManager; asyncio.run(DatabaseManager().init_db())'"
echo ""
echo "4. 安装服务："
echo "   sudo cp deployment/blockchain-api.service /etc/systemd/system/"
echo "   sudo cp deployment/blockchain-scheduler.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable blockchain-api blockchain-scheduler"
echo "   sudo systemctl start blockchain-api blockchain-scheduler"
echo ""
echo "5. 查看状态："
echo "   sudo systemctl status blockchain-api"
echo "   sudo systemctl status blockchain-scheduler"
echo ""
