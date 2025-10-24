#!/usr/bin/env python3
"""
测试年龄过滤功能
演示如何过滤掉一个月之前创建的代币
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.dexscreener_service import DexScreenerService, quick_scrape_and_import


async def test_age_filter():
    """测试年龄过滤功能"""
    print("\n" + "=" * 80)
    print("测试：过滤掉一个月之前创建的代币")
    print("=" * 80)

    service = DexScreenerService()

    try:
        # 1. 爬取数据（不过滤）
        print("\n[测试 1] 爬取数据（不过滤）...")
        all_tokens = service.scrape_and_fetch(
            target_count=50,
            headless=True,
            filter_old_tokens=False  # 不过滤
        )
        print(f"✓ 获取到 {len(all_tokens)} 个代币（未过滤）")

        # 2. 手动应用年龄过滤
        print("\n[测试 2] 应用年龄过滤（30天）...")
        filtered_30days = DexScreenerService.filter_tokens_by_age(all_tokens, max_age_days=30)
        print(f"✓ 30天过滤后: {len(filtered_30days)} 个代币")

        # 3. 测试不同的天数
        print("\n[测试 3] 测试不同的过滤天数...")
        for days in [7, 14, 30, 60, 90]:
            filtered = DexScreenerService.filter_tokens_by_age(all_tokens, max_age_days=days)
            percentage = len(filtered) / len(all_tokens) * 100 if all_tokens else 0
            print(f"  {days:>3} 天内: {len(filtered):>3} 个代币 ({percentage:>5.1f}%)")

        # 4. 显示被过滤的代币详情
        print("\n[测试 4] 查看被过滤的代币（30天）...")
        cutoff_time = datetime.now() - timedelta(days=30)
        filtered_out = []

        for token in all_tokens:
            pair_created_at = token.get('pairCreatedAt')
            if pair_created_at:
                created_time = datetime.fromtimestamp(pair_created_at / 1000)
                age_days = (datetime.now() - created_time).days

                if age_days > 30:
                    symbol = token.get('baseToken', {}).get('symbol', 'N/A')
                    filtered_out.append({
                        'symbol': symbol,
                        'created': created_time.strftime('%Y-%m-%d'),
                        'age_days': age_days
                    })

        if filtered_out:
            print(f"\n被过滤掉的代币（共 {len(filtered_out)} 个）:")
            print(f"{'代币':>10} | {'创建日期':>12} | {'年龄（天）':>10}")
            print("-" * 40)
            for item in filtered_out[:10]:  # 只显示前10个
                print(f"{item['symbol']:>10} | {item['created']:>12} | {item['age_days']:>10}")
            if len(filtered_out) > 10:
                print(f"... 还有 {len(filtered_out) - 10} 个")
        else:
            print("没有被过滤的代币（所有代币都在30天内创建）")

        # 5. 显示保留的代币详情
        print("\n[测试 5] 查看保留的代币（30天内）...")
        kept_tokens = []

        for token in all_tokens:
            pair_created_at = token.get('pairCreatedAt')
            if pair_created_at:
                created_time = datetime.fromtimestamp(pair_created_at / 1000)
                age_days = (datetime.now() - created_time).days

                if age_days <= 30:
                    symbol = token.get('baseToken', {}).get('symbol', 'N/A')
                    liquidity = token.get('liquidity', {}).get('usd', 0) or 0
                    kept_tokens.append({
                        'symbol': symbol,
                        'created': created_time.strftime('%Y-%m-%d'),
                        'age_days': age_days,
                        'liquidity': liquidity
                    })

        if kept_tokens:
            # 按流动性排序
            kept_tokens.sort(key=lambda x: x['liquidity'], reverse=True)

            print(f"\n保留的代币（共 {len(kept_tokens)} 个，按流动性排序）:")
            print(f"{'代币':>10} | {'创建日期':>12} | {'年龄（天）':>10} | {'流动性':>15}")
            print("-" * 55)
            for item in kept_tokens[:10]:  # 只显示前10个
                print(f"{item['symbol']:>10} | {item['created']:>12} | "
                      f"{item['age_days']:>10} | ${item['liquidity']:>14,.2f}")
            if len(kept_tokens) > 10:
                print(f"... 还有 {len(kept_tokens) - 10} 个")
        else:
            print("没有保留的代币")

    finally:
        await service.close()


async def test_one_click_with_filter():
    """测试一键爬取（带年龄过滤）"""
    print("\n" + "=" * 80)
    print("测试：一键爬取并导入（自动过滤旧代币）")
    print("=" * 80)

    # 使用快捷函数，自动过滤30天前的代币
    result = await quick_scrape_and_import(
        target_count=50,
        headless=True,
        deduplicate=True,
        filter_old_tokens=True,  # 启用过滤
        max_age_days=30          # 只保留30天内的代币
    )

    if result['success']:
        print(f"\n✓ 一键操作成功！")
        print(f"  爬取: {result['steps']['scrape']['tokens_found']} 个代币")
        print(f"  导入: {result['steps']['import']['inserted']} 插入, "
              f"{result['steps']['import']['updated']} 更新")
        print(f"  最终: {result['final_count']} 条记录")
    else:
        print(f"\n✗ 操作失败: {result.get('error')}")


async def test_manual_filter():
    """测试手动过滤现有JSON数据"""
    print("\n" + "=" * 80)
    print("测试：过滤现有JSON文件中的旧代币")
    print("=" * 80)

    # 检查是否有现成的JSON文件
    json_file = "/Users/mac/Documents/code/blockchain-data/dexscreener_tokens.json"

    if not Path(json_file).exists():
        print(f"\n✗ 文件不存在: {json_file}")
        print("请先运行爬取操作生成数据")
        return

    print(f"\n读取文件: {json_file}")
    with open(json_file, 'r', encoding='utf-8') as f:
        tokens = json.load(f)

    print(f"原始数据: {len(tokens)} 个代币")

    # 应用年龄过滤
    filtered_tokens = DexScreenerService.filter_tokens_by_age(tokens, max_age_days=30)
    print(f"过滤后: {len(filtered_tokens)} 个代币")
    print(f"过滤掉: {len(tokens) - len(filtered_tokens)} 个代币")

    # 保存过滤后的数据
    output_file = "/tmp/dexscreener_tokens_filtered_30days.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_tokens, f, indent=2, ensure_ascii=False)

    print(f"\n✓ 过滤后的数据已保存到: {output_file}")

    # 导入到数据库
    choice = input("\n是否将过滤后的数据导入到数据库？(yes/no): ")
    if choice.lower() == 'yes':
        service = DexScreenerService()
        try:
            stats = await service.import_tokens(filtered_tokens)
            print(f"\n✓ 导入完成！")
            print(f"  插入: {stats['inserted']}")
            print(f"  更新: {stats['updated']}")
        finally:
            await service.close()


async def test_custom_days():
    """测试自定义天数过滤"""
    print("\n" + "=" * 80)
    print("测试：自定义天数过滤")
    print("=" * 80)

    days = input("\n请输入要保留的最大天数（例如：7, 14, 30, 60）: ").strip()

    try:
        max_age_days = int(days)
    except ValueError:
        print("✗ 无效输入，使用默认值30天")
        max_age_days = 30

    print(f"\n使用过滤条件: 只保留 {max_age_days} 天内创建的代币")

    service = DexScreenerService()

    try:
        # 爬取并应用自定义过滤
        print("\n爬取数据...")
        tokens = service.scrape_and_fetch(
            target_count=50,
            headless=True,
            filter_old_tokens=True,
            max_age_days=max_age_days
        )

        print(f"\n✓ 获取到 {len(tokens)} 个代币（{max_age_days}天内创建）")

        # 显示代币年龄分布
        if tokens:
            print(f"\n代币年龄分布:")
            age_distribution = {}

            for token in tokens:
                pair_created_at = token.get('pairCreatedAt')
                if pair_created_at:
                    created_time = datetime.fromtimestamp(pair_created_at / 1000)
                    age_days = (datetime.now() - created_time).days

                    if age_days <= 1:
                        key = "1天内"
                    elif age_days <= 7:
                        key = "1-7天"
                    elif age_days <= 14:
                        key = "7-14天"
                    elif age_days <= 30:
                        key = "14-30天"
                    else:
                        key = f"30天以上"

                    age_distribution[key] = age_distribution.get(key, 0) + 1

            for age_range, count in sorted(age_distribution.items()):
                percentage = count / len(tokens) * 100
                print(f"  {age_range:>10}: {count:>3} 个 ({percentage:>5.1f}%)")

    finally:
        await service.close()


async def main():
    """主函数"""
    tests = {
        "1": ("测试年龄过滤功能", test_age_filter),
        "2": ("一键爬取并导入（带过滤）", test_one_click_with_filter),
        "3": ("过滤现有JSON文件", test_manual_filter),
        "4": ("自定义天数过滤", test_custom_days),
    }

    print("\n" + "=" * 80)
    print("年龄过滤功能测试")
    print("=" * 80)

    print("\n可用测试:")
    for key, (desc, _) in tests.items():
        print(f"  {key}. {desc}")
    print("  0. 运行所有测试")
    print("  q. 退出")

    choice = input("\n请选择测试 (1-4, 0, q): ").strip()

    if choice == 'q':
        print("\n再见!")
        return

    if choice == '0':
        # 运行所有测试
        for key, (desc, func) in tests.items():
            try:
                await func()
                print("\n" + "-" * 80)
            except Exception as e:
                print(f"\n✗ 测试 {key} 失败: {e}")
                import traceback
                traceback.print_exc()
    elif choice in tests:
        # 运行单个测试
        desc, func = tests[choice]
        try:
            await func()
        except Exception as e:
            print(f"\n✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"\n✗ 无效选择: {choice}")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
