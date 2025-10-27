"""
测试爬虫筛选功能
- 运行爬取模块
- 保存HTML
- 分析缺失数据
- 测试筛选逻辑
"""

import asyncio
import json
from datetime import datetime
from src.services.dexscreener_service import DexScreenerService


async def test_scraper():
    print("="*80)
    print("开始测试爬虫模块")
    print("="*80)

    service = DexScreenerService()

    # 测试 BSC 链
    chain = 'bsc'
    print(f"\n爬取 {chain.upper()} 链...")

    # 使用 undetected-chromedriver（服务器使用的方法）
    tokens = service.scrape_with_undetected_chrome(
        chain=chain,
        limit=100
    )

    print(f"\n{'='*80}")
    print(f"爬取结果统计")
    print(f"{'='*80}")
    print(f"总共爬取: {len(tokens)} 个代币")

    # 分析数据完整性
    complete_data = []
    missing_price_change = []
    missing_market_cap = []
    missing_liquidity = []
    missing_age = []

    for token in tokens:
        issues = []

        if token.get('price_change_24h') is None:
            missing_price_change.append(token)
            issues.append('price_change_24h')

        if token.get('market_cap') is None:
            missing_market_cap.append(token)
            issues.append('market_cap')

        if token.get('liquidity_usd') is None:
            missing_liquidity.append(token)
            issues.append('liquidity_usd')

        if token.get('age_days') is None:
            missing_age.append(token)
            issues.append('age')

        if not issues:
            complete_data.append(token)
        else:
            token['missing_fields'] = issues

    print(f"\n数据完整性分析:")
    print(f"  完整数据: {len(complete_data)} 个")
    print(f"  缺少 price_change_24h: {len(missing_price_change)} 个")
    print(f"  缺少 market_cap: {len(missing_market_cap)} 个")
    print(f"  缺少 liquidity_usd: {len(missing_liquidity)} 个")
    print(f"  缺少 age: {len(missing_age)} 个")

    # 显示缺少24h涨幅的代币详情
    if missing_price_change:
        print(f"\n缺少24h涨幅的代币详情:")
        print(f"  {'序号':<6} {'符号':<12} {'价格':<15} {'缺失字段'}")
        print(f"  {'-'*70}")
        for i, token in enumerate(missing_price_change[:10], 1):
            symbol = token.get('token_symbol', 'N/A')
            price = token.get('price_usd', 0)
            missing = ', '.join(token.get('missing_fields', []))
            print(f"  {i:<6} {symbol:<12} ${price:<14.8f} {missing}")

    # 保存完整数据到JSON
    output_file = '/tmp/scraper_test_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tokens, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n完整数据已保存到: {output_file}")

    # 测试筛选逻辑
    print(f"\n{'='*80}")
    print(f"测试筛选逻辑")
    print(f"{'='*80}")

    # 筛选条件
    min_market_cap = 500000  # 50万美元
    min_liquidity = 50000    # 5万美元
    max_token_age_days = 1   # 1天

    print(f"\n筛选条件:")
    print(f"  市值 >= ${min_market_cap:,.0f}")
    print(f"  流动性 >= ${min_liquidity:,.0f}")
    print(f"  代币年龄 <= {max_token_age_days} 天")

    # 只筛选有24h涨幅的代币
    tokens_with_change = [t for t in tokens if t.get('price_change_24h') is not None]

    filtered_tokens = []
    filtered_by_market_cap = 0
    filtered_by_liquidity = 0
    filtered_by_age = 0

    for token in tokens_with_change:
        # 检查市值
        market_cap = token.get('market_cap')
        if market_cap is None or market_cap < min_market_cap:
            filtered_by_market_cap += 1
            continue

        # 检查流动性
        liquidity = token.get('liquidity_usd')
        if liquidity is None or liquidity < min_liquidity:
            filtered_by_liquidity += 1
            continue

        # 检查代币年龄
        age_days = token.get('age_days')
        if age_days is None or age_days > max_token_age_days:
            filtered_by_age += 1
            continue

        filtered_tokens.append(token)

    print(f"\n筛选结果:")
    print(f"  有24h涨幅: {len(tokens_with_change)} 个")
    print(f"  过滤（市值）: {filtered_by_market_cap} 个")
    print(f"  过滤（流动性）: {filtered_by_liquidity} 个")
    print(f"  过滤（年龄）: {filtered_by_age} 个")
    print(f"  通过筛选: {len(filtered_tokens)} 个")

    # 按涨幅排序
    sorted_tokens = sorted(
        filtered_tokens,
        key=lambda x: x.get('price_change_24h', 0),
        reverse=True
    )

    # 显示 Top 10
    top_10 = sorted_tokens[:10]
    print(f"\nTop 10 涨幅榜（筛选后）:")
    print(f"  {'排名':<6} {'符号':<12} {'涨幅%':<10} {'市值':<15} {'流动性':<15} {'年龄'}")
    print(f"  {'-'*80}")
    for i, token in enumerate(top_10, 1):
        symbol = token.get('token_symbol', 'N/A')
        change = token.get('price_change_24h', 0)
        mcap = token.get('market_cap', 0)
        liq = token.get('liquidity_usd', 0)
        age = token.get('age', 'N/A')
        print(f"  {i:<6} {symbol:<12} +{change:>7.1f}%  ${mcap:>12,.0f}  ${liq:>12,.0f}  {age}")

    print(f"\n{'='*80}")
    print(f"测试完成")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(test_scraper())
