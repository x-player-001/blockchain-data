#!/usr/bin/env python3
"""
去重脚本：每个代币只保留流动性最大的交易对
删除其他低流动性的重复交易对
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.db_manager import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def deduplicate_tokens(dry_run=True):
    """
    去重代币，每个代币只保留流动性最大的交易对

    Args:
        dry_run: 如果为True，只显示将要删除的记录，不实际删除
    """
    db = DatabaseManager()
    await db.init_async_db()

    async with db.get_session() as session:
        # 查找所有有重复的代币
        find_duplicates_query = text("""
            SELECT
                base_token_address,
                base_token_symbol,
                base_token_name,
                COUNT(*) as pair_count
            FROM dexscreener_tokens
            GROUP BY base_token_address, base_token_symbol, base_token_name
            HAVING COUNT(*) > 1
        """)

        result = await session.execute(find_duplicates_query)
        duplicate_tokens = result.fetchall()

        logger.info(f"找到 {len(duplicate_tokens)} 个有重复交易对的代币")

        total_to_delete = 0
        deleted_pairs = []

        for token_addr, symbol, name, count in duplicate_tokens:
            logger.info(f"\n处理代币: {symbol} ({name}) - 有 {count} 个交易对")

            # 查找该代币的所有交易对，按流动性排序
            find_pairs_query = text("""
                SELECT
                    id,
                    pair_address,
                    dex_id,
                    liquidity_usd,
                    volume_h24
                FROM dexscreener_tokens
                WHERE base_token_address = :token_addr
                ORDER BY
                    COALESCE(liquidity_usd, 0) DESC,
                    COALESCE(volume_h24, 0) DESC
            """)

            result = await session.execute(find_pairs_query, {"token_addr": token_addr})
            pairs = result.fetchall()

            # 第一个是流动性最大的，保留
            keep_pair = pairs[0]
            logger.info(f"  ✓ 保留: {keep_pair[1][:20]}... (DEX: {keep_pair[2]}, 流动性: ${float(keep_pair[3]) if keep_pair[3] else 0:,.2f})")

            # 其余的标记为删除
            for pair in pairs[1:]:
                pair_id, pair_addr, dex, liq, vol = pair
                liq_str = f"${float(liq):,.2f}" if liq else "$0"
                logger.info(f"  ✗ 删除: {pair_addr[:20]}... (DEX: {dex}, 流动性: {liq_str})")
                deleted_pairs.append(pair_id)
                total_to_delete += 1

        logger.info("\n" + "=" * 80)
        logger.info(f"统计:")
        logger.info(f"  重复代币数: {len(duplicate_tokens)}")
        logger.info(f"  将删除的交易对数: {total_to_delete}")
        logger.info("=" * 80)

        if not dry_run and deleted_pairs:
            # 执行删除
            delete_query = text("""
                DELETE FROM dexscreener_tokens
                WHERE id = ANY(:ids)
            """)

            await session.execute(delete_query, {"ids": deleted_pairs})
            await session.commit()

            logger.info(f"\n✓ 已删除 {total_to_delete} 条重复记录")

            # 验证结果
            verify_query = text("SELECT COUNT(*) FROM dexscreener_tokens")
            result = await session.execute(verify_query)
            remaining = result.scalar()

            logger.info(f"✓ 数据库中剩余 {remaining} 条记录")

            # 验证是否还有重复
            verify_duplicates = text("""
                SELECT COUNT(*)
                FROM (
                    SELECT base_token_address
                    FROM dexscreener_tokens
                    GROUP BY base_token_address
                    HAVING COUNT(*) > 1
                ) as duplicates
            """)
            result = await session.execute(verify_duplicates)
            duplicate_count = result.scalar()

            if duplicate_count == 0:
                logger.info("✓ 去重完成！没有重复的代币了")
            else:
                logger.warning(f"⚠ 还有 {duplicate_count} 个代币有重复")
        else:
            logger.info("\n[预览模式] 未实际删除数据")
            logger.info("运行时添加 --execute 参数来实际执行删除")

    await db.close()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="去重DexScreener代币数据")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="实际执行删除操作（默认为预览模式）"
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("DexScreener 代币去重工具")
    logger.info("=" * 80)

    if args.execute:
        logger.info("模式: 执行删除")
        confirm = input("\n确认要删除重复的交易对吗？(yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("取消操作")
            return
    else:
        logger.info("模式: 预览（不会实际删除）")

    await deduplicate_tokens(dry_run=not args.execute)

    logger.info("\n完成！")


if __name__ == "__main__":
    asyncio.run(main())
