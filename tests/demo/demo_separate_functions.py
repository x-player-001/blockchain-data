#!/usr/bin/env python3
"""
演示：爬取筛选和监控功能分开使用

功能1：scrape_and_filter_top_gainers() - 只爬取和筛选，不添加监控
功能2：add_tokens_to_monitor() - 只添加监控，不爬取
功能3：scrape_and_add_top_gainers() - 一键操作（爬取+筛选+监控）
"""

import asyncio
import json
from src.services.token_monitor_service import TokenMonitorService


async def demo_separate_usage():
    """演示分开使用两个功能"""

    print("\n" + "="*80)
    print("演示：爬取筛选和监控功能分开使用")
    print("="*80 + "\n")

    service = TokenMonitorService()

    try:
        # ==================== 方式1：只爬取筛选，不添加监控 ====================
        print("【方式1】只爬取和筛选Top 5涨幅代币（不添加监控）")
        print("-"*80)

        top_gainers = service.scrape_and_filter_top_gainers(
            count=30,        # 爬取30个（测试用）
            top_n=5,         # 筛选前5名
            headless=False   # 使用有头模式绕过Cloudflare
        )

        print(f"\n✓ 已筛选出 {len(top_gainers)} 个Top涨幅代币")
        print("注意：此时还没有添加到监控表！\n")

        # 可以保存到文件
        output_file = "/tmp/top_gainers.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(top_gainers, f, indent=2, ensure_ascii=False)
        print(f"✓ 已保存到: {output_file}\n")

        # 暂停，让用户查看结果
        input("按回车键继续，将把这些代币添加到监控表...")

        # ==================== 方式2：只添加监控，不爬取 ====================
        print("\n" + "="*80)
        print("【方式2】将上面筛选的代币添加到监控表")
        print("-"*80 + "\n")

        result = await service.add_tokens_to_monitor(
            tokens=top_gainers,
            drop_threshold=15.0  # 15%跌幅报警
        )

        print(f"\n✓ 添加完成:")
        print(f"  总数: {result['total']}")
        print(f"  成功: {result['added']}")
        print(f"  跳过: {result['skipped']}\n")

        # ==================== 查看监控列表 ====================
        print("="*80)
        print("【查看监控列表】")
        print("="*80 + "\n")

        monitored = await service.get_active_monitored_tokens(limit=10)

        if monitored:
            for i, token in enumerate(monitored, 1):
                print(f"{i}. {token['token_symbol']:12s} "
                      f"入场价=${token['entry_price_usd']:.8f}  "
                      f"阈值={token['drop_threshold_percent']:.1f}%")
        else:
            print("监控列表为空")

        print("\n" + "="*80)
        print("✓ 演示完成！")
        print("="*80)

        print("\n说明:")
        print("  1. scrape_and_filter_top_gainers() - 只负责爬取和筛选")
        print("  2. add_tokens_to_monitor() - 只负责添加监控")
        print("  3. 两个功能完全独立，可以分开启动")
        print("\n使用场景:")
        print("  - 先爬取筛选，手动审核后再决定是否监控")
        print("  - 从文件加载代币列表，直接添加监控")
        print("  - 定时爬取筛选，单独运行监控服务")
        print()

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.close()


async def demo_load_from_file():
    """演示：从文件加载代币并添加监控"""

    print("\n" + "="*80)
    print("演示：从JSON文件加载代币并添加监控")
    print("="*80 + "\n")

    service = TokenMonitorService()

    try:
        # 从文件加载
        input_file = "/tmp/top_gainers.json"
        print(f"从文件加载代币: {input_file}\n")

        with open(input_file, 'r', encoding='utf-8') as f:
            tokens = json.load(f)

        print(f"✓ 已加载 {len(tokens)} 个代币")

        # 直接添加到监控
        result = await service.add_tokens_to_monitor(
            tokens=tokens,
            drop_threshold=20.0
        )

        print(f"\n添加结果:")
        print(f"  成功: {result['added']}")
        print(f"  跳过: {result['skipped']}")

    except FileNotFoundError:
        print(f"⚠ 文件不存在: {input_file}")
        print("请先运行 demo_separate_usage() 生成文件")
    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        await service.close()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'load':
        # 从文件加载
        asyncio.run(demo_load_from_file())
    else:
        # 分开使用演示
        asyncio.run(demo_separate_usage())
