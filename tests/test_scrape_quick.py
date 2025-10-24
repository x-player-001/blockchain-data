#!/usr/bin/env python3
"""
快速测试：使用旧的两步方式爬取（更稳定）
"""

from src.services.dexscreener_service import DexScreenerService

def test_scrape_count():
    """测试能爬取多少代币"""

    print("\n" + "="*60)
    print("快速测试：爬取代币数量")
    print("="*60 + "\n")

    service = DexScreenerService()

    # 使用旧的稳定方法：先爬取地址
    print("步骤1: 爬取交易对地址...")
    pairs = service.scrape_bsc_page(
        target_count=100,
        headless=True  # 无头模式
    )

    print(f"\n✓ 已爬取 {len(pairs)} 个交易对地址")

    # 取前30个测试API
    test_pairs = pairs[:30]
    print(f"\n步骤2: 获取前{len(test_pairs)}个交易对的详细信息...")

    detailed_tokens = service.fetch_pair_details(
        pair_addresses=[p['pair_address'] for p in test_pairs],
        delay=0.2
    )

    print(f"\n✓ 成功获取 {len(detailed_tokens)} 个代币详情")

    # 显示前5个
    print("\n" + "="*60)
    print("前5个代币:")
    print("="*60)

    for i, token in enumerate(detailed_tokens[:5], 1):
        symbol = token.get('baseToken', {}).get('symbol', 'UNKNOWN')
        price = token.get('priceUsd', 'N/A')
        change_24h = token.get('priceChange', {}).get('h24', 'N/A')

        print(f"\n{i}. {symbol}")
        print(f"   价格: ${price}")
        print(f"   24h涨幅: {change_24h}%")

    # 按涨幅排序
    tokens_with_change = [
        t for t in detailed_tokens
        if t.get('priceChange', {}).get('h24') is not None
    ]

    sorted_tokens = sorted(
        tokens_with_change,
        key=lambda x: float(x.get('priceChange', {}).get('h24', 0)),
        reverse=True
    )

    print("\n" + "="*60)
    print("Top 5 涨幅榜:")
    print("="*60)

    for i, token in enumerate(sorted_tokens[:5], 1):
        symbol = token.get('baseToken', {}).get('symbol', 'UNKNOWN')
        price = token.get('priceUsd', 'N/A')
        change_24h = float(token.get('priceChange', {}).get('h24', 0))

        print(f"{i}. {symbol:12s} +{change_24h:>7.2f}%  ${price}")

    print("\n" + "="*60)
    print(f"总结：")
    print(f"  爬取地址: {len(pairs)} 个")
    print(f"  获取详情: {len(detailed_tokens)} 个")
    print(f"  有涨幅数据: {len(tokens_with_change)} 个")
    print("="*60 + "\n")


if __name__ == '__main__':
    test_scrape_count()
