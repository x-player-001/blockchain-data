#!/usr/bin/env python3
"""
测试监控功能
"""

import asyncio
from src.services.token_monitor_service import TokenMonitorService
from src.services.dexscreener_service import DexScreenerService

async def test_scrape_and_filter():
    """测试爬取DexScreener首页并按涨幅筛选"""

    print("\n" + "="*60)
    print("测试：爬取DexScreener首页代币并按涨幅筛选")
    print("="*60 + "\n")

    # 创建服务实例
    dex_service = DexScreenerService()

    # 步骤1: 爬取首页
    print("步骤1: 爬取DexScreener BSC首页...")
    print("  目标: 获取50个交易对（测试用）")
    print("  模式: 无头浏览器\n")

    pair_data = dex_service.scrape_bsc_page(
        target_count=50,  # 测试只抓取50个
        headless=True,
        max_scrolls=20
    )

    print(f"\n✓ 已爬取 {len(pair_data)} 个交易对\n")

    # 步骤2: 获取详细信息
    print("步骤2: 获取交易对详细信息...")
    pair_addresses = [p['pair_address'] for p in pair_data[:50]]  # 限制前50个

    detailed_tokens = dex_service.fetch_pair_details(pair_addresses[:30], delay=0.3)  # 先测试30个

    print(f"\n✓ 已获取 {len(detailed_tokens)} 个代币详情\n")

    # 步骤3: 筛选有涨幅数据的代币
    print("步骤3: 筛选有24h涨幅数据的代币...")

    tokens_with_change = [
        t for t in detailed_tokens
        if t.get('priceChange', {}).get('h24') is not None
    ]

    print(f"✓ 找到 {len(tokens_with_change)} 个有涨幅数据的代币\n")

    # 步骤4: 按涨幅排序
    print("步骤4: 按24h涨幅排序...")

    sorted_tokens = sorted(
        tokens_with_change,
        key=lambda x: float(x.get('priceChange', {}).get('h24', 0)),
        reverse=True
    )

    # 显示Top 10
    print("\n" + "="*60)
    print("Top 10 涨幅榜")
    print("="*60)

    for i, token in enumerate(sorted_tokens[:10], 1):
        base_token = token.get('baseToken', {})
        symbol = base_token.get('symbol', 'UNKNOWN')
        name = base_token.get('name', 'Unknown')
        price = float(token.get('priceUsd', 0))
        change_24h = float(token.get('priceChange', {}).get('h24', 0))
        liquidity = float(token.get('liquidity', {}).get('usd', 0)) if token.get('liquidity') else 0
        volume = float(token.get('volume', {}).get('h24', 0)) if token.get('volume') else 0

        print(f"\n{i}. {symbol} ({name})")
        print(f"   价格: ${price:.8f}")
        print(f"   24h涨幅: +{change_24h:.2f}%")
        print(f"   流动性: ${liquidity:,.2f}")
        print(f"   24h成交量: ${volume:,.2f}")

    print("\n" + "="*60)
    print("测试完成！")
    print("="*60 + "\n")

    return sorted_tokens[:10]


async def test_add_to_monitor():
    """测试添加到监控表"""

    print("\n" + "="*60)
    print("测试：添加Top 5涨幅代币到监控表")
    print("="*60 + "\n")

    monitor_service = TokenMonitorService()

    try:
        result = await monitor_service.scrape_and_add_top_gainers(
            count=50,        # 抓取50个
            top_n=5,         # 只取前5名
            drop_threshold=15.0,  # 15%跌幅报警
            headless=True
        )

        print("\n✓ 添加监控完成！")
        print(f"  已抓取: {result['scraped']} 个交易对")
        print(f"  获取详情: {result['detailed']} 个代币")
        print(f"  涨幅榜: {result['top_gainers']} 个")
        print(f"  已添加监控: {result['added_to_monitor']} 个\n")

        # 查询监控列表
        print("="*60)
        print("当前监控列表:")
        print("="*60)

        monitored = await monitor_service.get_active_monitored_tokens(limit=10)

        for i, token in enumerate(monitored, 1):
            print(f"\n{i}. {token['token_symbol']}")
            print(f"   入场价: ${token['entry_price_usd']:.8f}")
            print(f"   峰值价: ${token['peak_price_usd']:.8f}")
            print(f"   入场涨幅: +{token.get('price_change_24h_at_entry', 0):.2f}%")
            print(f"   状态: {token['status']}")

        print("\n" + "="*60 + "\n")

    finally:
        await monitor_service.close()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'monitor':
        # 测试添加到监控
        asyncio.run(test_add_to_monitor())
    else:
        # 测试爬取和筛选
        asyncio.run(test_scrape_and_filter())
