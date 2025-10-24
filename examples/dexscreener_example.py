#!/usr/bin/env python3
"""
DexScreener服务基础使用示例
演示如何使用封装好的服务类进行数据爬取和管理
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.dexscreener_service import DexScreenerService, quick_scrape_and_import


# ==================== 示例 1: 最简单的方式 ====================

async def example1_quickstart():
    """示例1: 使用快捷函数一键完成所有操作"""
    print("\n" + "=" * 80)
    print("示例 1: 快捷函数 - 一键爬取并导入")
    print("=" * 80)

    result = await quick_scrape_and_import(
        target_count=50,       # 爬取50个代币（演示用，减少时间）
        headless=True,         # 使用无头浏览器
        deduplicate=True       # 自动去重
    )

    if result['success']:
        print(f"\n✓ 成功完成！")
        print(f"  - 爬取到: {result['steps']['scrape']['tokens_found']} 个代币")
        print(f"  - 插入: {result['steps']['import']['inserted']} 条")
        print(f"  - 更新: {result['steps']['import']['updated']} 条")
        print(f"  - 去重删除: {result['steps']['deduplicate'].get('pairs_to_delete', 0)} 条")
        print(f"  - 最终记录数: {result['final_count']}")
    else:
        print(f"\n✗ 失败: {result.get('error')}")


# ==================== 示例 2: 分步操作 ====================

async def example2_step_by_step():
    """示例2: 分步执行 - 更灵活的控制"""
    print("\n" + "=" * 80)
    print("示例 2: 分步操作 - 爬取、导入、去重")
    print("=" * 80)

    service = DexScreenerService()

    try:
        # 步骤1: 爬取数据
        print("\n[1/3] 爬取页面数据...")
        tokens = service.scrape_and_fetch(
            target_count=50,
            output_file="/tmp/example_tokens.json",
            headless=True
        )
        print(f"✓ 爬取到 {len(tokens)} 个代币的完整数据")

        # 步骤2: 导入数据库
        print("\n[2/3] 导入到数据库...")
        stats = await service.import_tokens(tokens, update_existing=True)
        print(f"✓ 插入: {stats['inserted']}, 更新: {stats['updated']}, 错误: {stats['errors']}")

        # 步骤3: 去重
        print("\n[3/3] 执行去重...")
        # 先预览
        preview = await service.deduplicate_tokens(dry_run=True)
        print(f"  发现 {preview['duplicate_tokens_count']} 个有重复的代币")
        print(f"  将删除 {preview['pairs_to_delete']} 条重复记录")

        # 执行删除
        if preview['pairs_to_delete'] > 0:
            result = await service.deduplicate_tokens(dry_run=False)
            print(f"✓ 已删除 {result['pairs_to_delete']} 条重复记录")

        # 查看最终结果
        final_count = await service.get_token_count()
        print(f"\n✓ 完成！数据库中有 {final_count} 个代币")

    finally:
        await service.close()


# ==================== 示例 3: 只爬取数据 ====================

def example3_scrape_only():
    """示例3: 只爬取数据，不导入数据库"""
    print("\n" + "=" * 80)
    print("示例 3: 只爬取数据（不导入数据库）")
    print("=" * 80)

    service = DexScreenerService()

    # 只获取交易对地址
    print("\n获取交易对地址...")
    pairs = service.scrape_bsc_page(
        target_count=20,
        headless=True,
        max_scrolls=10
    )

    print(f"\n获取到 {len(pairs)} 个交易对地址:")
    for i, pair in enumerate(pairs[:5], 1):
        print(f"  {i}. {pair['pair_address']}")
    print(f"  ... 还有 {len(pairs) - 5} 个")

    # 获取详细信息
    print("\n获取详细信息...")
    pair_addresses = [p['pair_address'] for p in pairs[:10]]  # 只取前10个
    details = service.fetch_pair_details(pair_addresses)

    print(f"\n获取到 {len(details)} 个代币的详细信息:")
    for token in details[:5]:
        symbol = token.get('baseToken', {}).get('symbol', 'N/A')
        price = token.get('priceUsd', 'N/A')
        liquidity = token.get('liquidity', {}).get('usd', 'N/A')
        print(f"  - {symbol:>10}: ${price:>12} (流动性: ${liquidity:>12})")


# ==================== 示例 4: 只导入数据 ====================

async def example4_import_only():
    """示例4: 从现有JSON文件导入数据"""
    print("\n" + "=" * 80)
    print("示例 4: 从JSON文件导入数据")
    print("=" * 80)

    # 检查文件是否存在
    json_file = "/tmp/example_tokens.json"
    if not Path(json_file).exists():
        print(f"\n✗ 文件不存在: {json_file}")
        print("  请先运行示例2生成JSON文件")
        return

    service = DexScreenerService()

    try:
        print(f"\n从文件导入: {json_file}")
        stats = await service.import_from_json(
            json_file,
            update_existing=True
        )

        print(f"\n✓ 导入完成!")
        print(f"  - 插入: {stats['inserted']} 条新记录")
        print(f"  - 更新: {stats['updated']} 条现有记录")
        print(f"  - 错误: {stats['errors']} 条")

        # 查看总数
        total = await service.get_token_count()
        print(f"  - 数据库总计: {total} 个代币")

    finally:
        await service.close()


# ==================== 示例 5: 只去重 ====================

async def example5_deduplicate_only():
    """示例5: 只执行去重操作"""
    print("\n" + "=" * 80)
    print("示例 5: 去重现有数据")
    print("=" * 80)

    service = DexScreenerService()

    try:
        # 查看当前状态
        count_before = await service.get_token_count()
        print(f"\n当前数据库有 {count_before} 条记录")

        # 分析重复情况
        print("\n分析重复代币...")
        result = await service.deduplicate_tokens(dry_run=True)

        print(f"  - 有重复的代币: {result['duplicate_tokens_count']} 个")
        print(f"  - 将删除的交易对: {result['pairs_to_delete']} 个")

        # 显示详细信息
        if result['duplicate_info']:
            print("\n重复代币详情:")
            for info in result['duplicate_info'][:3]:  # 只显示前3个
                print(f"\n  代币: {info['token_symbol']} ({info['token_name']})")
                print(f"    共有 {info['total_pairs']} 个交易对")
                print(f"    保留: {info['keep']['pair_address'][:20]}... "
                      f"(流动性: ${info['keep']['liquidity_usd']:,.2f})")
                print(f"    删除:")
                for del_pair in info['delete']:
                    print(f"      - {del_pair['pair_address'][:20]}... "
                          f"(流动性: ${del_pair['liquidity_usd']:,.2f})")

        # 执行去重
        if result['pairs_to_delete'] > 0:
            confirm = input("\n是否执行去重? (yes/no): ")
            if confirm.lower() == 'yes':
                final_result = await service.deduplicate_tokens(dry_run=False)
                print(f"\n✓ 去重完成!")
                print(f"  - 删除: {final_result['pairs_to_delete']} 条重复记录")
                print(f"  - 剩余: {final_result['remaining_records']} 条记录")
            else:
                print("\n取消操作")
        else:
            print("\n✓ 没有重复数据，无需去重")

    finally:
        await service.close()


# ==================== 示例 6: 数据过滤 ====================

async def example6_filter_data():
    """示例6: 爬取时过滤数据"""
    print("\n" + "=" * 80)
    print("示例 6: 爬取并过滤高质量代币")
    print("=" * 80)

    service = DexScreenerService()

    try:
        # 爬取数据
        print("\n爬取数据...")
        tokens = service.scrape_and_fetch(
            target_count=50,
            headless=True
        )
        print(f"✓ 爬取到 {len(tokens)} 个代币")

        # 过滤条件
        print("\n应用过滤条件:")
        print("  - 流动性 > $10,000")
        print("  - 24小时交易量 > $5,000")
        print("  - 有价格数据")

        filtered_tokens = []
        for token in tokens:
            liquidity = token.get('liquidity', {}).get('usd', 0) or 0
            volume_24h = token.get('volume', {}).get('h24', 0) or 0
            price_usd = token.get('priceUsd')

            if liquidity > 10000 and volume_24h > 5000 and price_usd:
                filtered_tokens.append(token)

        print(f"\n✓ 过滤后剩余 {len(filtered_tokens)} 个高质量代币")

        # 导入过滤后的数据
        if filtered_tokens:
            print("\n导入过滤后的数据...")
            stats = await service.import_tokens(filtered_tokens)
            print(f"✓ 插入: {stats['inserted']}, 更新: {stats['updated']}")

            # 显示前几个
            print("\n高质量代币示例:")
            for token in filtered_tokens[:5]:
                symbol = token.get('baseToken', {}).get('symbol', 'N/A')
                price = float(token.get('priceUsd', 0))
                liquidity = token.get('liquidity', {}).get('usd', 0)
                volume = token.get('volume', {}).get('h24', 0)
                print(f"  {symbol:>10}: ${price:>12.6f} | "
                      f"流动性: ${liquidity:>12,.2f} | "
                      f"交易量: ${volume:>12,.2f}")

    finally:
        await service.close()


# ==================== 示例 7: 增量更新 ====================

async def example7_incremental_update():
    """示例7: 增量更新现有数据"""
    print("\n" + "=" * 80)
    print("示例 7: 增量更新（刷新价格和交易量）")
    print("=" * 80)

    service = DexScreenerService()

    try:
        # 获取当前数据库中的代币数量
        count_before = await service.get_token_count()
        print(f"\n当前数据库有 {count_before} 个代币")

        # 爬取最新数据
        print("\n爬取最新数据...")
        result = await service.scrape_and_import(
            target_count=50,
            headless=True,
            deduplicate=True,
            save_json=False
        )

        if result['success']:
            print(f"\n✓ 更新完成!")
            print(f"  - 新增代币: {result['steps']['import']['inserted']}")
            print(f"  - 更新代币: {result['steps']['import']['updated']}")
            print(f"  - 总计: {result['final_count']} 个代币")

    finally:
        await service.close()


# ==================== 主函数 ====================

async def main():
    """运行所有示例"""
    print("\n" + "=" * 80)
    print("DexScreener 服务使用示例")
    print("=" * 80)

    examples = {
        "1": ("快捷函数 - 一键爬取并导入", example1_quickstart),
        "2": ("分步操作 - 爬取、导入、去重", example2_step_by_step),
        "3": ("只爬取数据（不导入数据库）", example3_scrape_only),
        "4": ("从JSON文件导入数据", example4_import_only),
        "5": ("去重现有数据", example5_deduplicate_only),
        "6": ("爬取并过滤高质量代币", example6_filter_data),
        "7": ("增量更新现有数据", example7_incremental_update),
    }

    print("\n可用示例:")
    for key, (desc, _) in examples.items():
        print(f"  {key}. {desc}")
    print("  0. 运行所有示例")
    print("  q. 退出")

    choice = input("\n请选择示例 (1-7, 0, q): ").strip()

    if choice == 'q':
        print("\n再见!")
        return

    if choice == '0':
        # 运行所有示例
        for key, (desc, func) in examples.items():
            try:
                if asyncio.iscoroutinefunction(func):
                    await func()
                else:
                    func()
                print("\n" + "-" * 80)
            except Exception as e:
                print(f"\n✗ 示例 {key} 失败: {e}")
                import traceback
                traceback.print_exc()
    elif choice in examples:
        # 运行单个示例
        desc, func = examples[choice]
        try:
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()
        except Exception as e:
            print(f"\n✗ 示例失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"\n✗ 无效选择: {choice}")

    print("\n" + "=" * 80)
    print("示例运行完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
