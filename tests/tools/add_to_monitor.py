#!/usr/bin/env python3
"""
爬取Top涨幅代币并添加到监控表
"""

import asyncio
from src.services.token_monitor_service import TokenMonitorService


async def scrape_and_monitor():
    """爬取并添加到监控"""

    print("\n" + "="*80)
    print("爬取Top涨幅代币并添加到监控表")
    print("="*80 + "\n")

    service = TokenMonitorService()

    try:
        # 步骤1: 爬取和筛选（不添加监控）
        print("步骤1: 爬取并筛选Top 10涨幅代币...")
        print("-"*80 + "\n")

        top_gainers = service.scrape_and_filter_top_gainers(
            count=100,        # 爬取100个
            top_n=10,         # 筛选前10名
            headless=False    # 有头模式（更稳定）
        )

        if not top_gainers:
            print("❌ 未获取到代币数据")
            return

        # 步骤2: 添加到监控表
        print("\n步骤2: 添加到监控表...")
        print("-"*80 + "\n")

        result = await service.add_tokens_to_monitor(
            tokens=top_gainers,
            drop_threshold=20.0  # 20%跌幅报警
        )

        print("\n" + "="*80)
        print("✅ 完成！")
        print("="*80)
        print(f"  筛选: {len(top_gainers)} 个Top涨幅代币")
        print(f"  成功添加监控: {result['added']} 个")
        print(f"  跳过（已存在）: {result['skipped']} 个")
        print("="*80 + "\n")

        # 步骤3: 查看监控列表
        print("当前监控列表:")
        print("-"*80)

        monitored = await service.get_active_monitored_tokens(limit=15)

        if monitored:
            for i, token in enumerate(monitored, 1):
                symbol = token['token_symbol']
                entry_price = token['entry_price_usd']
                peak_price = token['peak_price_usd']
                threshold = token['drop_threshold_percent']
                entry_gain = token.get('price_change_24h_at_entry', 0)

                print(f"{i:2d}. {symbol:12s} "
                      f"入场价=${entry_price:.8f}  "
                      f"峰值=${peak_price:.8f}  "
                      f"入场涨幅=+{entry_gain:.2f}%  "
                      f"阈值={threshold:.0f}%")
        else:
            print("监控列表为空")

        print("\n下一步可以运行:")
        print("  python -m src.scripts.monitor_tokens update  # 更新价格并检查报警")
        print("  python -m src.scripts.monitor_tokens list-tokens  # 查看监控列表")
        print("  python -m src.scripts.monitor_tokens list-alerts  # 查看报警")
        print()

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.close()


if __name__ == '__main__':
    asyncio.run(scrape_and_monitor())
