#!/usr/bin/env python3
"""
直接从dexscreener_tokens表收集K线数据
不需要先导入到tokens表，更加高效
"""

import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.db_manager import DatabaseManager
from src.api_clients.geckoterminal_client import GeckoTerminalClient
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class DirectDexScreenerOHLCVCollector:
    """直接从DexScreener代币收集K线数据"""

    MAX_CANDLES = 200

    def __init__(self):
        self.client = GeckoTerminalClient()
        self.db = None

    async def init_db(self):
        """初始化数据库"""
        self.db = DatabaseManager()
        await self.db.init_async_db()

    async def close(self):
        """关闭数据库连接"""
        if self.db:
            await self.db.close()

    def calculate_optimal_timeframe(
        self,
        created_at: Optional[datetime]
    ) -> tuple[str, int, int]:
        """
        计算最优时间周期

        Args:
            created_at: 代币创建时间

        Returns:
            (timeframe, expected_candles, aggregate)
        """
        if not created_at:
            # 如果没有创建时间，默认使用4小时
            return ('hour', self.MAX_CANDLES, 4)

        now = datetime.utcnow()
        age = now - created_at
        age_minutes = age.total_seconds() / 60
        age_hours = age_minutes / 60

        # 尝试分钟级别
        for agg in [1, 5, 15]:
            candles = age_minutes / agg
            if candles <= self.MAX_CANDLES:
                return ('minute', int(candles), agg)

        # 尝试小时级别
        for agg in [1, 4, 12]:
            candles = age_hours / agg
            if candles <= self.MAX_CANDLES:
                return ('hour', int(candles), agg)

        # 降级到天级别
        age_days = age_hours / 24
        return ('day', int(age_days), 1)

    async def collect_for_token(
        self,
        token_data: Dict[str, Any],
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        为单个代币收集K线数据

        Args:
            token_data: DexScreener代币数据
            skip_existing: 是否跳过已有数据

        Returns:
            收集结果统计
        """
        symbol = token_data['symbol']
        pair_address = token_data['pair_address']
        created_at = token_data.get('pair_created_at')

        stats = {
            'symbol': symbol,
            'pair_address': pair_address,
            'success': False,
            'skipped': False,
            'error': None,
            'timeframe': None,
            'aggregate': None,
            'candles_saved': 0
        }

        try:
            # 检查是否已有数据
            if skip_existing:
                async with self.db.get_session() as session:
                    result = await session.execute(
                        text("SELECT COUNT(*) FROM token_ohlcv WHERE pool_address = :pool_address"),
                        {"pool_address": pair_address}
                    )
                    count = result.scalar()
                    if count > 0:
                        logger.info(f"{symbol}: 已有 {count} 根K线，跳过")
                        stats['skipped'] = True
                        stats['candles_saved'] = count
                        return stats

            # 计算最优时间周期
            timeframe, expected_candles, aggregate = self.calculate_optimal_timeframe(created_at)
            stats['timeframe'] = f"{aggregate}{timeframe[0]}"
            stats['aggregate'] = aggregate

            logger.info(f"{symbol}: 收集 {timeframe} K线 (agg={aggregate}, expect≈{expected_candles})")

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
                stats['error'] = "No data returned"
                return stats

            # 保存到数据库
            saved_count = await self._save_ohlcv(
                token_id=token_data['token_id'],
                pair_address=pair_address,
                symbol=symbol,
                timeframe=stats['timeframe'],
                ohlcv_data=ohlcv_data
            )

            stats['candles_saved'] = saved_count
            stats['success'] = True

            logger.info(f"{symbol}: ✓ 保存 {saved_count} 根K线")

        except Exception as e:
            logger.error(f"{symbol}: 收集失败 - {e}")
            stats['error'] = str(e)

        return stats

    async def _save_ohlcv(
        self,
        token_id: str,
        pair_address: str,
        symbol: str,
        timeframe: str,
        ohlcv_data: list
    ) -> int:
        """
        保存K线数据到数据库

        Args:
            token_id: 代币ID（来自dexscreener_tokens表）
            pair_address: 交易对地址
            symbol: 代币符号
            timeframe: 时间周期
            ohlcv_data: K线数据

        Returns:
            保存的K线数量
        """
        if not ohlcv_data:
            return 0

        async with self.db.get_session() as session:
            saved_count = 0

            for candle in ohlcv_data:
                timestamp_unix, open_price, high, low, close, volume = candle
                timestamp = datetime.utcfromtimestamp(timestamp_unix)

                # 检查是否已存在
                result = await session.execute(
                    text("""
                        SELECT id FROM token_ohlcv
                        WHERE pool_address = :pool_address
                        AND timeframe = :timeframe
                        AND timestamp = :timestamp
                    """),
                    {
                        "pool_address": pair_address,
                        "timeframe": timeframe,
                        "timestamp": timestamp
                    }
                )

                if result.scalar():
                    continue

                # 插入新K线
                await session.execute(
                    text("""
                        INSERT INTO token_ohlcv (
                            id, token_id, pool_address, timeframe, timestamp,
                            open, high, low, close, volume
                        ) VALUES (
                            :id, :token_id, :pool_address, :timeframe, :timestamp,
                            :open, :high, :low, :close, :volume
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "token_id": token_id,
                        "pool_address": pair_address,
                        "timeframe": timeframe,
                        "timestamp": timestamp,
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "close": close,
                        "volume": volume
                    }
                )
                saved_count += 1

            await session.commit()

            return saved_count


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='直接从DexScreener代币收集K线数据')
    parser.add_argument('--limit', type=int, help='限制收集的代币数量')
    parser.add_argument('--min-liquidity', type=float, help='最小流动性（USD）')
    parser.add_argument('--no-skip-existing', action='store_true', help='不跳过已有K线数据的代币')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("直接从DexScreener代币收集K线数据")
    logger.info("=" * 80)

    collector = DirectDexScreenerOHLCVCollector()
    await collector.init_db()

    try:
        # 查询DexScreener代币
        async with collector.db.get_session() as session:
            query = """
                SELECT
                    id,
                    base_token_symbol,
                    base_token_name,
                    pair_address,
                    pair_created_at,
                    liquidity_usd,
                    volume_h24,
                    dex_id,
                    base_token_address
                FROM dexscreener_tokens
                WHERE 1=1
            """

            params = {}

            if args.min_liquidity:
                query += " AND liquidity_usd >= :min_liquidity"
                params["min_liquidity"] = args.min_liquidity

            query += " ORDER BY liquidity_usd DESC NULLS LAST"

            if args.limit:
                query += " LIMIT :limit"
                params["limit"] = args.limit

            result = await session.execute(text(query), params)
            tokens = result.fetchall()

            if not tokens:
                logger.warning("未找到DexScreener代币")
                return

            logger.info(f"找到 {len(tokens)} 个DexScreener代币")

        # 收集统计
        success_count = 0
        error_count = 0
        skipped_count = 0
        total_candles = 0

        # 收集K线
        for i, token_row in enumerate(tokens, 1):
            token_id = token_row[0]
            symbol = token_row[1]
            name = token_row[2]
            pair_address = token_row[3]
            pair_created_at_unix = token_row[4]
            liquidity_usd = token_row[5]
            volume_h24 = token_row[6]
            dex_id = token_row[7]
            base_token_address = token_row[8]

            # 转换Unix时间戳为datetime
            pair_created_at = None
            if pair_created_at_unix:
                pair_created_at = datetime.utcfromtimestamp(pair_created_at_unix / 1000)

            token_data = {
                'token_id': token_id,
                'symbol': symbol,
                'name': name,
                'pair_address': pair_address,
                'pair_created_at': pair_created_at,
                'liquidity_usd': liquidity_usd,
                'volume_h24': volume_h24,
                'dex_id': dex_id,
                'base_token_address': base_token_address
            }

            logger.info(f"\n[{i}/{len(tokens)}] 处理: {symbol} ({name})")
            logger.info(f"  - Pair: {pair_address}")
            logger.info(f"  - DEX: {dex_id}")
            logger.info(f"  - 流动性: ${liquidity_usd:,.2f}" if liquidity_usd else "  - 流动性: N/A")

            # 收集K线
            stats = await collector.collect_for_token(
                token_data,
                skip_existing=not args.no_skip_existing
            )

            if stats['success']:
                logger.info(f"  ✓ 成功收集 {stats['candles_saved']} 根K线")
                logger.info(f"    - 时间周期: {stats['timeframe']}")
                success_count += 1
                total_candles += stats['candles_saved']
            elif stats['skipped']:
                logger.info(f"  ⊙ 跳过（已有 {stats['candles_saved']} 根K线）")
                skipped_count += 1
            else:
                logger.warning(f"  ✗ 收集失败: {stats.get('error', 'Unknown error')}")
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
        logger.info(f"总K线数: {total_candles}")
        logger.info(f"总计: {len(tokens)}")
        logger.info("=" * 80)

    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
