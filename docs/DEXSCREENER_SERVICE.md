# DexScreener 服务使用文档

本文档介绍如何使用封装好的 `DexScreenerService` 类来爬取、导入和管理 DexScreener 代币数据。

## 📦 功能概述

`DexScreenerService` 提供了完整的 DexScreener 数据处理功能：

- ✅ **爬取功能**：使用 Selenium 爬取 DexScreener BSC 页面
- ✅ **数据获取**：调用 DexScreener API 获取详细代币信息
- ✅ **数据解析**：解析原始 JSON 数据为结构化字段
- ✅ **数据库导入**：批量导入代币数据到 PostgreSQL
- ✅ **去重功能**：删除重复代币，保留流动性最大的交易对
- ✅ **一键操作**：完整的自动化流程

## 🚀 快速开始

### 1. 一键爬取并导入（最简单）

```python
import asyncio
from src.services.dexscreener_service import quick_scrape_and_import

async def main():
    # 一键完成：爬取 -> 导入 -> 去重
    result = await quick_scrape_and_import(
        target_count=100,      # 爬取100个代币
        headless=True,         # 使用无头浏览器
        deduplicate=True       # 自动去重
    )

    print(f"成功: {result['success']}")
    print(f"最终记录数: {result['final_count']}")

asyncio.run(main())
```

### 2. 使用服务类（更灵活）

```python
import asyncio
from src.services.dexscreener_service import DexScreenerService

async def main():
    # 创建服务实例
    service = DexScreenerService()

    try:
        # 方式1: 一键操作
        result = await service.scrape_and_import(
            target_count=100,
            headless=True,
            deduplicate=True,
            save_json=True,
            json_path="/tmp/my_tokens.json"
        )

        print(f"✓ 操作完成！最终有 {result['final_count']} 条记录")

    finally:
        await service.close()

asyncio.run(main())
```

## 📖 详细用法

### 单独使用各个功能

#### 1️⃣ 只爬取数据（不导入数据库）

```python
from src.services.dexscreener_service import DexScreenerService

service = DexScreenerService()

# 方法1: 只获取交易对地址
pairs = service.scrape_bsc_page(
    target_count=100,
    headless=False,    # 显示浏览器窗口
    max_scrolls=50
)

print(f"获取到 {len(pairs)} 个交易对")
for pair in pairs[:5]:
    print(f"  - {pair['pair_address']}")

# 方法2: 获取完整数据并保存到JSON
tokens = service.scrape_and_fetch(
    target_count=100,
    output_file="my_tokens.json",
    headless=True
)

print(f"获取到 {len(tokens)} 个代币的完整数据")
```

#### 2️⃣ 只导入数据（已有JSON文件）

```python
import asyncio
from src.services.dexscreener_service import DexScreenerService

async def import_data():
    service = DexScreenerService()

    try:
        # 从JSON文件导入
        stats = await service.import_from_json(
            "dexscreener_tokens.json",
            update_existing=True  # 更新已存在的记录
        )

        print(f"插入: {stats['inserted']}")
        print(f"更新: {stats['updated']}")
        print(f"错误: {stats['errors']}")

    finally:
        await service.close()

asyncio.run(import_data())
```

#### 3️⃣ 只执行去重

```python
import asyncio
from src.services.dexscreener_service import DexScreenerService

async def dedupe():
    service = DexScreenerService()

    try:
        # 预览模式
        preview = await service.deduplicate_tokens(dry_run=True)
        print(f"将删除 {preview['pairs_to_delete']} 条重复记录")

        # 查看详情
        for info in preview['duplicate_info']:
            print(f"\n代币: {info['token_symbol']}")
            print(f"  保留: {info['keep']['pair_address']}")
            print(f"  删除: {len(info['delete'])} 个交易对")

        # 确认后执行删除
        result = await service.deduplicate_tokens(dry_run=False)
        print(f"\n✓ 已删除 {result['pairs_to_delete']} 条记录")
        print(f"✓ 剩余 {result['remaining_records']} 条记录")

    finally:
        await service.close()

asyncio.run(dedupe())
```

#### 4️⃣ 获取API详细数据

```python
from src.services.dexscreener_service import DexScreenerService

service = DexScreenerService()

# 为已知的交易对地址获取详细信息
pair_addresses = [
    "0xCAaF3c41a40103a23Eeaa4BbA468AF3cF5b0e0D8",
    "0xcF59B8C8BAA2dea520e3D549F97d4e49aDE17057"
]

details = service.fetch_pair_details(
    pair_addresses,
    delay=0.3  # 请求间隔（秒）
)

for token in details:
    print(f"{token['baseToken']['symbol']}: ${token['priceUsd']}")
```

### 组合使用

#### 场景1: 爬取新数据并与现有数据合并

```python
import asyncio
from src.services.dexscreener_service import DexScreenerService

async def refresh_data():
    service = DexScreenerService()

    try:
        # 1. 爬取最新数据
        print("爬取最新数据...")
        tokens = service.scrape_and_fetch(
            target_count=100,
            output_file="/tmp/latest_tokens.json",
            headless=True
        )

        # 2. 导入到数据库（更新已存在的）
        print("导入数据库...")
        stats = await service.import_tokens(
            tokens,
            update_existing=True
        )

        # 3. 去重
        print("执行去重...")
        await service.deduplicate_tokens(dry_run=False)

        # 4. 查看最终结果
        count = await service.get_token_count()
        print(f"\n✓ 完成！数据库中有 {count} 个代币")

    finally:
        await service.close()

asyncio.run(refresh_data())
```

#### 场景2: 定期更新数据

```python
import asyncio
from src.services.dexscreener_service import DexScreenerService
from datetime import datetime

async def scheduled_update():
    """每小时更新一次数据"""
    service = DexScreenerService()

    try:
        print(f"[{datetime.now()}] 开始更新...")

        result = await service.scrape_and_import(
            target_count=100,
            headless=True,
            deduplicate=True,
            save_json=True,
            json_path=f"/tmp/tokens_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        )

        if result['success']:
            print(f"✓ 更新成功！当前有 {result['final_count']} 个代币")
        else:
            print(f"✗ 更新失败: {result.get('error')}")

    finally:
        await service.close()

# 配合 APScheduler 或 crontab 使用
asyncio.run(scheduled_update())
```

## 🔧 高级配置

### 自定义数据库连接

```python
from src.services.dexscreener_service import DexScreenerService
from src.storage.db_manager import DatabaseManager

# 使用自己的数据库管理器
db_manager = DatabaseManager()
await db_manager.init_async_db()

service = DexScreenerService(db_manager=db_manager)

# ... 使用服务 ...

# 注意：使用自定义 db_manager 时，需要手动关闭
await db_manager.close()
```

### 自定义Chrome选项

```python
from src.services.dexscreener_service import DexScreenerService

service = DexScreenerService()

# 修改 setup_chrome_driver 方法
driver = service.setup_chrome_driver(headless=True)

# 或者继承并扩展
class CustomDexScreenerService(DexScreenerService):
    def setup_chrome_driver(self, headless=False):
        driver = super().setup_chrome_driver(headless)
        # 添加自定义选项
        return driver
```

### 数据解析自定义

```python
from src.services.dexscreener_service import DexScreenerService

# 使用静态方法解析数据
raw_data = {...}  # 原始DexScreener数据

parsed = DexScreenerService.parse_token_data(raw_data)

print(parsed['base_token_symbol'])
print(parsed['price_usd'])
print(parsed['liquidity_usd'])
```

## 📊 返回值说明

### scrape_and_import 返回值

```python
{
    "success": True,  # 是否成功
    "final_count": 81,  # 最终数据库记录数
    "steps": {
        "scrape": {
            "tokens_found": 100  # 爬取到的代币数
        },
        "import": {
            "inserted": 98,  # 新插入的记录
            "updated": 2,    # 更新的记录
            "errors": 0      # 错误数
        },
        "deduplicate": {
            "duplicate_tokens_count": 9,  # 有重复的代币数
            "pairs_to_delete": 17,        # 删除的交易对数
            "remaining_records": 81,       # 剩余记录数
            "deleted": True                # 是否执行了删除
        }
    }
}
```

### deduplicate_tokens 返回值

```python
{
    "duplicate_tokens_count": 9,  # 有重复的代币数
    "pairs_to_delete": 17,        # 要删除的交易对数
    "deleted": False,              # 是否已执行删除
    "duplicate_info": [            # 详细信息
        {
            "token_symbol": "USDT",
            "token_name": "Tether USD",
            "total_pairs": 3,
            "keep": {
                "pair_address": "0x...",
                "dex_id": "pancakeswap",
                "liquidity_usd": 1000000.0
            },
            "delete": [
                {
                    "pair_address": "0x...",
                    "dex_id": "uniswap",
                    "liquidity_usd": 500000.0
                }
            ]
        }
    ]
}
```

## ⚠️ 注意事项

### 1. Selenium依赖

需要安装Chrome浏览器和ChromeDriver：

```bash
# macOS
brew install --cask google-chrome
brew install chromedriver

# 或使用自动下载
pip install webdriver-manager
```

### 2. 请求频率限制

DexScreener API有请求频率限制，建议：
- 使用 `delay` 参数控制请求间隔（默认0.3秒）
- 不要并发请求过多
- 失败时实现重试机制

### 3. 内存使用

爬取大量数据时注意内存使用：
- 分批处理数据
- 使用 `save_json=True` 保存中间结果
- 及时关闭浏览器驱动

### 4. 数据库连接

```python
# 正确方式：使用 try-finally 确保关闭
service = DexScreenerService()
try:
    await service.scrape_and_import(...)
finally:
    await service.close()  # 重要！

# 或使用快捷函数（自动管理连接）
result = await quick_scrape_and_import(...)
```

## 🎯 最佳实践

### 1. 生产环境部署

```python
import asyncio
import logging
from src.services.dexscreener_service import DexScreenerService

logging.basicConfig(level=logging.INFO)

async def production_update():
    service = DexScreenerService()

    try:
        # 使用无头模式
        result = await service.scrape_and_import(
            target_count=100,
            headless=True,           # 生产环境必须使用无头模式
            deduplicate=True,
            save_json=True,
            json_path="/var/log/dexscreener/latest.json"
        )

        if not result['success']:
            # 发送告警
            logging.error(f"Update failed: {result.get('error')}")

        return result

    except Exception as e:
        logging.exception("Critical error during update")
        raise
    finally:
        await service.close()
```

### 2. 错误处理

```python
async def robust_scrape():
    service = DexScreenerService()
    max_retries = 3

    for attempt in range(max_retries):
        try:
            result = await service.scrape_and_import(
                target_count=100,
                headless=True
            )

            if result['success']:
                return result

        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                print(f"重试 {attempt + 1}/{max_retries}，等待 {wait_time}秒...")
                await asyncio.sleep(wait_time)
            else:
                raise

    await service.close()
```

### 3. 数据验证

```python
async def validate_and_import():
    service = DexScreenerService()

    try:
        # 爬取数据
        tokens = service.scrape_and_fetch(target_count=100)

        # 验证数据质量
        valid_tokens = [
            t for t in tokens
            if t.get('priceUsd') and
               t.get('liquidity', {}).get('usd', 0) > 1000
        ]

        print(f"过滤后剩余 {len(valid_tokens)} 个有效代币")

        # 导入验证后的数据
        stats = await service.import_tokens(valid_tokens)

        return stats

    finally:
        await service.close()
```

## 📚 相关文档

- [DexScreener API 文档](./DEXSCREENER_API.md) - API接口使用说明
- [数据库模型](../src/storage/models.py) - 数据表结构定义
- [原始脚本](../src/scripts/) - 独立的脚本工具

## 🆘 常见问题

### Q: 爬取失败返回空列表？

A: 检查以下几点：
- Chrome和ChromeDriver版本是否匹配
- 网络是否正常访问 dexscreener.com
- 尝试使用 `headless=False` 查看浏览器窗口
- 检查页面结构是否变化

### Q: 导入时出现数据库错误？

A: 确保：
- 数据库已初始化（运行过 `init_async_db()`）
- 数据库表已创建
- 字段精度足够（特别是 liquidity_base）

### Q: 去重逻辑是什么？

A: 按 `base_token_address` 分组，每组保留 `liquidity_usd` 最大的交易对，删除其他。

### Q: 如何只爬取特定DEX的数据？

A: 爬取后在导入前过滤：
```python
tokens = service.scrape_and_fetch(100)
pancake_tokens = [t for t in tokens if t.get('dexId') == 'pancakeswap']
await service.import_tokens(pancake_tokens)
```

## 💡 示例代码

完整示例请参考：
- [examples/dexscreener_example.py](../examples/dexscreener_example.py) - 基础用法示例
- [examples/dexscreener_advanced.py](../examples/dexscreener_advanced.py) - 高级用法示例
