#!/usr/bin/env python3
"""
收集DexScreener代币的K线数据
使用智能时间框架选择，根据代币年龄自动调整
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.db_manager import DatabaseManager
from src.api_clients.geckoterminal_client import GeckoTerminalClient
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class DexScreenerOHLCVCollector:
    """为DexScreener代币收集K线数据"""

    MAX_CANDLES = 200

    def __init__(self):
        """初始化收集器"""
        self.client = GeckoTerminalClient()
        self.db = DatabaseManager()

    def calculate_optimal_timeframe(
        self,
        created_at: datetime,
        max_candles: int = MAX_CANDLES
    ) -> Tuple[str, int, int]:
        """
        根据代币年龄计算最优时间框架

        Args:
            created_at: 代币创建时间
            max_candles: 最大K线数

        Returns:
            (timeframe, expected_candles, aggregate)
        """
        now = datetime.utcnow()
        age_minutes = (now - created_at).total_seconds() / 60

        logger.debug(f"代币年龄: {age_minutes:.0f}分钟 ({age_minutes/60:.1f}小时, {age_minutes/1440:.1f}天)")

        # 尝试分钟级时间框架
        for agg in [1, 5, 15]:
            candles = age_minutes / agg
            if candles <= max_candles:
                logger.debug(f"选择: {agg}分钟 (约{candles:.0f}根K线)")
                return ('minute', int(candles), agg)

        # 尝试小时级时间框架
        age_hours = age_minutes / 60
        for agg in [1, 4, 12]:
            candles = age_hours / agg
            if candles <= max_candles:
                logger.debug(f"选择: {agg}小时 (约{candles:.0f}根K线)")
                return ('hour', int(candles), agg)

        # 兜底：天级时间框架
        age_days = age_minutes / 1440
        candles = min(age_days, max_candles)
        logger.debug(f"选择: 1天 (约{candles:.0f}根K线)")
        return ('day', int(candles), 1)

    async def collect_for_token(
        self,
        token_id: str,
        symbol: str,
        pair_address: str,
        created_at: Optional[datetime],
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        为单个代币收集K线数据

        Args:
            token_id: 代币ID（使用pair_address）
            symbol: 代币符号
            pair_address: 交易对地址
            created_at: 创建时间
            skip_existing: 是否跳过已有数据

        Returns:
            收集统计信息
        """
        stats = {
            'token_id': token_id,
            'symbol': symbol,
            'pair_address': pair_address,
            'timeframe': None,
            'expected_candles': 0,
            'actual_candles': 0,
            'skipped': False,
            'success': False,
            'error': None
        }

        try:
            # 检查已有数据
            latest_candle_time = None
            existing_count = 0

            if skip_existing:
                latest_candle_time = await self._get_latest_candle_time(token_id, pair_address)
                existing_count = await self._get_existing_candle_count(token_id, pair_address)

                if latest_candle_time:
                    logger.info(f"{symbol}: 已有 {existing_count} 根K线，最新: {latest_candle_time}")
                    # 使用最新K线时间作为新的起点
                    created_at = latest_candle_time

            # 如果没有创建时间，使用默认值
            if not created_at:
                logger.warning(f"{symbol}: 无创建时间，使用默认值（100天前）")
                created_at = datetime.utcnow() - timedelta(days=100)

            # 计算时间差距
            now = datetime.utcnow()
            time_gap_minutes = (now - created_at).total_seconds() / 60

            # 如果时间差距太小，跳过
            if time_gap_minutes < 5:
                logger.info(f"{symbol}: 数据已是最新 (差距: {time_gap_minutes:.1f}分钟)，跳过")
                stats['skipped'] = True
                stats['actual_candles'] = existing_count
                return stats

            # 计算最优时间框架
            timeframe, expected_candles, aggregate = self.calculate_optimal_timeframe(created_at)

            stats['timeframe'] = f"{aggregate}{timeframe[0]}"
            stats['expected_candles'] = expected_candles

            # 日志
            if latest_candle_time:
                logger.info(f"{symbol}: 增量更新 - {timeframe} (聚合={aggregate}, 预期≈{expected_candles}根新K线)")
            else:
                logger.info(f"{symbol}: 首次收集 - {timeframe} (聚合={aggregate}, 预期≈{expected_candles}根)")

            # 获取K线数据
            if expected_candles > 100:
                ohlcv_data = await self.client.get_ohlcv_historical(
                    pool_address=pair_address,
                    timeframe=timeframe,
                    max_candles=expected_candles,
                    aggregate=aggregate
                )
            else:
                ohlcv_data = await self.client.get_ohlcv(
                    pool_address=pair_address,
                    timeframe=timeframe,
                    aggregate=aggregate
                )

            if not ohlcv_data:
                logger.warning(f"{symbol}: 未获取到K线数据")
                stats['error'] = "无数据"
                return stats

            # 如果是增量更新，过滤旧数据
            if latest_candle_time:
                latest_timestamp = int(latest_candle_time.timestamp())
                original_count = len(ohlcv_data)
                ohlcv_data = [c for c in ohlcv_data if c[0] > latest_timestamp]
                filtered_count = original_count - len(ohlcv_data)

                if filtered_count > 0:
                    logger.debug(f"{symbol}: 过滤了 {filtered_count} 根重复K线，剩余 {len(ohlcv_data)} 根新K线")

                if not ohlcv_data:
                    logger.info(f"{symbol}: 过滤后无新K线，数据已是最新")
                    stats['skipped'] = True
                    stats['actual_candles'] = existing_count
                    return stats

            # 保存到数据库
            saved_count = await self._save_ohlcv(
                token_id=token_id,
                pool_address=pair_address,
                timeframe=f"{aggregate}{timeframe[0]}",
                ohlcv_data=ohlcv_data
            )

            stats['actual_candles'] = saved_count
            stats['success'] = True

            logger.info(f"{symbol}: ✓ 保存了 {saved_count} 根K线")

        except Exception as e:
            logger.error(f"{symbol}: 收集K线出错 - {e}")
            stats['error'] = str(e)

        return stats

    async def collect_all(
        self,
        limit: Optional[int] = None,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        为所有DexScreener代币收集K线

        Args:
            limit: 限制处理的代币数量
            skip_existing: 是否跳过已有数据

        Returns:
            总体统计信息
        """
        logger.info("=" * 80)
        logger.info("开始收集DexScreener代币K线数据")
        logger.info(f"最大K线数: {self.MAX_CANDLES}")
        logger.info(f"跳过已有数据: {skip_existing}")
        logger.info("=" * 80)

        overall_stats = {
            'total_tokens': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'total_candles': 0,
            'tokens': [],
            'start_time': datetime.now()
        }

        await self.db.init_async_db()

        async with self.client:
            # 获取DexScreener代币列表
            async with self.db.get_session() as session:
                query = text("""
                    SELECT
                        pair_address,
                        base_token_symbol,
                        base_token_name,
                        pair_created_at
                    FROM dexscreener_tokens
                    WHERE pair_address IS NOT NULL
                    ORDER BY pair_created_at DESC NULLS LAST
                """)

                if limit:
                    query = text(str(query) + f" LIMIT {limit}")

                result = await session.execute(query)
                tokens = result.fetchall()

            if not tokens:
                logger.warning("未找到DexScreener代币")
                return overall_stats

            overall_stats['total_tokens'] = len(tokens)
            logger.info(f"找到 {len(tokens)} 个代币需要处理\n")

            # 处理每个代币
            for i, token_row in enumerate(tokens, 1):
                pair_address = token_row[0]
                symbol = token_row[1] or 'N/A'
                created_at_timestamp = token_row[3]

                # 转换时间戳
                created_at = None
                if created_at_timestamp:
                    created_at = datetime.fromtimestamp(created_at_timestamp / 1000)

                logger.info(f"[{i}/{len(tokens)}] 处理 {symbol}...")

                # 收集K线
                stats = await self.collect_for_token(
                    token_id=pair_address,  # 使用pair_address作为token_id
                    symbol=symbol,
                    pair_address=pair_address,
                    created_at=created_at,
                    skip_existing=skip_existing
                )

                overall_stats['tokens'].append(stats)

                if stats['skipped']:
                    overall_stats['skipped'] += 1
                    overall_stats['total_candles'] += stats['actual_candles']
                elif stats['success']:
                    overall_stats['successful'] += 1
                    overall_stats['total_candles'] += stats['actual_candles']
                else:
                    overall_stats['failed'] += 1

                # 限速（30 req/min = 2秒/请求）
                await asyncio.sleep(2)

        await self.db.close()

        overall_stats['end_time'] = datetime.now()
        overall_stats['duration'] = (overall_stats['end_time'] - overall_stats['start_time']).total_seconds()

        # 打印总结
        self._print_summary(overall_stats)

        return overall_stats

    async def _get_existing_candle_count(self, token_id: str, pool_address: str) -> int:
        """获取已有K线数量"""
        async with self.db.get_session() as session:
            result = await session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM token_ohlcv
                    WHERE token_id = :token_id AND pool_address = :pool_address
                """),
                {"token_id": token_id, "pool_address": pool_address}
            )
            count = result.scalar()
            return count or 0

    async def _get_latest_candle_time(self, token_id: str, pool_address: str) -> Optional[datetime]:
        """获取最新K线时间"""
        async with self.db.get_session() as session:
            result = await session.execute(
                text("""
                    SELECT MAX(timestamp)
                    FROM token_ohlcv
                    WHERE token_id = :token_id AND pool_address = :pool_address
                """),
                {"token_id": token_id, "pool_address": pool_address}
            )
            latest_time = result.scalar()
            return latest_time

    async def _save_ohlcv(
        self,
        token_id: str,
        pool_address: str,
        timeframe: str,
        ohlcv_data: List[List[float]]
    ) -> int:
        """保存K线数据到数据库"""
        if ohlcv_data:
            saved = await self.db.batch_insert_ohlcv(token_id, pool_address, timeframe, ohlcv_data)
            return saved
        return 0

    def _print_summary(self, stats: Dict[str, Any]) -> None:
        """打印收集总结"""
        logger.info("\n" + "=" * 80)
        logger.info("DEXSCREENER K线收集总结")
        logger.info("=" * 80)
        logger.info(f"总代币数:      {stats['total_tokens']:>6}")
        logger.info(f"成功:          {stats['successful']:>6}")
        logger.info(f"跳过:          {stats['skipped']:>6}")
        logger.info(f"失败:          {stats['failed']:>6}")
        logger.info(f"总K线数:       {stats['total_candles']:>6}")
        logger.info(f"耗时:          {stats['duration']:.1f}秒")
        logger.info("=" * 80)

        # 显示时间框架分布
        timeframe_dist = {}
        for token_stats in stats['tokens']:
            if token_stats['success']:
                tf = token_stats['timeframe']
                timeframe_dist[tf] = timeframe_dist.get(tf, 0) + 1

        if timeframe_dist:
            logger.info("\n时间框架分布:")
            for tf, count in sorted(timeframe_dist.items()):
                logger.info(f"  {tf}: {count} 个代币")


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="收集DexScreener代币K线数据")
    parser.add_argument(
        "--limit",
        type=int,
        help="限制处理的代币数量"
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="不跳过已有数据（重新收集）"
    )

    args = parser.parse_args()

    collector = DexScreenerOHLCVCollector()

    result = await collector.collect_all(
        limit=args.limit,
        skip_existing=not args.no_skip_existing
    )

    if result['failed'] > 0:
        logger.warning(f"\n有 {result['failed']} 个代币收集失败")

    logger.info("\n完成！")


if __name__ == "__main__":
    asyncio.run(main())
