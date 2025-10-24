"""AVE OHLCV collector with true incremental updates using from_time/to_time."""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, text

from ..api_clients.ave_client import AveClient
from ..storage.db_manager import db_manager
from ..storage.models import Token, TokenPair
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class AveOHLCVCollector:
    """Collect OHLCV data using AVE API with true incremental updates."""

    # AVE interval mapping (in minutes)
    INTERVAL_MAPPING = {
        '1m': 1,
        '5m': 5,
        '15m': 15,
        '30m': 30,
        '1h': 60,
        '2h': 120,
        '4h': 240,
        '1d': 1440,
        '3d': 4320,
        '1w': 10080,
        '1M': 43200,
        '1y': 525600
    }

    def __init__(self):
        """Initialize AVE OHLCV collector."""
        self.client = AveClient()

    async def collect_for_token(
        self,
        token_id: str,
        token_symbol: str,
        pair_address: str,
        interval: int = 1440,
        limit: int = 1000,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Collect OHLCV data for a single token using AVE API.

        Args:
            token_id: Token ID
            token_symbol: Token symbol (for logging)
            pair_address: Trading pair address
            interval: Time interval in minutes (1, 5, 15, 30, 60, 120, 240, 1440...)
            limit: Maximum number of candles to fetch
            skip_existing: Enable incremental update mode

        Returns:
            Collection statistics
        """
        stats = {
            'token_id': token_id,
            'symbol': token_symbol,
            'pair_address': pair_address,
            'interval': interval,
            'expected_candles': 0,
            'actual_candles': 0,
            'skipped': False,
            'success': False,
            'error': None
        }

        try:
            # Format pair_id with -bsc suffix for AVE API
            pair_id = f"{pair_address}-bsc"

            # Check existing data for incremental update
            latest_candle_time = None
            existing_count = 0
            from_time = None
            to_time = int(datetime.utcnow().timestamp())

            if skip_existing:
                latest_candle_time = await self._get_latest_candle_time(token_id, pair_address)
                existing_count = await self._get_existing_candle_count(token_id, pair_address)

                if latest_candle_time:
                    logger.info(f"{token_symbol}: Has {existing_count} candles, latest: {latest_candle_time}")
                    # Use latest candle time as start point (true incremental update!)
                    from_time = int(latest_candle_time.timestamp())

                    # Calculate time gap
                    time_gap_seconds = to_time - from_time
                    time_gap_minutes = time_gap_seconds / 60

                    # If gap is smaller than interval, skip
                    if time_gap_minutes < interval:
                        logger.info(f"{token_symbol}: Data is up-to-date (gap: {time_gap_minutes:.1f}min < interval: {interval}min), skipping")
                        stats['skipped'] = True
                        stats['actual_candles'] = existing_count
                        return stats

            # Log collection mode
            if from_time:
                from_dt = datetime.utcfromtimestamp(from_time)
                to_dt = datetime.utcfromtimestamp(to_time)
                logger.info(f"{token_symbol}: Incremental update from {from_dt} to {to_dt} (interval={interval}min)")
            else:
                logger.info(f"{token_symbol}: Initial collection (interval={interval}min, limit={limit})")

            # Fetch OHLCV data from AVE API
            ohlcv_data = await self.client.get_pair_klines(
                pair_id=pair_id,
                interval=interval,
                limit=limit,
                from_time=from_time,
                to_time=to_time
            )

            if not ohlcv_data:
                logger.warning(f"{token_symbol}: No OHLCV data returned from AVE API")
                stats['error'] = "No data from API"
                return stats

            # Convert AVE format to our storage format
            converted_data = self._convert_ave_format(ohlcv_data)

            if not converted_data:
                logger.info(f"{token_symbol}: No new candles after conversion")
                stats['skipped'] = True
                stats['actual_candles'] = existing_count
                return stats

            # Save to database
            timeframe = self._interval_to_timeframe(interval)
            saved_count = await self._save_ohlcv(
                token_id=token_id,
                pool_address=pair_address,
                timeframe=timeframe,
                ohlcv_data=converted_data
            )

            stats['actual_candles'] = saved_count
            stats['success'] = True

            logger.info(f"{token_symbol}: ✓ Saved {saved_count} candles (interval={interval}min)")

        except Exception as e:
            logger.error(f"{token_symbol}: Error collecting OHLCV - {e}")
            stats['error'] = str(e)

        return stats

    async def collect_all(
        self,
        interval: int = 1440,
        limit: int = 1000,
        skip_existing: bool = True,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Collect OHLCV data for all tokens using AVE API.

        Args:
            interval: Time interval in minutes
            limit: Maximum candles per token
            skip_existing: Enable incremental update
            max_tokens: Maximum number of tokens to process

        Returns:
            Overall collection statistics
        """
        logger.info("=" * 80)
        logger.info("Starting AVE OHLCV collection")
        logger.info(f"Interval: {interval} minutes ({self._interval_to_timeframe(interval)})")
        logger.info(f"Max candles per token: {limit}")
        logger.info(f"Incremental update: {skip_existing}")
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

        async with self.client:
            # Get tokens with pair addresses
            async with db_manager.get_session() as session:
                query = text("""
                    SELECT
                        t.id,
                        t.symbol,
                        t.name,
                        tp.pair_address,
                        tp.pair_created_at
                    FROM tokens t
                    JOIN token_pairs tp ON t.id = tp.token_id
                    WHERE tp.pair_address IS NOT NULL
                    ORDER BY tp.pair_created_at DESC NULLS LAST
                """)

                if max_tokens:
                    query = text(str(query) + f" LIMIT {max_tokens}")

                result = await session.execute(query)
                tokens = result.fetchall()

            if not tokens:
                logger.warning("No tokens with pair addresses found")
                return overall_stats

            overall_stats['total_tokens'] = len(tokens)
            logger.info(f"Found {len(tokens)} tokens to process\n")

            # Process each token
            for i, token_row in enumerate(tokens, 1):
                token_id = token_row.id
                symbol = token_row.symbol
                pair_address = token_row.pair_address

                logger.info(f"[{i}/{len(tokens)}] Processing {symbol}...")

                # Collect OHLCV
                stats = await self.collect_for_token(
                    token_id=token_id,
                    token_symbol=symbol,
                    pair_address=pair_address,
                    interval=interval,
                    limit=limit,
                    skip_existing=skip_existing
                )

                overall_stats['tokens'].append(stats)

                if stats['skipped']:
                    overall_stats['skipped'] += 1
                elif stats['success']:
                    overall_stats['successful'] += 1
                    overall_stats['total_candles'] += stats['actual_candles']
                else:
                    overall_stats['failed'] += 1

                # Rate limiting (60 req/min = 1 sec/req)
                await asyncio.sleep(1)

        overall_stats['end_time'] = datetime.now()
        overall_stats['duration'] = (overall_stats['end_time'] - overall_stats['start_time']).total_seconds()

        # Print summary
        self._print_summary(overall_stats)

        return overall_stats

    async def _get_existing_candle_count(
        self,
        token_id: str,
        pool_address: str
    ) -> int:
        """Get count of existing candles for a token."""
        async with db_manager.get_session() as session:
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

    async def _get_latest_candle_time(
        self,
        token_id: str,
        pool_address: str
    ) -> Optional[datetime]:
        """Get timestamp of the latest candle for a token."""
        async with db_manager.get_session() as session:
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

    def _convert_ave_format(self, ave_data: List[List[Any]]) -> List[List[float]]:
        """
        Convert AVE API format to our storage format.

        AVE format (dict): {"open": "110652.17", "high": "111989.54", ...}
        Our format (list): [timestamp, open, high, low, close, volume]

        Args:
            ave_data: AVE API response data (list of dicts)

        Returns:
            Converted data in our format
        """
        converted = []

        # AVE returns dict format in data.points
        for point in ave_data:
            try:
                timestamp = int(point['time'])
                open_price = float(point['open'])
                high = float(point['high'])
                low = float(point['low'])
                close = float(point['close'])
                volume = float(point['volume'])

                converted.append([timestamp, open_price, high, low, close, volume])
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Failed to convert AVE data point: {e}")
                continue

        return converted

    def _interval_to_timeframe(self, interval: int) -> str:
        """
        Convert interval (minutes) to timeframe string.

        Args:
            interval: Interval in minutes

        Returns:
            Timeframe string (e.g., "1d", "4h", "15m")
        """
        if interval >= 1440:
            if interval == 1440:
                return "1d"
            elif interval == 4320:
                return "3d"
            elif interval == 10080:
                return "1w"
            else:
                days = interval // 1440
                return f"{days}d"
        elif interval >= 60:
            hours = interval // 60
            return f"{hours}h"
        else:
            return f"{interval}m"

    async def _save_ohlcv(
        self,
        token_id: str,
        pool_address: str,
        timeframe: str,
        ohlcv_data: List[List[float]]
    ) -> int:
        """
        Save OHLCV data to database.

        Args:
            token_id: Token ID
            pool_address: Pool address
            timeframe: Timeframe string (e.g., "1d", "4h", "15m")
            ohlcv_data: List of [timestamp, open, high, low, close, volume]

        Returns:
            Number of candles saved
        """
        if ohlcv_data:
            saved = await db_manager.batch_insert_ohlcv(token_id, pool_address, timeframe, ohlcv_data)
            return saved

        return 0

    def _print_summary(self, stats: Dict[str, Any]) -> None:
        """Print collection summary."""
        logger.info("\n" + "=" * 80)
        logger.info("AVE OHLCV COLLECTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total tokens:     {stats['total_tokens']:>6}")
        logger.info(f"Successful:       {stats['successful']:>6}")
        logger.info(f"Skipped:          {stats['skipped']:>6}")
        logger.info(f"Failed:           {stats['failed']:>6}")
        logger.info(f"Total candles:    {stats['total_candles']:>6}")
        logger.info(f"Duration:         {stats['duration']:.1f}s")
        logger.info("=" * 80)
