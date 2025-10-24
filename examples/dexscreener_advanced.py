#!/usr/bin/env python3
"""
DexScreener服务高级用法示例
演示定时任务、错误处理、数据分析等高级场景
"""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.dexscreener_service import DexScreenerService
from src.storage.db_manager import DatabaseManager
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 高级示例 1: 错误重试机制 ====================

async def example1_retry_mechanism():
    """示例1: 实现错误重试机制"""
    print("\n" + "=" * 80)
    print("高级示例 1: 错误重试机制")
    print("=" * 80)

    max_retries = 3
    retry_delay = 5  # 秒

    for attempt in range(max_retries):
        service = DexScreenerService()

        try:
            logger.info(f"尝试 {attempt + 1}/{max_retries}...")

            result = await service.scrape_and_import(
                target_count=50,
                headless=True,
                deduplicate=True
            )

            if result['success']:
                logger.info(f"✓ 成功！最终有 {result['final_count']} 个代币")
                return result
            else:
                raise Exception(result.get('error', 'Unknown error'))

        except Exception as e:
            logger.error(f"✗ 尝试 {attempt + 1} 失败: {e}")

            if attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                logger.info(f"等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)
            else:
                logger.error("达到最大重试次数，放弃")
                raise

        finally:
            await service.close()


# ==================== 高级示例 2: 定时更新任务 ====================

async def example2_scheduled_update():
    """示例2: 定时更新数据（模拟）"""
    print("\n" + "=" * 80)
    print("高级示例 2: 定时更新任务")
    print("=" * 80)

    update_interval = 60  # 60秒更新一次（演示用）
    max_iterations = 3    # 最多运行3次（演示用）

    async def update_task():
        """更新任务"""
        service = DexScreenerService()

        try:
            logger.info(f"[{datetime.now()}] 开始更新...")

            result = await service.scrape_and_import(
                target_count=30,  # 减少数量以加快速度
                headless=True,
                deduplicate=True,
                save_json=True,
                json_path=f"/tmp/tokens_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

            if result['success']:
                logger.info(f"✓ 更新成功！当前有 {result['final_count']} 个代币")
                logger.info(f"  新增: {result['steps']['import']['inserted']}")
                logger.info(f"  更新: {result['steps']['import']['updated']}")
                return True
            else:
                logger.error(f"✗ 更新失败: {result.get('error')}")
                return False

        except Exception as e:
            logger.exception("更新过程中出错")
            return False

        finally:
            await service.close()

    # 模拟定时任务
    for i in range(max_iterations):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"第 {i + 1}/{max_iterations} 次更新")
        logger.info(f"{'=' * 60}")

        success = await update_task()

        if i < max_iterations - 1:
            logger.info(f"\n等待 {update_interval} 秒后进行下一次更新...")
            await asyncio.sleep(update_interval)

    logger.info("\n定时任务演示完成")


# ==================== 高级示例 3: 数据质量分析 ====================

async def example3_data_quality_analysis():
    """示例3: 分析数据库中的数据质量"""
    print("\n" + "=" * 80)
    print("高级示例 3: 数据质量分析")
    print("=" * 80)

    db_manager = DatabaseManager()
    await db_manager.init_async_db()

    try:
        async with db_manager.get_session() as session:
            # 1. 总体统计
            print("\n【总体统计】")
            result = await session.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(DISTINCT base_token_address) as unique_tokens,
                    COUNT(DISTINCT dex_id) as dex_count
                FROM dexscreener_tokens
            """))
            stats = result.fetchone()
            print(f"  总记录数: {stats[0]}")
            print(f"  唯一代币数: {stats[1]}")
            print(f"  DEX数量: {stats[2]}")

            # 2. 数据完整性
            print("\n【数据完整性】")
            result = await session.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE price_usd IS NOT NULL) as has_price,
                    COUNT(*) FILTER (WHERE liquidity_usd IS NOT NULL) as has_liquidity,
                    COUNT(*) FILTER (WHERE volume_h24 IS NOT NULL) as has_volume,
                    COUNT(*) FILTER (WHERE market_cap IS NOT NULL) as has_market_cap,
                    COUNT(*) FILTER (WHERE website_url IS NOT NULL) as has_website,
                    COUNT(*) as total
                FROM dexscreener_tokens
            """))
            completeness = result.fetchone()
            total = completeness[5]
            print(f"  有价格数据: {completeness[0]}/{total} ({completeness[0]/total*100:.1f}%)")
            print(f"  有流动性数据: {completeness[1]}/{total} ({completeness[1]/total*100:.1f}%)")
            print(f"  有交易量数据: {completeness[2]}/{total} ({completeness[2]/total*100:.1f}%)")
            print(f"  有市值数据: {completeness[3]}/{total} ({completeness[3]/total*100:.1f}%)")
            print(f"  有网站链接: {completeness[4]}/{total} ({completeness[4]/total*100:.1f}%)")

            # 3. 流动性分布
            print("\n【流动性分布】")
            result = await session.execute(text("""
                SELECT
                    CASE
                        WHEN liquidity_usd < 10000 THEN '< $10k'
                        WHEN liquidity_usd < 100000 THEN '$10k - $100k'
                        WHEN liquidity_usd < 1000000 THEN '$100k - $1M'
                        WHEN liquidity_usd < 10000000 THEN '$1M - $10M'
                        ELSE '> $10M'
                    END as range,
                    COUNT(*) as count
                FROM dexscreener_tokens
                WHERE liquidity_usd IS NOT NULL
                GROUP BY range
                ORDER BY MIN(liquidity_usd)
            """))
            print("  流动性范围 | 代币数量")
            print("  " + "-" * 30)
            for row in result:
                print(f"  {row[0]:>15} | {row[1]}")

            # 4. Top DEX
            print("\n【Top DEX】")
            result = await session.execute(text("""
                SELECT
                    dex_id,
                    COUNT(*) as pair_count,
                    SUM(liquidity_usd) as total_liquidity
                FROM dexscreener_tokens
                GROUP BY dex_id
                ORDER BY pair_count DESC
                LIMIT 5
            """))
            print("  DEX | 交易对数 | 总流动性")
            print("  " + "-" * 50)
            for row in result:
                liq = float(row[2]) if row[2] else 0
                print(f"  {row[0]:>15} | {row[1]:>8} | ${liq:>15,.2f}")

            # 5. 活跃度分析
            print("\n【交易活跃度】")
            result = await session.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE txns_h24_buys + txns_h24_sells > 1000) as very_active,
                    COUNT(*) FILTER (WHERE txns_h24_buys + txns_h24_sells BETWEEN 100 AND 1000) as active,
                    COUNT(*) FILTER (WHERE txns_h24_buys + txns_h24_sells BETWEEN 10 AND 100) as moderate,
                    COUNT(*) FILTER (WHERE txns_h24_buys + txns_h24_sells < 10) as low,
                    COUNT(*) as total
                FROM dexscreener_tokens
                WHERE txns_h24_buys IS NOT NULL AND txns_h24_sells IS NOT NULL
            """))
            activity = result.fetchone()
            total = activity[4]
            print(f"  非常活跃 (>1000 txns/24h): {activity[0]} ({activity[0]/total*100:.1f}%)")
            print(f"  活跃 (100-1000 txns/24h): {activity[1]} ({activity[1]/total*100:.1f}%)")
            print(f"  中等 (10-100 txns/24h): {activity[2]} ({activity[2]/total*100:.1f}%)")
            print(f"  低活跃 (<10 txns/24h): {activity[3]} ({activity[3]/total*100:.1f}%)")

    finally:
        await db_manager.close()


# ==================== 高级示例 4: 自定义过滤器 ====================

class TokenFilter:
    """代币过滤器类"""

    @staticmethod
    def high_quality(token: Dict[str, Any]) -> bool:
        """高质量代币：高流动性、高交易量"""
        liquidity = token.get('liquidity', {}).get('usd', 0) or 0
        volume = token.get('volume', {}).get('h24', 0) or 0
        return liquidity > 50000 and volume > 10000

    @staticmethod
    def trending(token: Dict[str, Any]) -> bool:
        """趋势代币：24小时涨幅大"""
        price_change = token.get('priceChange', {}).get('h24', 0) or 0
        volume = token.get('volume', {}).get('h24', 0) or 0
        return price_change > 10 and volume > 5000

    @staticmethod
    def safe(token: Dict[str, Any]) -> bool:
        """安全代币：有官网、有社交媒体"""
        info = token.get('info', {})
        has_website = len(info.get('websites', [])) > 0
        has_socials = len(info.get('socials', [])) > 0
        return has_website and has_socials

    @staticmethod
    def new_listing(token: Dict[str, Any]) -> bool:
        """新上市代币：创建时间在7天内"""
        created_at = token.get('pairCreatedAt')
        if not created_at:
            return False

        created_time = datetime.fromtimestamp(created_at / 1000)
        age = datetime.now() - created_time
        return age < timedelta(days=7)


async def example4_custom_filters():
    """示例4: 使用自定义过滤器"""
    print("\n" + "=" * 80)
    print("高级示例 4: 自定义过滤器")
    print("=" * 80)

    service = DexScreenerService()

    try:
        # 爬取数据
        print("\n爬取数据...")
        tokens = service.scrape_and_fetch(target_count=50, headless=True)
        print(f"✓ 爬取到 {len(tokens)} 个代币")

        # 应用各种过滤器
        filters = {
            "高质量": TokenFilter.high_quality,
            "趋势": TokenFilter.trending,
            "安全": TokenFilter.safe,
            "新上市": TokenFilter.new_listing,
        }

        print("\n应用过滤器:")
        for name, filter_func in filters.items():
            filtered = [t for t in tokens if filter_func(t)]
            print(f"  {name:>6}: {len(filtered):>3} 个代币")

        # 组合过滤：高质量 + 安全
        combined = [
            t for t in tokens
            if TokenFilter.high_quality(t) and TokenFilter.safe(t)
        ]
        print(f"\n组合过滤（高质量 + 安全）: {len(combined)} 个代币")

        if combined:
            print("\n符合条件的代币:")
            for token in combined[:5]:
                symbol = token.get('baseToken', {}).get('symbol', 'N/A')
                price = token.get('priceUsd', 'N/A')
                liquidity = token.get('liquidity', {}).get('usd', 0)
                volume = token.get('volume', {}).get('h24', 0)
                print(f"  {symbol:>10}: ${float(price):>12.6f} | "
                      f"流动性: ${liquidity:>12,.2f} | "
                      f"交易量: ${volume:>12,.2f}")

            # 导入过滤后的代币
            stats = await service.import_tokens(combined)
            print(f"\n✓ 导入了 {stats['inserted']} 个高质量代币")

    finally:
        await service.close()


# ==================== 高级示例 5: 批量操作 ====================

async def example5_batch_operations():
    """示例5: 批量操作和性能优化"""
    print("\n" + "=" * 80)
    print("高级示例 5: 批量操作")
    print("=" * 80)

    service = DexScreenerService()

    try:
        # 模拟批量爬取多个来源
        print("\n批量爬取（模拟多次爬取）...")

        all_tokens = []
        batch_sizes = [20, 20, 20]  # 3批，每批20个

        for i, batch_size in enumerate(batch_sizes, 1):
            print(f"\n批次 {i}/{len(batch_sizes)}: 爬取 {batch_size} 个代币...")

            tokens = service.scrape_and_fetch(
                target_count=batch_size,
                headless=True
            )

            all_tokens.extend(tokens)
            print(f"  ✓ 本批获取: {len(tokens)}")
            print(f"  ✓ 累计获取: {len(all_tokens)}")

            # 批次间休息
            if i < len(batch_sizes):
                await asyncio.sleep(2)

        # 批量导入
        print(f"\n批量导入 {len(all_tokens)} 个代币...")
        stats = await service.import_tokens(all_tokens)
        print(f"✓ 插入: {stats['inserted']}, 更新: {stats['updated']}")

        # 批量去重
        print("\n批量去重...")
        dedup_result = await service.deduplicate_tokens(dry_run=False)
        if dedup_result['pairs_to_delete'] > 0:
            print(f"✓ 删除: {dedup_result['pairs_to_delete']} 条重复")
        else:
            print("✓ 无需去重")

    finally:
        await service.close()


# ==================== 高级示例 6: 数据导出 ====================

async def example6_data_export():
    """示例6: 导出数据为不同格式"""
    print("\n" + "=" * 80)
    print("高级示例 6: 数据导出")
    print("=" * 80)

    db_manager = DatabaseManager()
    await db_manager.init_async_db()

    try:
        async with db_manager.get_session() as session:
            # 查询数据
            result = await session.execute(text("""
                SELECT
                    base_token_symbol,
                    base_token_name,
                    price_usd,
                    liquidity_usd,
                    volume_h24,
                    market_cap,
                    dex_id,
                    pair_address
                FROM dexscreener_tokens
                ORDER BY liquidity_usd DESC NULLS LAST
                LIMIT 20
            """))

            tokens = result.fetchall()

            # 导出为CSV
            import csv
            csv_file = "/tmp/top_tokens.csv"
            print(f"\n导出为CSV: {csv_file}")

            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Symbol', 'Name', 'Price USD', 'Liquidity USD',
                    'Volume 24h', 'Market Cap', 'DEX', 'Pair Address'
                ])

                for token in tokens:
                    writer.writerow(token)

            print(f"✓ 已导出 {len(tokens)} 条记录到 CSV")

            # 导出为JSON
            import json
            json_file = "/tmp/top_tokens_export.json"
            print(f"\n导出为JSON: {json_file}")

            data = [
                {
                    "symbol": t[0],
                    "name": t[1],
                    "price_usd": float(t[2]) if t[2] else None,
                    "liquidity_usd": float(t[3]) if t[3] else None,
                    "volume_24h": float(t[4]) if t[4] else None,
                    "market_cap": float(t[5]) if t[5] else None,
                    "dex": t[6],
                    "pair_address": t[7]
                }
                for t in tokens
            ]

            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"✓ 已导出 {len(tokens)} 条记录到 JSON")

            # 打印预览
            print("\n数据预览（前5条）:")
            print(f"{'Symbol':>10} | {'Price USD':>15} | {'Liquidity USD':>15} | {'Volume 24h':>15}")
            print("-" * 70)
            for token in tokens[:5]:
                symbol = token[0] or 'N/A'
                price = float(token[2]) if token[2] else 0
                liq = float(token[3]) if token[3] else 0
                vol = float(token[4]) if token[4] else 0
                print(f"{symbol:>10} | ${price:>14.6f} | ${liq:>14,.2f} | ${vol:>14,.2f}")

    finally:
        await db_manager.close()


# ==================== 主函数 ====================

async def main():
    """运行高级示例"""
    print("\n" + "=" * 80)
    print("DexScreener 服务 - 高级用法示例")
    print("=" * 80)

    examples = {
        "1": ("错误重试机制", example1_retry_mechanism),
        "2": ("定时更新任务", example2_scheduled_update),
        "3": ("数据质量分析", example3_data_quality_analysis),
        "4": ("自定义过滤器", example4_custom_filters),
        "5": ("批量操作", example5_batch_operations),
        "6": ("数据导出", example6_data_export),
    }

    print("\n可用示例:")
    for key, (desc, _) in examples.items():
        print(f"  {key}. {desc}")
    print("  0. 运行所有示例")
    print("  q. 退出")

    choice = input("\n请选择示例 (1-6, 0, q): ").strip()

    if choice == 'q':
        print("\n再见!")
        return

    if choice == '0':
        # 运行所有示例
        for key, (desc, func) in examples.items():
            try:
                await func()
                print("\n" + "-" * 80)
            except Exception as e:
                logger.exception(f"示例 {key} 失败")
    elif choice in examples:
        # 运行单个示例
        desc, func = examples[choice]
        try:
            await func()
        except Exception as e:
            logger.exception("示例失败")
    else:
        print(f"\n✗ 无效选择: {choice}")

    print("\n" + "=" * 80)
    print("高级示例运行完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
