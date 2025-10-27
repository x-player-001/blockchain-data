#!/usr/bin/env python3
"""
K线数据补齐脚本
用于补齐数据库中缺失的K线数据

使用方法：
    python3 backfill_klines.py              # 只补齐缺失的代币
    python3 backfill_klines.py --force      # 强制重新拉取所有代币
    python3 backfill_klines.py --check      # 只检查，不拉取
"""

import asyncio
import argparse
import logging
from datetime import datetime
from sqlalchemy import select, func, and_

from src.storage.db_manager import DatabaseManager
from src.storage.models import MonitoredToken, PotentialToken, TokenKline
from src.services.kline_service import KlineService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/backfill_klines.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def check_missing_klines():
    """
    检查哪些代币缺失K线数据

    Returns:
        (missing_tokens, total_tokens, stats)
    """
    db_manager = DatabaseManager()
    missing_tokens = []

    try:
        async with db_manager.get_session() as session:
            # 1. 获取所有监控代币
            monitored_result = await session.execute(
                select(MonitoredToken).where(
                    and_(
                        MonitoredToken.deleted_at.is_(None),
                        MonitoredToken.permanently_deleted == 0
                    )
                )
            )
            monitored_tokens = monitored_result.scalars().all()

            # 2. 获取所有潜力代币
            potential_result = await session.execute(
                select(PotentialToken).where(
                    and_(
                        PotentialToken.is_added_to_monitoring == 0,
                        PotentialToken.deleted_at.is_(None),
                        PotentialToken.permanently_deleted == 0
                    )
                )
            )
            potential_tokens = potential_result.scalars().all()

            # 3. 检查每个代币的K线数据
            logger.info("=" * 80)
            logger.info("开始检查K线数据...")
            logger.info("=" * 80)

            total_monitored = len(monitored_tokens)
            total_potential = len(potential_tokens)
            total_tokens = total_monitored + total_potential

            logger.info(f"监控代币: {total_monitored} 个")
            logger.info(f"潜力代币: {total_potential} 个")
            logger.info(f"总计: {total_tokens} 个")
            logger.info("-" * 80)

            # 检查监控代币
            for token in monitored_tokens:
                kline_count_result = await session.execute(
                    select(func.count(TokenKline.id)).where(
                        and_(
                            TokenKline.pair_address == token.pair_address.lower(),
                            TokenKline.timeframe == "minute",
                            TokenKline.aggregate == 5
                        )
                    )
                )
                kline_count = kline_count_result.scalar()

                if kline_count == 0:
                    missing_tokens.append({
                        "type": "monitored",
                        "token_address": token.token_address,
                        "pair_address": token.pair_address,
                        "chain": token.chain,
                        "symbol": getattr(token, 'token_symbol', 'N/A'),
                        "kline_count": 0
                    })
                    logger.info(
                        f"❌ [监控] {getattr(token, 'token_symbol', 'N/A'):10s} "
                        f"{token.token_address[:10]}... - 缺失K线数据"
                    )
                else:
                    logger.info(
                        f"✅ [监控] {getattr(token, 'token_symbol', 'N/A'):10s} "
                        f"{token.token_address[:10]}... - 已有 {kline_count} 根K线"
                    )

            # 检查潜力代币
            for token in potential_tokens:
                kline_count_result = await session.execute(
                    select(func.count(TokenKline.id)).where(
                        and_(
                            TokenKline.pair_address == token.pair_address.lower(),
                            TokenKline.timeframe == "minute",
                            TokenKline.aggregate == 5
                        )
                    )
                )
                kline_count = kline_count_result.scalar()

                if kline_count == 0:
                    missing_tokens.append({
                        "type": "potential",
                        "token_address": token.token_address,
                        "pair_address": token.pair_address,
                        "chain": token.chain,
                        "symbol": getattr(token, 'token_symbol', 'N/A'),
                        "kline_count": 0
                    })
                    logger.info(
                        f"❌ [潜力] {getattr(token, 'token_symbol', 'N/A'):10s} "
                        f"{token.token_address[:10]}... - 缺失K线数据"
                    )
                else:
                    logger.info(
                        f"✅ [潜力] {getattr(token, 'token_symbol', 'N/A'):10s} "
                        f"{token.token_address[:10]}... - 已有 {kline_count} 根K线"
                    )

            logger.info("=" * 80)
            logger.info(f"检查完成: 总计 {total_tokens} 个代币，缺失 {len(missing_tokens)} 个")
            logger.info("=" * 80)

            stats = {
                "total_tokens": total_tokens,
                "total_monitored": total_monitored,
                "total_potential": total_potential,
                "missing_count": len(missing_tokens),
                "missing_monitored": len([t for t in missing_tokens if t["type"] == "monitored"]),
                "missing_potential": len([t for t in missing_tokens if t["type"] == "potential"])
            }

            return missing_tokens, total_tokens, stats

    finally:
        await db_manager.close()


async def backfill_missing_klines(missing_tokens, delay=2.5):
    """
    补齐缺失的K线数据

    Args:
        missing_tokens: 缺失K线的代币列表
        delay: 每次请求之间的延迟（秒）
    """
    if not missing_tokens:
        logger.info("没有需要补齐的K线数据")
        return

    kline_service = KlineService()

    logger.info("=" * 80)
    logger.info(f"开始补齐 {len(missing_tokens)} 个代币的K线数据...")
    logger.info(f"使用延迟: {delay} 秒/请求")
    logger.info("=" * 80)

    success_count = 0
    failed_count = 0
    total_fetched = 0
    total_saved = 0

    start_time = datetime.now()

    for idx, token_info in enumerate(missing_tokens, 1):
        logger.info(
            f"[{idx}/{len(missing_tokens)}] 补齐 {token_info['type']} 代币: "
            f"{token_info['symbol']} ({token_info['token_address'][:8]}...) "
            f"链: {token_info['chain']}"
        )

        try:
            stats = await kline_service.update_token_klines(
                token_address=token_info["token_address"],
                pair_address=token_info["pair_address"],
                chain=token_info["chain"],
                timeframe="minute",
                aggregate=5,
                max_candles=500
            )

            if stats["success"]:
                success_count += 1
                total_fetched += stats["fetched"]
                total_saved += stats["saved"]
                logger.info(
                    f"  ✅ 成功: 拉取 {stats['fetched']} 根，保存 {stats['saved']} 根"
                )
            else:
                failed_count += 1
                logger.error(
                    f"  ❌ 失败: {stats.get('error', 'Unknown error')}"
                )

        except Exception as e:
            failed_count += 1
            logger.error(f"  ❌ 异常: {e}")

        # 延迟避免API限流
        if idx < len(missing_tokens):
            await asyncio.sleep(delay)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info("=" * 80)
    logger.info("补齐完成!")
    logger.info(f"总计: {len(missing_tokens)} 个代币")
    logger.info(f"成功: {success_count} 个")
    logger.info(f"失败: {failed_count} 个")
    logger.info(f"拉取: {total_fetched} 根K线")
    logger.info(f"保存: {total_saved} 根K线")
    logger.info(f"耗时: {duration:.2f} 秒 ({duration/60:.2f} 分钟)")
    logger.info("=" * 80)


async def backfill_all_klines(delay=2.5):
    """
    强制重新拉取所有代币的K线数据

    Args:
        delay: 每次请求之间的延迟（秒）
    """
    kline_service = KlineService()

    result = await kline_service.update_all_tokens_klines(
        timeframe="minute",
        aggregate=5,
        max_candles=500
    )

    logger.info("=" * 80)
    logger.info("强制补齐完成!")
    logger.info(f"监控代币: {result['monitored']} 个")
    logger.info(f"潜力代币: {result['potential']} 个")
    logger.info(f"总代币数: {result['total']} 个")
    logger.info(f"成功: {result['success']} 个")
    logger.info(f"失败: {result['failed']} 个")
    logger.info(f"拉取: {result['total_fetched']} 根K线")
    logger.info(f"保存: {result['total_saved']} 根K线")
    logger.info("=" * 80)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='K线数据补齐脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  python3 backfill_klines.py              # 只补齐缺失的代币
  python3 backfill_klines.py --force      # 强制重新拉取所有代币
  python3 backfill_klines.py --check      # 只检查，不拉取
  python3 backfill_klines.py --delay 3    # 自定义延迟时间（秒）
        """
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重新拉取所有代币（包括已有K线的）'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='只检查缺失情况，不进行补齐'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=2.5,
        help='每次请求之间的延迟时间（秒），默认2.5秒'
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("K线数据补齐脚本启动")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    if args.force:
        # 强制重新拉取所有代币
        logger.info("模式: 强制补齐所有代币")
        await backfill_all_klines(delay=args.delay)
    else:
        # 只补齐缺失的代币
        missing_tokens, total_tokens, stats = await check_missing_klines()

        if args.check:
            # 只检查，不补齐
            logger.info("=" * 80)
            logger.info("检查模式 - 不进行补齐")
            logger.info(f"总代币数: {stats['total_tokens']}")
            logger.info(f"  监控代币: {stats['total_monitored']}")
            logger.info(f"  潜力代币: {stats['total_potential']}")
            logger.info(f"缺失K线: {stats['missing_count']}")
            logger.info(f"  监控代币缺失: {stats['missing_monitored']}")
            logger.info(f"  潜力代币缺失: {stats['missing_potential']}")
            logger.info("=" * 80)
        else:
            # 补齐缺失的代币
            if missing_tokens:
                logger.info("模式: 补齐缺失的代币")
                await backfill_missing_klines(missing_tokens, delay=args.delay)
            else:
                logger.info("所有代币都已有K线数据，无需补齐")

    logger.info("=" * 80)
    logger.info("脚本执行完成")
    logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
