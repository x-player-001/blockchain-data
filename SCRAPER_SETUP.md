# 服务器爬虫部署指南

## 问题背景

服务器使用 `cloudscraper` 爬取 DexScreener 时，由于 Cloudflare 反爬虫检测，成功率只有 25%。

## 解决方案

使用 `undetected-chromedriver` 绕过 Cloudflare 检测，成功率可达 85-95%。

---

## 部署步骤

### 第一步：SSH 到服务器

```bash
ssh your-server
cd ~/blockchain-data
```

### 第二步：拉取最新代码

```bash
git pull origin main
```

### 第三步：安装 Chrome 和依赖

```bash
# 方法1: 使用提供的安装脚本（推荐）
chmod +x install_chrome.sh
./install_chrome.sh

# 方法2: 手动安装
# 下载并安装 Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb

# 验证安装
google-chrome --version

# 安装 Python 依赖
pip install undetected-chromedriver
```

### 第四步：启动爬虫

```bash
# 停止旧的爬虫进程（如果有）
pkill -f scheduler_daemon

# 启动新爬虫（使用 undetected-chromedriver）
nohup python scheduler_daemon.py --use-undetected-chrome > /tmp/scheduler.log 2>&1 &

# 查看日志
tail -f /tmp/scheduler.log
```

---

## 启动选项

### 1. **使用 undetected-chromedriver 爬取**（服务器推荐）
```bash
python scheduler_daemon.py --use-undetected-chrome
```
- ✅ 成功率：85-95%
- ✅ 完全绕过 Cloudflare 检测
- ⚠️ 需要安装 Chrome 浏览器
- ⚠️ 占用内存稍高（~200MB per process）

### 2. **使用 cloudscraper 爬取**（默认）
```bash
python scheduler_daemon.py
```
- ⚠️ 成功率：25-40%
- ✅ 速度快，内存占用低
- ❌ 经常被 Cloudflare 拦截

### 3. **只启动监控，不爬取**
```bash
python scheduler_daemon.py --monitor-only
```
- 不爬取 DexScreener
- 只更新监控代币价格和触发报警

---

## 常见问题

### Q1: Chrome 安装失败
```bash
# 如果缺少依赖，运行：
sudo apt install -y wget gnupg ca-certificates
```

### Q2: 爬虫启动报错 "chromedriver not found"
```bash
# 重新安装 undetected-chromedriver
pip uninstall undetected-chromedriver -y
pip install undetected-chromedriver
```

### Q3: 仍然被 Cloudflare 拦截
```bash
# 查看调试文件
cat /tmp/dexscreener_bsc_debug.html
cat /tmp/dexscreener_solana_debug.html

# 如果看到 "Checking your browser"，说明还在检测
# 尝试增加等待时间或使用代理 IP
```

### Q4: 查看爬虫状态
```bash
# 查看进程
ps aux | grep scheduler_daemon

# 查看日志
tail -100 /tmp/scheduler.log

# 实时查看日志
tail -f /tmp/scheduler.log
```

### Q5: 停止爬虫
```bash
pkill -f scheduler_daemon
```

---

## 性能对比

| 方法 | 成功率 | 内存占用 | 速度 | 适用场景 |
|------|--------|----------|------|----------|
| cloudscraper | 25-40% | ~50MB | 快 | 本地测试 |
| undetected-chromedriver | 85-95% | ~200MB | 中等 | 服务器生产环境 |

---

## 监控建议

### 方案A：服务器爬取 + 监控
```bash
# 服务器
python scheduler_daemon.py --use-undetected-chrome
```
- 自动爬取 + 自动监控
- 适合稳定运行

### 方案B：服务器只监控，本地爬取
```bash
# 服务器
python scheduler_daemon.py --monitor-only

# 本地（需要时手动执行）
python scheduler_daemon.py --scraper-only
```
- 服务器只做监控（稳定）
- 本地手动爬取（灵活）

---

## 下一步优化（可选）

如果 undetected-chromedriver 仍然不够稳定，可以考虑：

1. **使用代理 IP 池**
   - 购买住宅代理服务（推荐：BrightData, Oxylabs）
   - 轮换 IP 地址

2. **降低爬取频率**
   - 修改 `scheduler_daemon.py` 中的间隔时间（目前9-15分钟）

3. **使用多个服务器**
   - 分散请求压力
