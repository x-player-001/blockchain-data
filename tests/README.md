# 测试和工具脚本目录

本目录包含所有测试脚本、工具脚本和演示代码。

## 目录结构

```
tests/
├── README.md                           # 本文件
├── __init__.py                         # Python 包标识
│
├── 测试脚本
│   ├── test_api_speed.py              # API 性能测试
│   ├── test_api_speed_v2.py           # API 性能测试 v2
│   ├── test_full_workflow.py          # 完整工作流测试
│   ├── test_monitor.py                # 监控功能测试
│   ├── test_monitor_api.py            # 监控 API 测试
│   ├── test_monitor_update.py         # 监控更新测试
│   ├── test_scrape_quick.py           # 快速爬取测试
│   ├── test_scrape_update.py          # 爬取更新逻辑测试
│   └── test_scraper_improved.py       # 改进版爬虫测试
│
├── 工具脚本
│   ├── rescrape_and_monitor.py        # 重新爬取并添加监控（一站式脚本）
│   ├── scrape_potential_non_headless.py  # 非无头模式爬取（调试用）
│   ├── scrape_potential_tokens.py     # 爬取潜力代币
│   ├── update_ave_data.py             # 更新 AVE API 数据
│   └── update_potential_ave.py        # 更新潜力代币的 AVE 数据
│
└── 子目录
    ├── analysis/                       # 数据分析脚本
    ├── demo/                          # 演示代码
    └── tools/                         # 其他工具
```

## 脚本说明

### 测试脚本

#### test_monitor_api.py
完整的监控 API 测试，验证所有返回字段。

```bash
python3 tests/test_monitor_api.py
```

#### test_scrape_update.py
测试爬取更新逻辑（智能比较涨幅）。

```bash
python3 tests/test_scrape_update.py
```

#### test_full_workflow.py
测试完整的监控流程（爬取 → 添加监控 → 更新价格 → 触发报警）。

```bash
python3 tests/test_full_workflow.py
```

### 工具脚本

#### rescrape_and_monitor.py
一站式脚本，重新爬取并添加到监控。

```bash
python3 tests/rescrape_and_monitor.py
```

#### scrape_potential_non_headless.py
使用非无头模式爬取（可以看到浏览器界面，用于调试）。

```bash
python3 tests/scrape_potential_non_headless.py
```

#### update_ave_data.py
更新监控代币的 AVE API 数据（60+字段）。

```bash
python3 tests/update_ave_data.py
```

#### update_potential_ave.py
更新潜力代币的 AVE API 数据。

```bash
python3 tests/update_potential_ave.py
```

## 使用场景

### 场景1: 测试爬虫功能

```bash
# 快速测试爬取（不保存数据库）
python3 tests/test_scrape_quick.py

# 测试爬取并保存
python3 tests/scrape_potential_tokens.py
```

### 场景2: 测试监控功能

```bash
# 测试监控 API
python3 tests/test_monitor_api.py

# 测试价格更新和报警
python3 tests/test_monitor_update.py
```

### 场景3: 调试爬虫问题

```bash
# 使用非无头模式查看浏览器行为
python3 tests/scrape_potential_non_headless.py
```

### 场景4: 手动更新数据

```bash
# 手动更新 AVE 数据
python3 tests/update_ave_data.py

# 重新爬取并添加监控
python3 tests/rescrape_and_monitor.py
```

## 注意事项

1. **运行位置**: 所有脚本都应该从项目根目录运行
   ```bash
   cd /path/to/blockchain-data
   python3 tests/test_*.py
   ```

2. **数据库连接**: 确保 PostgreSQL 正在运行
   ```bash
   sudo systemctl start postgresql-14
   ```

3. **浏览器依赖**: 爬虫脚本需要 Chrome 和 undetected-chromedriver
   ```bash
   pip3 install undetected-chromedriver
   ```

4. **API 服务**: 某些测试需要 API 服务运行
   ```bash
   python3 run_api.py &
   ```

## 相关文档

- [部署文档](../deployment/CENTOS_DEPLOYMENT.md)
- [爬取更新逻辑](../SCRAPE_UPDATE_LOGIC.md)
- [部署总结](../DEPLOYMENT_SUMMARY.md)
