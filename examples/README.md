# DexScreener 示例代码

本目录包含 DexScreener 服务的使用示例代码。

## 📁 文件说明

### 1. [dexscreener_example.py](dexscreener_example.py)
**基础用法示例** - 适合初学者

包含7个示例：
1. ✨ 快捷函数 - 一键爬取并导入
2. 🔧 分步操作 - 爬取、导入、去重
3. 📥 只爬取数据（不导入数据库）
4. 💾 从JSON文件导入数据
5. 🧹 去重现有数据
6. 🔍 爬取并过滤高质量代币
7. 🔄 增量更新现有数据

### 2. [dexscreener_advanced.py](dexscreener_advanced.py)
**高级用法示例** - 适合生产环境

包含6个高级示例：
1. 🔁 错误重试机制
2. ⏰ 定时更新任务
3. 📊 数据质量分析
4. 🎯 自定义过滤器
5. 📦 批量操作
6. 📤 数据导出（CSV/JSON）

## 🚀 快速开始

### 运行基础示例

```bash
# 交互式运行
python3 examples/dexscreener_example.py

# 直接运行特定示例（修改代码中的main函数）
python3 -c "
import asyncio
from examples.dexscreener_example import example1_quickstart
asyncio.run(example1_quickstart())
"
```

### 运行高级示例

```bash
# 交互式运行
python3 examples/dexscreener_advanced.py

# 运行数据质量分析
python3 -c "
import asyncio
from examples.dexscreener_advanced import example3_data_quality_analysis
asyncio.run(example3_data_quality_analysis())
"
```

## 📖 代码片段

### 最简单的用法

```python
import asyncio
from src.services.dexscreener_service import quick_scrape_and_import

async def main():
    result = await quick_scrape_and_import(
        target_count=100,
        headless=True,
        deduplicate=True
    )
    print(f"成功: {result['success']}")
    print(f"最终记录数: {result['final_count']}")

asyncio.run(main())
```

### 分步操作

```python
import asyncio
from src.services.dexscreener_service import DexScreenerService

async def main():
    service = DexScreenerService()

    try:
        # 1. 爬取
        tokens = service.scrape_and_fetch(target_count=100, headless=True)

        # 2. 导入
        stats = await service.import_tokens(tokens)

        # 3. 去重
        await service.deduplicate_tokens(dry_run=False)

        # 4. 查看结果
        count = await service.get_token_count()
        print(f"数据库中有 {count} 个代币")

    finally:
        await service.close()

asyncio.run(main())
```

### 只爬取不导入

```python
from src.services.dexscreener_service import DexScreenerService

service = DexScreenerService()

# 获取数据并保存到JSON
tokens = service.scrape_and_fetch(
    target_count=100,
    output_file="my_tokens.json",
    headless=True
)

print(f"获取到 {len(tokens)} 个代币")
```

### 从JSON导入

```python
import asyncio
from src.services.dexscreener_service import DexScreenerService

async def main():
    service = DexScreenerService()

    try:
        stats = await service.import_from_json(
            "my_tokens.json",
            update_existing=True
        )
        print(f"插入: {stats['inserted']}, 更新: {stats['updated']}")
    finally:
        await service.close()

asyncio.run(main())
```

### 数据过滤

```python
import asyncio
from src.services.dexscreener_service import DexScreenerService

async def main():
    service = DexScreenerService()

    try:
        # 爬取数据
        tokens = service.scrape_and_fetch(100)

        # 过滤高流动性代币
        filtered = [
            t for t in tokens
            if t.get('liquidity', {}).get('usd', 0) > 50000
        ]

        # 导入过滤后的数据
        stats = await service.import_tokens(filtered)
        print(f"导入了 {stats['inserted']} 个高流动性代币")

    finally:
        await service.close()

asyncio.run(main())
```

## 🎯 使用场景

### 场景1: 首次收集数据

```bash
python3 -c "
import asyncio
from src.services.dexscreener_service import quick_scrape_and_import

asyncio.run(quick_scrape_and_import(
    target_count=100,
    headless=True,
    deduplicate=True
))
"
```

### 场景2: 定期更新数据

将以下代码添加到crontab或使用APScheduler：

```python
# update_tokens.py
import asyncio
from src.services.dexscreener_service import DexScreenerService

async def update():
    service = DexScreenerService()
    try:
        result = await service.scrape_and_import(
            target_count=100,
            headless=True,
            deduplicate=True
        )
        print(f"更新完成: {result['final_count']} 个代币")
    finally:
        await service.close()

asyncio.run(update())
```

```bash
# 添加到crontab（每小时运行）
0 * * * * cd /path/to/project && python3 update_tokens.py
```

### 场景3: 数据分析

```python
import asyncio
from examples.dexscreener_advanced import example3_data_quality_analysis

# 分析数据库中的数据质量
asyncio.run(example3_data_quality_analysis())
```

### 场景4: 导出报告

```python
import asyncio
from examples.dexscreener_advanced import example6_data_export

# 导出Top代币为CSV和JSON
asyncio.run(example6_data_export())
```

## 📝 注意事项

1. **Chrome依赖**
   - 需要安装Chrome浏览器和ChromeDriver
   - macOS: `brew install --cask google-chrome && brew install chromedriver`

2. **数据库初始化**
   - 首次使用前需要初始化数据库
   - 参考 [DEXSCREENER_API.md](../docs/DEXSCREENER_API.md)

3. **请求频率**
   - DexScreener API有请求限制
   - 建议使用默认的 `delay=0.3` 秒

4. **资源清理**
   - 使用 `try-finally` 确保调用 `service.close()`
   - 或使用快捷函数（自动管理资源）

5. **错误处理**
   - 生产环境建议实现重试机制
   - 参考高级示例中的错误处理代码

## 🔗 相关文档

- [DexScreener Service 文档](../docs/DEXSCREENER_SERVICE.md) - 完整的API文档
- [DexScreener API 文档](../docs/DEXSCREENER_API.md) - REST API接口说明
- [服务类源码](../src/services/dexscreener_service.py) - 实现代码

## 💡 提示

1. **开发调试**: 使用 `headless=False` 查看浏览器窗口
2. **减少爬取数量**: 开发时使用 `target_count=20` 加快测试
3. **保存中间结果**: 使用 `save_json=True` 保存原始数据
4. **数据验证**: 导入前先检查数据质量
5. **增量更新**: 使用 `update_existing=True` 更新现有记录

## 🆘 常见问题

**Q: 如何运行示例？**
A: `python3 examples/dexscreener_example.py` 然后选择示例编号

**Q: 示例运行失败？**
A: 检查：
   - 数据库是否已初始化
   - Chrome/ChromeDriver是否已安装
   - 网络连接是否正常

**Q: 如何修改爬取数量？**
A: 修改 `target_count` 参数，例如 `target_count=50`

**Q: 如何只爬取不导入？**
A: 使用 `service.scrape_and_fetch()` 方法，不调用导入相关方法

**Q: 如何导出数据？**
A: 参考 `dexscreener_advanced.py` 中的 `example6_data_export`

## 📞 获取帮助

- 查看文档: [docs/DEXSCREENER_SERVICE.md](../docs/DEXSCREENER_SERVICE.md)
- 查看源码: [src/services/dexscreener_service.py](../src/services/dexscreener_service.py)
- 运行示例: 本目录中的 `.py` 文件
