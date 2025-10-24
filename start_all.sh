#!/bin/bash
set -e

echo "================================================"
echo "启动 Blockchain Data 服务"
echo "================================================"

# 获取项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 检查数据库
echo "检查数据库连接..."
if ! python3 -c "import asyncio; from src.storage.db_manager import DatabaseManager; asyncio.run(DatabaseManager().init_db())" 2>/dev/null; then
    echo "警告: 数据库连接失败，请检查 PostgreSQL 是否运行"
fi

# 停止旧进程
echo "停止旧进程..."
pkill -f "run_api.py" 2>/dev/null || true
pkill -f "scheduler_daemon.py" 2>/dev/null || true
sleep 2

# 启动 API 服务
echo "启动 API 服务..."
nohup python3 run_api.py > /tmp/blockchain-api.log 2>&1 &
API_PID=$!
echo "API 服务已启动，PID: $API_PID"

# 等待 API 启动
sleep 3

# 启动定时任务守护进程
echo "启动定时任务守护进程..."
nohup python3 scheduler_daemon.py > /tmp/blockchain-scheduler.log 2>&1 &
SCHEDULER_PID=$!
echo "定时任务守护进程已启动，PID: $SCHEDULER_PID"

echo ""
echo "================================================"
echo "服务启动完成"
echo "================================================"
echo "API 服务: http://localhost:8888"
echo "API 文档: http://localhost:8888/docs"
echo ""
echo "进程信息:"
echo "  API PID: $API_PID"
echo "  Scheduler PID: $SCHEDULER_PID"
echo ""
echo "日志文件:"
echo "  API: tail -f /tmp/blockchain-api.log"
echo "  Scheduler: tail -f /tmp/blockchain-scheduler.log"
echo ""
echo "停止服务: ./stop_all.sh"
echo "================================================"
