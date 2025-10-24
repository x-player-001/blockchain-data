# Linux服务器部署指南

本文档说明如何在Linux服务器上部署Selenium爬虫。

## 问题说明

DexScreener使用Cloudflare保护，在Linux无GUI环境下运行Selenium需要特殊配置。

## 解决方案

### 方案1：使用undetected-chromedriver（推荐）

#### 安装步骤

```bash
# 1. 安装Chrome浏览器（Ubuntu/Debian）
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt-get update
sudo apt-get install -y google-chrome-stable

# 2. 安装Python依赖
pip install undetected-chromedriver

# 3. 安装虚拟显示（可选，提高成功率）
sudo apt-get install -y xvfb

# 4. 运行爬虫
# 方式A：直接运行
python3 -m src.main collect-dexscreener-homepage-fast --target-count 100

# 方式B：使用Xvfb（推荐）
xvfb-run python3 -m src.main collect-dexscreener-homepage-fast --target-count 100
```

#### 代码说明

代码已自动支持undetected-chromedriver：
- 如果安装了`undetected-chromedriver`，自动使用
- 如果未安装，回退到普通Chrome
- 日志会显示使用的是哪种驱动

### 方案2：Docker部署（最简单）

#### Dockerfile

```dockerfile
FROM selenium/standalone-chrome:latest

USER root

# 安装Python
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# 安装Python依赖
WORKDIR /app
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# 复制代码
COPY . .

# 运行
CMD ["python3", "-m", "src.main", "collect-dexscreener-homepage-fast", "--target-count", "100"]
```

#### 构建和运行

```bash
# 构建镜像
docker build -t blockchain-scraper .

# 运行
docker run --rm blockchain-scraper
```

### 方案3：CentOS/RHEL系统

```bash
# 1. 添加Chrome仓库
cat <<EOF | sudo tee /etc/yum.repos.d/google-chrome.repo
[google-chrome]
name=google-chrome
baseurl=http://dl.google.com/linux/chrome/rpm/stable/x86_64
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
EOF

# 2. 安装Chrome
sudo yum install -y google-chrome-stable

# 3. 安装依赖
sudo yum install -y xorg-x11-server-Xvfb
pip install undetected-chromedriver

# 4. 运行
xvfb-run python3 -m src.main collect-dexscreener-homepage-fast
```

## 验证安装

```bash
# 检查Chrome版本
google-chrome --version

# 检查Python包
pip list | grep undetected

# 测试运行
python3 -c "import undetected_chromedriver as uc; print('✓ undetected-chromedriver 已安装')"
```

## 常见问题

### 1. Chrome未找到

```bash
# 错误：selenium.common.exceptions.WebDriverException: Message: 'chromedriver' executable needs to be in PATH

# 解决：确保Chrome已安装
which google-chrome
google-chrome --version
```

### 2. 显示问题

```bash
# 错误：could not connect to display

# 解决：使用xvfb-run
xvfb-run python3 -m src.main collect-dexscreener-homepage-fast
```

### 3. Cloudflare拦截

```bash
# 现象：获取到0个代币

# 解决：
# 1. 确保安装了undetected-chromedriver
pip install undetected-chromedriver

# 2. 使用Xvfb
xvfb-run python3 -m src.main collect-dexscreener-homepage-fast

# 3. 增加等待时间（修改代码）
```

### 4. 权限问题

```bash
# 错误：Permission denied

# 解决：给Chrome可执行权限
sudo chmod +x /usr/bin/google-chrome
```

## 性能优化

### 1. Headless模式

代码默认使用非headless模式以提高成功率，但在Linux服务器上建议配合Xvfb使用。

### 2. 并发限制

Selenium爬虫不建议并发，建议按顺序执行。

### 3. 定时任务

```bash
# crontab示例：每小时运行一次
0 * * * * cd /path/to/blockchain-data && xvfb-run python3 -m src.main collect-dexscreener-homepage-fast --target-count 100 >> /var/log/scraper.log 2>&1
```

## 命令对比

### 快速方法（推荐）
```bash
# 直接从页面解析数据，无需API调用，约20秒
python3 -m src.main collect-dexscreener-homepage-fast --target-count 100 --max-age-days 30
```

### 完整方法
```bash
# Selenium + API调用，获取最完整数据，约3分钟
python3 -m src.main collect-dexscreener-homepage --target-count 100 --max-age-days 30
```

## 监控和日志

```bash
# 查看实时日志
tail -f /var/log/scraper.log

# 检查数据库
psql -U mac -d blockchain_data -c "SELECT COUNT(*) FROM dexscreener_tokens;"
```

## 故障排查

1. 查看日志中是否显示"使用 undetected-chromedriver"
2. 检查Chrome进程是否正常：`ps aux | grep chrome`
3. 测试基本功能：`python3 -c "from selenium import webdriver; print('OK')"`
4. 检查网络连接：`curl -I https://dexscreener.com`

## 总结

- **开发环境**：可以不用headless，直接运行
- **Linux服务器**：安装undetected-chromedriver + 使用xvfb-run
- **Docker部署**：使用官方selenium镜像，最简单
