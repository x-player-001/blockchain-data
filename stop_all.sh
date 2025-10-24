#!/bin/bash
set -e

echo "================================================"
echo "停止 Blockchain Data 服务"
echo "================================================"

# 查找并停止 API 服务
echo "停止 API 服务..."
API_PIDS=$(pgrep -f "run_api.py" || true)
if [ -n "$API_PIDS" ]; then
    echo "找到 API 进程: $API_PIDS"
    pkill -f "run_api.py"
    echo "API 服务已停止"
else
    echo "API 服务未运行"
fi

# 查找并停止定时任务守护进程
echo "停止定时任务守护进程..."
SCHEDULER_PIDS=$(pgrep -f "scheduler_daemon.py" || true)
if [ -n "$SCHEDULER_PIDS" ]; then
    echo "找到 Scheduler 进程: $SCHEDULER_PIDS"
    pkill -f "scheduler_daemon.py"
    echo "定时任务守护进程已停止"
else
    echo "定时任务守护进程未运行"
fi

# 等待进程完全停止
sleep 2

# 检查是否还有残留进程
REMAINING=$(pgrep -f "run_api.py|scheduler_daemon.py" || true)
if [ -n "$REMAINING" ]; then
    echo "警告: 发现残留进程，强制终止..."
    pkill -9 -f "run_api.py" 2>/dev/null || true
    pkill -9 -f "scheduler_daemon.py" 2>/dev/null || true
    sleep 1
fi

echo ""
echo "================================================"
echo "所有服务已停止"
echo "================================================"
