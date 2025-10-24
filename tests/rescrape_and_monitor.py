#!/usr/bin/env python3
"""
重新抓取并添加监控
一站式脚本：爬取 -> 筛选 -> 添加监控 -> 更新AVE数据
"""

import asyncio
from src.services.token_monitor_service import TokenMonitorService


async def rescrape_and_monitor():
    """重新抓取Top涨幅代币并添加到监控"""

    print("\n" + "="*80)
    print("重新抓取并添加监控")
    print("="*80 + "\n")

    monitor_service = TokenMonitorService()

    try:
        # 使用一键操作：爬取 + 筛选 + 添加监控
        result = await monitor_service.scrape_and_add_top_gainers(
            count=100,          # 爬取100个代币
            top_n=10,           # 取前10名涨幅榜
            drop_threshold=20.0,  # 跌幅20%触发报警
            headless=False      # 显示浏览器（绕过Cloudflare）
        )

        print("\n" + "="*80)
        print("抓取结果")
        print("="*80)
        print(f"  爬取代币数: {result['scraped']}")
        print(f"  筛选Top N: {result['top_n']}")
        print(f"  添加成功: {result['added']}")
        print(f"  跳过重复: {result['skipped']}")
        print("="*80 + "\n")

        if result['added'] > 0:
            print("✓ 代币已成功添加到监控表")
            print("\n正在使用AVE API更新详细数据...")

            # 更新价格和AVE API数据
            update_result = await monitor_service.update_monitored_prices(delay=0.3)

            print("\n" + "="*80)
            print("AVE API更新结果")
            print("="*80)
            print(f"  总监控数: {update_result['total_monitored']}")
            print(f"  成功更新: {update_result['updated']}")
            print(f"  触发报警: {update_result['alerts_triggered']}")
            print("="*80 + "\n")

            print("✓ 所有操作完成！")
        else:
            print("⚠ 未添加任何新代币")

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await monitor_service.close()


if __name__ == '__main__':
    asyncio.run(rescrape_and_monitor())
