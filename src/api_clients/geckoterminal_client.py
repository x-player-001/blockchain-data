"""GeckoTerminal API client."""
from typing import Optional, List, Dict, Any

from .base_client import BaseAPIClient
from ..utils.config import config
from ..utils.logger import setup_logger
from ..utils.helpers import safe_get

logger = setup_logger(__name__)


class GeckoTerminalClient(BaseAPIClient):
    """Client for GeckoTerminal API."""

    def __init__(self):
        """Initialize GeckoTerminal client."""
        super().__init__(
            base_url=config.GECKOTERMINAL_BASE_URL,
            rate_limit=config.GECKOTERMINAL_RATE_LIMIT
        )

    async def health_check(self) -> bool:
        """Check if API is accessible."""
        try:
            data = await self.get("/networks/bsc/trending_pools")
            return data is not None
        except Exception as e:
            logger.error(f"GeckoTerminal health check failed: {e}")
            return False

    async def get_token_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Get token data by address.

        Args:
            token_address: Token contract address

        Returns:
            Token data dictionary or None
        """
        endpoint = f"/networks/bsc/tokens/{token_address}"
        data = await self.get(endpoint)

        if not data or "data" not in data:
            logger.warning(f"No data found for token {token_address}")
            return None

        token_data = data["data"]
        attributes = token_data.get("attributes", {})

        # Parse total supply
        total_supply = attributes.get("total_supply")
        if total_supply:
            try:
                total_supply = int(float(total_supply))
            except (ValueError, TypeError):
                total_supply = None

        token_info = {
            "address": token_address.lower(),
            "name": attributes.get("name", "Unknown"),
            "symbol": attributes.get("symbol", "Unknown"),
            "decimals": int(attributes.get("decimals", 18)),
            "total_supply": total_supply,
            "price_usd": float(attributes.get("price_usd", 0)),
            "market_cap": float(safe_get(attributes, "market_cap_usd", default=0)),
            "liquidity_usd": float(safe_get(attributes, "total_reserve_in_usd", default=0)),
            "volume_24h": float(safe_get(attributes, "volume_usd", "h24", default=0)),
        }

        logger.debug(f"Fetched data for {token_info['symbol']} from GeckoTerminal")
        return token_info

    async def get_trending_pools(self, page: int = 1) -> List[Dict[str, Any]]:
        """
        Get trending pools on BSC with token details.

        Args:
            page: Page number

        Returns:
            List of pool data dictionaries with token metadata
        """
        endpoint = f"/networks/bsc/trending_pools?page={page}"
        data = await self.get(endpoint)

        if not data or "data" not in data:
            logger.warning("No trending pools data found")
            return []

        pools = []
        for pool in data["data"]:
            attributes = pool.get("attributes", {})
            relationships = pool.get("relationships", {})

            # Get base token info
            base_token = safe_get(relationships, "base_token", "data")
            if not base_token:
                continue

            token_address = base_token.get("id", "").split("_")[-1] if base_token.get("id") else None
            if not token_address:
                continue

            # Fetch token details to get name, symbol, decimals, total_supply
            token_details = await self.get_token_data(token_address)
            if not token_details:
                logger.warning(f"Could not fetch token details for {token_address}")
                continue

            # Combine pool data with token metadata
            pool_info = {
                "address": token_address.lower(),
                "name": token_details.get("name", "Unknown"),
                "symbol": token_details.get("symbol", "Unknown"),
                "decimals": token_details.get("decimals", 18),
                "total_supply": token_details.get("total_supply"),
                "pool_address": pool.get("id", "").split("_")[-1],
                "pool_created_at": attributes.get("pool_created_at"),  # ISO 8601 format
                "price_usd": float(safe_get(attributes, "base_token_price_usd", default=0)),
                "liquidity_usd": float(safe_get(attributes, "reserve_in_usd", default=0)),
                "volume_24h": float(safe_get(attributes, "volume_usd", "h24", default=0)),
                "price_change_24h": float(safe_get(attributes, "price_change_percentage", "h24", default=0)),
                "dex_name": attributes.get("dex_id", "Unknown"),
            }

            pools.append(pool_info)

        logger.info(f"Found {len(pools)} trending pools")
        return pools

    async def get_new_pools(self, page: int = 1) -> List[Dict[str, Any]]:
        """
        Get new pools on BSC with token details.

        Args:
            page: Page number

        Returns:
            List of pool data dictionaries with token metadata
        """
        endpoint = f"/networks/bsc/new_pools?page={page}"
        data = await self.get(endpoint)

        if not data or "data" not in data:
            logger.warning("No new pools data found")
            return []

        pools = []
        for pool in data["data"]:
            attributes = pool.get("attributes", {})
            relationships = pool.get("relationships", {})

            # Get base token info
            base_token = safe_get(relationships, "base_token", "data")
            if not base_token:
                continue

            token_address = base_token.get("id", "").split("_")[-1] if base_token.get("id") else None
            if not token_address:
                continue

            # Fetch token details to get name, symbol, decimals, total_supply
            token_details = await self.get_token_data(token_address)
            if not token_details:
                logger.warning(f"Could not fetch token details for {token_address}")
                continue

            # Combine pool data with token metadata
            pool_info = {
                "address": token_address.lower(),
                "name": token_details.get("name", "Unknown"),
                "symbol": token_details.get("symbol", "Unknown"),
                "decimals": token_details.get("decimals", 18),
                "total_supply": token_details.get("total_supply"),
                "pool_address": pool.get("id", "").split("_")[-1],
                "price_usd": float(safe_get(attributes, "base_token_price_usd", default=0)),
                "liquidity_usd": float(safe_get(attributes, "reserve_in_usd", default=0)),
                "volume_24h": float(safe_get(attributes, "volume_usd", "h24", default=0)),
                "dex_name": attributes.get("dex_id", "Unknown"),
            }

            pools.append(pool_info)

        logger.info(f"Found {len(pools)} new pools")
        return pools

    async def get_top_pools(self, page: int = 1, sort: str = "h24_volume_usd_desc") -> List[Dict[str, Any]]:
        """
        Get top pools on BSC with token details.

        Args:
            page: Page number
            sort: Sort order (h24_volume_usd_desc, h24_tx_count_desc, etc.)

        Returns:
            List of pool data dictionaries with token metadata
        """
        endpoint = f"/networks/bsc/pools?page={page}&sort={sort}"
        data = await self.get(endpoint)

        if not data or "data" not in data:
            logger.warning("No pools data found")
            return []

        pools = []
        for pool in data["data"]:
            attributes = pool.get("attributes", {})
            relationships = pool.get("relationships", {})

            # Get base token info
            base_token = safe_get(relationships, "base_token", "data")
            if not base_token:
                continue

            token_address = base_token.get("id", "").split("_")[-1] if base_token.get("id") else None
            if not token_address:
                continue

            # Fetch token details to get name, symbol, decimals, total_supply
            token_details = await self.get_token_data(token_address)
            if not token_details:
                logger.warning(f"Could not fetch token details for {token_address}")
                continue

            # Calculate market cap from FDV if available
            fdv = float(safe_get(attributes, "fdv_usd", default=0))
            market_cap = float(safe_get(attributes, "market_cap_usd", default=fdv))

            # Combine pool data with token metadata
            pool_info = {
                "address": token_address.lower(),
                "name": token_details.get("name", "Unknown"),
                "symbol": token_details.get("symbol", "Unknown"),
                "decimals": token_details.get("decimals", 18),
                "total_supply": token_details.get("total_supply"),
                "pool_address": pool.get("id", "").split("_")[-1],
                "pool_created_at": attributes.get("pool_created_at"),  # ISO 8601 format
                "price_usd": float(safe_get(attributes, "base_token_price_usd", default=0)),
                "market_cap": market_cap,
                "liquidity_usd": float(safe_get(attributes, "reserve_in_usd", default=0)),
                "volume_24h": float(safe_get(attributes, "volume_usd", "h24", default=0)),
                "price_change_24h": float(safe_get(attributes, "price_change_percentage", "h24", default=0)),
                "dex_name": attributes.get("dex_id", "Unknown"),
            }

            pools.append(pool_info)

        logger.info(f"Found {len(pools)} pools")
        return pools

    async def get_ohlcv(
        self,
        pool_address: str,
        timeframe: str = "day",
        aggregate: int = 1,
        before_timestamp: Optional[int] = None,
        network: str = "bsc"
    ) -> List[List[float]]:
        """
        Get OHLCV (candlestick) data for a pool.

        Args:
            pool_address: Pool contract address
            timeframe: Time period (minute, hour, day)
            aggregate: Aggregation level (1, 5, 15 for minute; 1, 4, 12 for hour; 1 for day)
            before_timestamp: Get data before this Unix timestamp
            network: Network name (bsc, solana, eth, etc.)

        Returns:
            List of OHLCV data: [[timestamp, open, high, low, close, volume], ...]
        """
        # GeckoTerminal uses 'solana' for Solana, 'bsc' for BSC, etc.
        endpoint = f"/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}"

        params = []
        if aggregate > 1:
            params.append(f"aggregate={aggregate}")
        if before_timestamp:
            params.append(f"before_timestamp={before_timestamp}")

        if params:
            endpoint += "?" + "&".join(params)

        data = await self.get(endpoint)

        if not data or "data" not in data:
            logger.warning(f"No OHLCV data found for pool {pool_address}")
            return []

        ohlcv_list = data["data"].get("attributes", {}).get("ohlcv_list", [])
        logger.debug(f"Fetched {len(ohlcv_list)} candles for pool {pool_address} ({timeframe})")
        return ohlcv_list

    async def get_ohlcv_historical(
        self,
        pool_address: str,
        timeframe: str = "day",
        max_candles: int = 1000,
        aggregate: int = 1,
        network: str = "bsc"
    ) -> List[List[float]]:
        """
        Get historical OHLCV data by paginating through before_timestamp.

        Args:
            pool_address: Pool contract address
            timeframe: Time period (minute, hour, day)
            max_candles: Maximum number of candles to fetch (default: 1000)
            aggregate: Aggregation level (1, 5, 15 for minute; 1, 4, 12 for hour; 1 for day)
            network: Network name (bsc, solana, eth, etc.)

        Returns:
            List of OHLCV data: [[timestamp, open, high, low, close, volume], ...]
        """
        all_candles = []
        before_timestamp = None
        fetch_count = 0
        max_iterations = (max_candles // 100) + 1

        logger.info(f"Fetching up to {max_candles} historical candles for {pool_address} on {network} ({timeframe}, agg={aggregate})")

        while fetch_count < max_iterations:
            # Fetch batch
            candles = await self.get_ohlcv(
                pool_address=pool_address,
                timeframe=timeframe,
                aggregate=aggregate,
                before_timestamp=before_timestamp,
                network=network
            )

            if not candles:
                logger.info(f"No more data available. Total fetched: {len(all_candles)} candles")
                break

            all_candles.extend(candles)
            fetch_count += 1

            # Check if we've reached the limit
            if len(all_candles) >= max_candles:
                all_candles = all_candles[:max_candles]
                logger.info(f"Reached max_candles limit: {max_candles}")
                break

            # Get the oldest timestamp for next iteration
            oldest_timestamp = candles[-1][0]

            # If we got less than 100 candles, we've reached the end
            if len(candles) < 100:
                logger.info(f"Reached end of available data. Total: {len(all_candles)} candles")
                break

            # Set before_timestamp for next batch
            before_timestamp = oldest_timestamp
            logger.debug(f"Fetched batch {fetch_count}: {len(candles)} candles, total: {len(all_candles)}")

        logger.info(f"Completed fetching {len(all_candles)} candles for {pool_address}")
        return all_candles
