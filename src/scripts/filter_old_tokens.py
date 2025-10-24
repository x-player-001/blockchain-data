#!/usr/bin/env python3
"""
过滤数据库中的旧代币
删除超过指定天数的代币记录
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.db_manager import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def filter_old_tokens(max_age_days: int = 30, dry_run: bool = True):
    """
    过滤数据库中的旧代币

    Args:
        max_age_days: 最大年龄（天数）
        dry_run: 如果为True，只显示将要删除的记录，不实际删除
    """
    db = DatabaseManager()
    await db.init_async_db()

    try:
        # 计算截止时间戳（毫秒）
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        cutoff_timestamp = int(cutoff_time.timestamp() * 1000)

        logger.info(f"过滤条件: 删除 {max_age_days} 天前创建的代币")
        logger.info(f"截止时间: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"截止时间戳: {cutoff_timestamp}")

        async with db.get_session() as session:
            # 1. 查询总体统计
            stats_query = text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE pair_created_at IS NULL) as no_timestamp,
                    COUNT(*) FILTER (WHERE pair_created_at >= :cutoff) as keep,
                    COUNT(*) FILTER (WHERE pair_created_at < :cutoff) as delete
                FROM dexscreener_tokens
            """)

            result = await session.execute(stats_query, {"cutoff": cutoff_timestamp})
            stats = result.fetchone()

            logger.info("\n" + "=" * 80)
            logger.info("数据库统计:")
            logger.info(f"  总记录数: {stats[0]}")
            logger.info(f"  无创建时间: {stats[1]} (将保留)")
            logger.info(f"  {max_age_days}天内: {stats[2]} (将保留)")
            logger.info(f"  {max_age_days}天前: {stats[3]} (将删除)")
            logger.info("=" * 80)

            if stats[3] == 0:
                logger.info("\n✓ 没有需要删除的旧代币")
                return {
                    "total": stats[0],
                    "to_delete": 0,
                    "to_keep": stats[0],
                    "deleted": False
                }

            # 2. 查询将要删除的代币详情
            detail_query = text("""
                SELECT
                    base_token_symbol,
                    base_token_name,
                    pair_address,
                    pair_created_at,
                    liquidity_usd,
                    dex_id
                FROM dexscreener_tokens
                WHERE pair_created_at < :cutoff
                ORDER BY pair_created_at ASC
            """)

            result = await session.execute(detail_query, {"cutoff": cutoff_timestamp})
            old_tokens = result.fetchall()

            logger.info(f"\n将要删除的代币详情（共 {len(old_tokens)} 个）:")
            logger.info(f"{'代币':<12} | {'创建日期':<12} | {'年龄':>8} | {'流动性':>15} | {'DEX':<12}")
            logger.info("-" * 80)

            for token in old_tokens:
                symbol = token[0] or 'N/A'
                created_at = token[3]

                if created_at:
                    created_time = datetime.fromtimestamp(created_at / 1000)
                    age_days = (datetime.now() - created_time).days
                    created_str = created_time.strftime('%Y-%m-%d')
                    age_str = f"{age_days}天前"
                else:
                    created_str = "未知"
                    age_str = "N/A"

                liquidity = float(token[4]) if token[4] else 0
                dex = token[5] or 'N/A'

                logger.info(f"{symbol:<12} | {created_str:<12} | {age_str:>8} | ${liquidity:>14,.2f} | {dex:<12}")

            # 3. 执行删除（如果不是预览模式）
            if not dry_run:
                logger.info("\n" + "=" * 80)
                logger.info("执行删除操作...")

                delete_query = text("""
                    DELETE FROM dexscreener_tokens
                    WHERE pair_created_at < :cutoff
                """)

                result = await session.execute(delete_query, {"cutoff": cutoff_timestamp})
                await session.commit()

                deleted_count = result.rowcount
                logger.info(f"✓ 已删除 {deleted_count} 条记录")

                # 验证结果
                verify_query = text("SELECT COUNT(*) FROM dexscreener_tokens")
                result = await session.execute(verify_query)
                remaining = result.scalar()

                logger.info(f"✓ 数据库中剩余 {remaining} 条记录")
                logger.info("=" * 80)

                return {
                    "total": stats[0],
                    "to_delete": deleted_count,
                    "to_keep": remaining,
                    "deleted": True
                }
            else:
                logger.info("\n" + "=" * 80)
                logger.info("[预览模式] 未实际删除数据")
                logger.info("运行时添加 --execute 参数来实际执行删除")
                logger.info("=" * 80)

                return {
                    "total": stats[0],
                    "to_delete": stats[3],
                    "to_keep": stats[0] - stats[3],
                    "deleted": False
                }

    finally:
        await db.close()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="过滤数据库中的旧代币")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="代币最大年龄（天数），默认30天"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="实际执行删除操作（默认为预览模式）"
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("过滤数据库中的旧代币")
    logger.info("=" * 80)

    if args.execute:
        logger.info(f"模式: 执行删除（删除 {args.days} 天前的代币）")
        confirm = input(f"\n确认要删除超过 {args.days} 天的代币吗？(yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("取消操作")
            return
    else:
        logger.info(f"模式: 预览（查看 {args.days} 天前的代币）")

    result = await filter_old_tokens(max_age_days=args.days, dry_run=not args.execute)

    logger.info("\n" + "=" * 80)
    logger.info("执行摘要:")
    logger.info(f"  原始记录数: {result['total']}")
    logger.info(f"  将保留: {result['to_keep']}")
    logger.info(f"  将删除: {result['to_delete']}")
    if result['deleted']:
        logger.info(f"  状态: ✓ 已删除")
    else:
        logger.info(f"  状态: 预览模式")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
