#!/bin/bash
# 在 Ubuntu 服务器上安装 Chrome 和爬虫依赖

echo "================================"
echo "安装 Chrome 和爬虫依赖"
echo "================================"

# 1. 更新软件包列表
echo "1. 更新软件包列表..."
sudo apt update

# 2. 下载 Google Chrome
echo "2. 下载 Google Chrome..."
cd /tmp
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# 3. 安装 Chrome
echo "3. 安装 Chrome..."
sudo apt install -y ./google-chrome-stable_current_amd64.deb

# 4. 验证安装
echo "4. 验证 Chrome 安装..."
google-chrome --version

# 5. 安装 Python 依赖
echo "5. 安装 Python 依赖..."
pip install undetected-chromedriver

echo ""
echo "================================"
echo "✅ 安装完成！"
echo "================================"
echo ""
echo "现在可以使用以下命令启动爬虫："
echo "  python scheduler_daemon.py --use-undetected-chrome"
echo ""
