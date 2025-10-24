#!/usr/bin/env python3
"""
测试改进后的爬虫：直接从HTML解析完整数据
"""

from src.services.dexscreener_service import DexScreenerService

def test_improved_scraper():
    """测试改进后的一次性爬取方法"""

    print("\n" + "="*60)
    print("测试改进后的爬虫：一次性爬取完整数据")
    print("="*60 + "\n")

    # 创建服务实例
    dex_service = DexScreenerService()

    # 使用新方法：直接从页面解析所有数据
    print("开始爬取DexScreener BSC页面（一次性获取完整数据）...")
    print("  目标: 50个交易对（测试用）")
    print("  模式: 有头浏览器（绕过Cloudflare）\n")

    tokens = dex_service.scrape_bsc_page_with_details(
        target_count=50,
        headless=False  # 使用有头模式绕过Cloudflare
    )

    print(f"\n✓ 已爬取 {len(tokens)} 个交易对（含完整数据）\n")

    # 显示前10个代币的详细信息
    print("="*60)
    print("前10个代币详细信息")
    print("="*60)

    for i, token in enumerate(tokens[:10], 1):
        base_token = token.get('baseToken', {})
        symbol = base_token.get('symbol', 'UNKNOWN')
        name = base_token.get('name', 'Unknown')
        price = token.get('priceUsd', 'N/A')

        price_change = token.get('priceChange', {})
        change_5m = price_change.get('m5', 'N/A')
        change_1h = price_change.get('h1', 'N/A')
        change_6h = price_change.get('h6', 'N/A')
        change_24h = price_change.get('h24', 'N/A')

        liquidity = token.get('liquidity', {})
        liquidity_usd = liquidity.get('usd', 'N/A') if liquidity else 'N/A'

        volume = token.get('volume', {})
        volume_24h = volume.get('h24', 'N/A') if volume else 'N/A'

        market_cap = token.get('marketCap', 'N/A')

        print(f"\n{i}. {symbol} ({name})")
        print(f"   价格: ${price}")
        print(f"   涨幅: 5m={change_5m}% | 1h={change_1h}% | 6h={change_6h}% | 24h={change_24h}%")
        if liquidity_usd != 'N/A':
            print(f"   流动性: ${liquidity_usd:,.0f}")
        if volume_24h != 'N/A':
            print(f"   24h成交量: ${volume_24h:,.0f}")
        if market_cap != 'N/A':
            print(f"   市值: ${market_cap:,.0f}")

    # 筛选有24h涨幅数据的代币
    print("\n" + "="*60)
    print("按24h涨幅排序")
    print("="*60)

    tokens_with_change = [
        t for t in tokens
        if t.get('priceChange', {}).get('h24') is not None
    ]

    sorted_tokens = sorted(
        tokens_with_change,
        key=lambda x: float(x.get('priceChange', {}).get('h24', 0)),
        reverse=True
    )

    print(f"\n找到 {len(tokens_with_change)} 个有24h涨幅数据的代币\n")
    print("Top 10 涨幅榜:")
    print("-"*60)

    for i, token in enumerate(sorted_tokens[:10], 1):
        base_token = token.get('baseToken', {})
        symbol = base_token.get('symbol', 'UNKNOWN')
        price = token.get('priceUsd', 'N/A')
        change_24h = float(token.get('priceChange', {}).get('h24', 0))

        print(f"{i}. {symbol:12s} | 价格: ${price:12s} | 24h涨幅: +{change_24h:.2f}%")

    print("\n" + "="*60)
    print("测试完成！")
    print("="*60 + "\n")


if __name__ == '__main__':
    test_improved_scraper()
