"""AVE API data collector."""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..api_clients.ave_client import AveClient
from ..storage.db_manager import db_manager
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class AveCollector:
    """Collects blockchain data from AVE API."""

    def __init__(self):
        """Initialize AVE collector."""
        self.client = AveClient()

    async def collect_tokens(
        self,
        chain: str = "bsc",
        min_market_cap: float = 1000000,
        limit: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Collect tokens with minimum market cap.

        Args:
            chain: Blockchain name
            min_market_cap: Minimum market cap in USD
            limit: Maximum number of tokens

        Returns:
            List of collected token data
        """
        logger.info(f"Collecting tokens from AVE API (chain={chain}, min_mc=${min_market_cap:,.0f})")

        async with self.client:
            # Filter tokens by market cap
            tokens = await self.client.filter_tokens_by_market_cap(
                chain=chain,
                min_market_cap=min_market_cap,
                limit=limit
            )

            if not tokens:
                logger.warning("No tokens found from AVE API")
                return []

            logger.info(f"Found {len(tokens)} tokens from AVE API")

            # Save tokens to database
            saved_count = 0
            for token_data in tokens:
                try:
                    # Extract token information
                    token_info = self._parse_token_data(token_data, source="ave")

                    if not token_info:
                        continue

                    # Save token to database
                    token = await db_manager.upsert_token(
                        address=token_info["address"],
                        name=token_info["name"],
                        symbol=token_info["symbol"],
                        decimals=token_info["decimals"],
                        total_supply=int(token_info["total_supply"]) if token_info.get("total_supply") else None
                    )

                    # Update data_source field
                    async with db_manager.get_session() as session:
                        token.data_source = token_info["data_source"]
                        session.add(token)
                        await session.flush()

                    # Save market metrics data
                    if token_info.get("price_usd") or token_info.get("market_cap"):
                        await db_manager.add_token_metrics(
                            token_id=token.id,
                            price_usd=token_info.get("price_usd"),
                            market_cap=token_info.get("market_cap"),
                            liquidity_usd=token_info.get("liquidity_usd"),
                            volume_24h=token_info.get("volume_24h"),
                            price_change_24h=token_info.get("price_change_24h"),
                            holders_count=token_info.get("holders_count"),
                            source="ave"
                        )

                    # Save main trading pair if available
                    if token_info.get("main_pair"):
                        # Convert Unix timestamp to datetime
                        from datetime import datetime
                        pair_created_at = None
                        if token_info.get("launch_at"):
                            pair_created_at = datetime.utcfromtimestamp(token_info["launch_at"])

                        await db_manager.upsert_token_pair(
                            token_id=token.id,
                            dex_name="pancakeswap",  # AVE data usually from PancakeSwap
                            pair_address=token_info["main_pair"],
                            base_token="WBNB",
                            liquidity_usd=token_info.get("liquidity_usd"),
                            volume_24h=token_info.get("volume_24h"),
                            pair_created_at=pair_created_at
                        )

                    saved_count += 1

                except Exception as e:
                    logger.error(f"Error saving token {token_data.get('address')}: {e}")
                    continue

            logger.info(f"Successfully saved {saved_count}/{len(tokens)} tokens to database")
            return tokens

    async def collect_token_ohlcv(
        self,
        token_address: str,
        token_id: str,
        interval: int = 1440,  # Daily
        limit: int = 1000
    ) -> int:
        """
        Collect OHLCV data for a specific token.

        Args:
            token_address: Token contract address
            token_id: Token ID in database
            interval: Time interval in minutes (1440 = 1 day)
            limit: Number of candles to fetch

        Returns:
            Number of OHLCV records inserted
        """
        logger.info(f"Collecting OHLCV data for {token_address} (interval={interval}min, limit={limit})")

        async with self.client:
            # Get klines data
            klines = await self.client.get_token_klines(
                token_id=token_address,
                interval=interval,
                limit=limit
            )

            if not klines:
                logger.warning(f"No klines data found for {token_address}")
                return 0

            logger.info(f"Fetched {len(klines)} klines for {token_address}")

            # Convert interval to timeframe string
            timeframe = self._interval_to_timeframe(interval)

            # Save to database
            inserted = await db_manager.batch_insert_ohlcv(
                token_id=token_id,
                pool_address=token_address,  # Use token address as pool identifier
                timeframe=timeframe,
                ohlcv_data=klines
            )

            logger.info(f"Inserted {inserted} new OHLCV records for {token_address}")
            return inserted

    async def collect_all_tokens_ohlcv(
        self,
        interval: int = 1440,
        limit_per_token: int = 1000,
        max_tokens: Optional[int] = None
    ) -> Dict[str, int]:
        """
        Collect OHLCV data for all tokens in database.

        Args:
            interval: Time interval in minutes
            limit_per_token: Number of candles per token
            max_tokens: Maximum number of tokens to process

        Returns:
            Dictionary with statistics
        """
        logger.info(f"Collecting OHLCV for all tokens (interval={interval}min)")

        # Get tokens from database
        async with db_manager.get_session() as session:
            from sqlalchemy import select
            from src.storage.models import Token

            query = select(Token).where(Token.data_source == "ave")
            if max_tokens:
                query = query.limit(max_tokens)

            result = await session.execute(query)
            tokens = result.scalars().all()

        if not tokens:
            logger.warning("No AVE tokens found in database")
            return {"total": 0, "success": 0, "failed": 0}

        logger.info(f"Processing {len(tokens)} tokens")

        stats = {"total": len(tokens), "success": 0, "failed": 0, "total_candles": 0}

        for i, token in enumerate(tokens, 1):
            try:
                logger.info(f"[{i}/{len(tokens)}] Processing {token.symbol} ({token.address})")

                inserted = await self.collect_token_ohlcv(
                    token_address=token.address,
                    token_id=token.id,
                    interval=interval,
                    limit=limit_per_token
                )

                stats["success"] += 1
                stats["total_candles"] += inserted

                # Rate limiting - sleep between requests
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error collecting OHLCV for {token.symbol}: {e}")
                stats["failed"] += 1
                continue

        logger.info(
            f"OHLCV collection complete: {stats['success']}/{stats['total']} tokens, "
            f"{stats['total_candles']} total candles"
        )
        return stats

    def _parse_token_data(self, token_data: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
        """
        Parse token data from AVE API response.

        Args:
            token_data: Raw token data from API
            source: Data source identifier

        Returns:
            Parsed token info dict or None
        """
        try:
            # AVE API uses "token" field for address
            address = token_data.get("token") or token_data.get("address") or token_data.get("token_address")
            if not address:
                logger.warning(f"Token has no address: {token_data.get('symbol', 'unknown')}")
                return None

            # Extract fields with multiple possible keys
            name = token_data.get("name") or token_data.get("token_name") or "Unknown"
            symbol = token_data.get("symbol") or token_data.get("token_symbol") or "UNKNOWN"
            decimals = token_data.get("decimal") or token_data.get("decimals") or 18

            # Market data - AVE specific field names
            price_usd = token_data.get("current_price_usd") or token_data.get("price_usd") or token_data.get("price") or 0
            market_cap = token_data.get("market_cap") or token_data.get("marketCap") or token_data.get("mc")
            total_supply = token_data.get("total") or token_data.get("total_supply") or token_data.get("totalSupply")
            volume_24h = token_data.get("tx_volume_u_24h") or token_data.get("volume_24h")

            # Price changes
            price_change_24h = token_data.get("price_change_24h") or token_data.get("priceChange24h")

            # Liquidity
            liquidity_usd = token_data.get("main_pair_tvl") or token_data.get("tvl") or token_data.get("liquidity")

            # Main trading pair address
            main_pair = token_data.get("main_pair") or token_data.get("pair_address")

            # Holders count
            holders_count = token_data.get("holders") or token_data.get("holders_count")

            # Pair launch time (Unix timestamp)
            launch_at = token_data.get("launch_at") or token_data.get("created_at")

            return {
                "address": address.lower(),
                "name": name,
                "symbol": symbol,
                "decimals": int(decimals) if decimals else 18,
                "price_usd": float(price_usd) if price_usd else None,
                "market_cap": float(market_cap) if market_cap else None,
                "total_supply": float(total_supply) if total_supply else None,
                "volume_24h": float(volume_24h) if volume_24h else None,
                "price_change_24h": float(price_change_24h) if price_change_24h else None,
                "liquidity_usd": float(liquidity_usd) if liquidity_usd else None,
                "main_pair": main_pair.lower() if main_pair else None,
                "holders_count": int(holders_count) if holders_count else None,
                "launch_at": int(launch_at) if launch_at else None,
                "data_source": source
            }

        except Exception as e:
            logger.error(f"Error parsing token data: {e}")
            return None

    async def _save_pair(self, token_id: str, pair_data: Dict[str, Any]) -> None:
        """
        Save trading pair to database.

        Args:
            token_id: Token ID
            pair_data: Pair information from API
        """
        try:
            pair_address = pair_data.get("pair_address") or pair_data.get("address")
            if not pair_address:
                return

            await db_manager.upsert_token_pair(
                token_id=token_id,
                pair_address=pair_address,
                dex_name=pair_data.get("dex_name") or pair_data.get("dex") or "unknown",
                base_token=pair_data.get("base_token") or pair_data.get("quote_token"),
                quote_token=pair_data.get("quote_token") or pair_data.get("base_token"),
                liquidity_usd=pair_data.get("tvl") or pair_data.get("liquidity")
            )

        except Exception as e:
            logger.error(f"Error saving pair: {e}")

    def _interval_to_timeframe(self, interval: int) -> str:
        """
        Convert interval in minutes to timeframe string.

        Args:
            interval: Interval in minutes

        Returns:
            Timeframe string (minute, hour, day, etc.)
        """
        if interval < 60:
            return "minute"
        elif interval < 1440:
            return "hour"
        elif interval < 10080:
            return "day"
        elif interval < 43200:
            return "week"
        else:
            return "month"
