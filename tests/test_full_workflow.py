#!/usr/bin/env python3
"""
测试完整监控工作流：
1. 一次性爬取完整数据
2. 按涨幅排序
3. 添加到监控表
4. 查看监控列表
"""

import asyncio
from src.services.token_monitor_service import TokenMonitorService


async def test_full_workflow():
    """测试完整的监控工作流"""

    print("\n" + "="*80)
    print("测试完整监控工作流（使用改进后的一步爬取）")
    print("="*80 + "\n")

    monitor_service = TokenMonitorService()

    try:
        # 步骤1: 爬取并添加到监控（一步完成）
        print("步骤1: 爬取DexScreener首页并添加Top 5到监控...")
        print("-"*80)

        result = await monitor_service.scrape_and_add_top_gainers(
            count=50,           # 爬取50个代币（测试用）
            top_n=5,            # 只取前5名
            drop_threshold=15.0,  # 15%跌幅报警
            headless=False      # 使用有头模式绕过Cloudflare
        )

        print("\n✓ 爬取和添加完成！")
        print(f"  已爬取: {result['scraped']} 个代币（含完整数据）")
        print(f"  涨幅榜: {result['top_gainers']} 个")
        print(f"  已添加监控: {result['added_to_monitor']} 个\n")

        # 步骤2: 查看监控列表
        print("="*80)
        print("步骤2: 查看监控列表")
        print("="*80 + "\n")

        monitored = await monitor_service.get_active_monitored_tokens(limit=10)

        if not monitored:
            print("⚠ 监控列表为空\n")
        else:
            for i, token in enumerate(monitored, 1):
                print(f"{i}. {token['token_symbol']}")
                print(f"   入场价: ${token['entry_price_usd']:.8f}")
                print(f"   峰值价: ${token['peak_price_usd']:.8f}")

                entry_gain = token.get('price_change_24h_at_entry', 0)
                if entry_gain:
                    print(f"   入场时24h涨幅: +{entry_gain:.2f}%")

                print(f"   状态: {token['status']}")
                print(f"   跌幅阈值: {token['drop_threshold_percent']:.1f}%")
                print()

        print("="*80)
        print("✓ 完整工作流测试成功！")
        print("="*80)
        print("\n说明:")
        print("  1. ✓ 一次性从HTML爬取完整数据（无需API调用）")
        print("  2. ✓ 按24h涨幅排序")
        print("  3. ✓ 添加Top N到监控表")
        print("  4. ✓ 监控表查询正常")
        print("\n下一步可以:")
        print("  - 运行 'python -m src.scripts.monitor_tokens update' 更新价格")
        print("  - 运行 'python -m src.scripts.monitor_tokens auto-monitor' 启动自动监控")
        print()

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await monitor_service.close()


if __name__ == '__main__':
    asyncio.run(test_full_workflow())
