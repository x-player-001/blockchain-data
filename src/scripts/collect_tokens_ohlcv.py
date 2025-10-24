#!/usr/bin/env python3
"""
为数据库中的代币收集K线数据
使用SmartOHLCVCollector自动选择最优时间周期
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.db_manager import DatabaseManager
from src.collectors.smart_ohlcv_collector import SmartOHLCVCollector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def collect_ohlcv_for_tokens(
    limit: Optional[int] = None,
    data_source: Optional[str] = None,
    skip_existing: bool = True
):
    """
    为数据库中的代币收集K线数据

    Args:
        limit: 限制收集的代币数量
        data_source: 只收集特定来源的代币（如 'dexscreener'）
        skip_existing: 是否跳过已有K线数据的代币
    """
    db = DatabaseManager()
    await db.init_async_db()

    collector = SmartOHLCVCollector()

    try:
        async with db.get_session() as session:
            # 构建查询
            query = """
                SELECT
                    t.id,
                    t.symbol,
                    t.name,
                    t.address,
                    tp.pair_address,
                    tp.pair_created_at,
                    tp.dex_name
                FROM tokens t
                JOIN token_pairs tp ON t.id = tp.token_id
            """

            conditions = []
            params = {}

            if data_source:
                conditions.append("t.data_source = :data_source")
                params["data_source"] = data_source

            if skip_existing:
                conditions.append("""
                    NOT EXISTS (
                        SELECT 1 FROM token_ohlcv
                        WHERE token_id = t.id
                    )
                """)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY tp.liquidity_usd DESC NULLS LAST"

            if limit:
                query += f" LIMIT :limit"
                params["limit"] = limit

            # 执行查询
            result = await session.execute(text(query), params)
            tokens = result.fetchall()

            if not tokens:
                logger.warning("未找到需要收集K线的代币")
                return

            logger.info(f"找到 {len(tokens)} 个代币需要收集K线数据")

            # 收集统计
            success_count = 0
            error_count = 0
            skipped_count = 0

            for i, token in enumerate(tokens, 1):
                token_id = token[0]
                symbol = token[1]
                name = token[2]
                address = token[3]
                pair_address = token[4]
                pair_created_at = token[5]
                dex_name = token[6]

                logger.info(f"\n[{i}/{len(tokens)}] 处理代币: {symbol} ({name})")
                logger.info(f"  - Token ID: {token_id}")
                logger.info(f"  - Pair: {pair_address}")
                logger.info(f"  - DEX: {dex_name}")

                try:
                    # 使用智能收集器
                    result = await collector.collect_for_token(
                        token_id=token_id,
                        token_symbol=symbol,
                        pair_address=pair_address,
                        created_at=pair_created_at
                    )

                    if result.get('success'):
                        logger.info(f"  ✓ 成功收集 {result.get('actual_candles', 0)} 根K线")
                        logger.info(f"    - 时间周期: {result.get('timeframe')}")
                        logger.info(f"    - 聚合: {result.get('aggregate')}")
                        success_count += 1
                    elif result.get('skipped'):
                        logger.info(f"  ⊙ 跳过（数据已是最新）")
                        skipped_count += 1
                    else:
                        logger.warning(f"  ✗ 收集失败: {result.get('error', 'Unknown error')}")
                        error_count += 1

                except Exception as e:
                    logger.error(f"  ✗ 处理失败: {str(e)}")
                    error_count += 1

                # 避免请求过快
                if i < len(tokens):
                    await asyncio.sleep(0.5)

            # 输出统计
            logger.info("\n" + "=" * 80)
            logger.info("K线收集完成！")
            logger.info("=" * 80)
            logger.info(f"成功: {success_count}")
            logger.info(f"失败: {error_count}")
            logger.info(f"跳过: {skipped_count}")
            logger.info(f"总计: {len(tokens)}")
            logger.info("=" * 80)

    finally:
        await db.close()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='为数据库中的代币收集K线数据')
    parser.add_argument('--limit', type=int, help='限制收集的代币数量')
    parser.add_argument('--source', type=str, help='只收集特定来源的代币（如 dexscreener）')
    parser.add_argument('--no-skip-existing', action='store_true', help='不跳过已有K线数据的代币')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("为数据库中的代币收集K线数据")
    logger.info("=" * 80)

    if args.limit:
        logger.info(f"限制数量: {args.limit}")
    if args.source:
        logger.info(f"数据源: {args.source}")
    logger.info(f"跳过已有数据: {not args.no_skip_existing}")

    await collect_ohlcv_for_tokens(
        limit=args.limit,
        data_source=args.source,
        skip_existing=not args.no_skip_existing
    )


if __name__ == "__main__":
    asyncio.run(main())
