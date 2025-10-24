"""DexPaprika API client."""
from typing import Optional, List, Dict, Any
from enum import Enum

from .base_client import BaseAPIClient
from ..utils.config import config
from ..utils.logger import setup_logger
from ..utils.helpers import safe_get

logger = setup_logger(__name__)


class SortOrder(str, Enum):
    """Sorting order options."""
    ASC = "asc"
    DESC = "desc"


class OrderBy(str, Enum):
    """Fields to order pools by."""
    VOLUME_USD = "volume_usd"
    PRICE_USD = "price_usd"
    TRANSACTIONS = "transactions"
    PRICE_CHANGE_24H = "last_price_change_usd_24h"
    CREATED_AT = "created_at"


class DexPaprikaClient(BaseAPIClient):
    """Client for DexPaprika API."""

    def __init__(self):
        """Initialize DexPaprika client."""
        super().__init__(
            base_url=config.DEXPAPRIKA_BASE_URL,
            rate_limit=config.DEXPAPRIKA_RATE_LIMIT
        )

    async def health_check(self) -> bool:
        """Check if API is accessible."""
        try:
            # Try to get networks list
            data = await self.get("/networks")
            return data is not None and len(data) > 0
        except Exception as e:
            logger.error(f"DexPaprika health check failed: {e}")
            return False

    async def get_networks(self) -> List[Dict[str, Any]]:
        """
        Get list of supported networks.

        Returns:
            List of network information
        """
        endpoint = "/networks"
        data = await self.get(endpoint)
        return data if data else []

    async def get_top_pools(
        self,
        network: str = "bsc",
        limit: int = 100,
        page: int = 0,
        order_by: OrderBy = OrderBy.VOLUME_USD,
        sort: SortOrder = SortOrder.DESC
    ) -> List[Dict[str, Any]]:
        """
        Get top liquidity pools on a network.

        Args:
            network: Network slug (default: "bsc")
            limit: Number of pools per page (1-100, default: 100)
            page: Zero-based page index (default: 0)
            order_by: Field to order by (default: volume_usd)
            sort: Sort order (default: desc)

        Returns:
            List of pool data dictionaries
        """
        endpoint = f"/networks/{network}/pools"
        params = {
            "limit": min(limit, 100),  # API max is 100
            "page": page,
            "order_by": order_by.value,
            "sort": sort.value
        }

        data = await self.get(endpoint, params=params)

        if not data or "pools" not in data:
            logger.warning(f"No pools found for network {network}")
            return []

        pools = data.get("pools", [])
        logger.info(f"Fetched {len(pools)} pools from {network} (order_by={order_by.value})")
        return pools

    async def get_tokens_from_pools(
        self,
        network: str = "bsc",
        limit: int = 100,
        order_by: OrderBy = OrderBy.VOLUME_USD,
        min_fdv: float = 0,
        exclude_symbols: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract unique tokens from top pools.

        Args:
            network: Network slug (default: "bsc")
            limit: Number of pools to fetch (default: 100)
            order_by: Field to order by (default: volume_usd)
            min_fdv: Minimum FDV in USD (default: 0)
            exclude_symbols: Token symbols to exclude (default: mainstream coins)

        Returns:
            List of token data dictionaries
        """
        # Default exclusions: mainstream coins
        if exclude_symbols is None:
            exclude_symbols = ['USDT', 'USDC', 'BUSD', 'WBNB', 'BNB', 'DAI', 'ETH', 'WETH']

        # Get pools
        pools = await self.get_top_pools(
            network=network,
            limit=limit,
            order_by=order_by,
            sort=SortOrder.DESC
        )

        # Extract unique tokens
        seen_addresses = set()
        tokens = []

        for pool in pools:
            pool_tokens = pool.get("tokens", [])
            pool_volume = pool.get("volume_usd", 0)
            pool_price = pool.get("price_usd", 0)
            pool_transactions = pool.get("transactions", 0)
            pool_created_at = pool.get("created_at")

            for token in pool_tokens:
                # Skip if excluded symbol
                symbol = token.get("symbol", "")
                if symbol in exclude_symbols:
                    continue

                # Skip if already seen
                address = token.get("id", "")
                if not address or address.lower() in seen_addresses:
                    continue

                # Filter by FDV
                fdv_value = token.get("fdv")
                if fdv_value is None:
                    fdv = 0
                else:
                    fdv = float(fdv_value)

                if fdv < min_fdv:
                    continue

                seen_addresses.add(address.lower())

                # Build token info
                token_info = {
                    "address": address.lower(),
                    "name": token.get("name", "Unknown"),
                    "symbol": symbol,
                    "decimals": token.get("decimals", 18),
                    "total_supply": token.get("total_supply"),
                    "price_usd": pool_price,  # Pool price (might be pair price)
                    "market_cap": fdv,  # Use FDV as market cap
                    "liquidity_usd": 0,  # DexPaprika doesn't provide liquidity directly
                    "volume_24h": pool_volume,
                    "price_change_24h": 0,  # Could calculate from pool data if needed
                    "dex_name": pool.get("dex_name", "Unknown"),
                    "pair_address": pool.get("id", ""),
                    "pair_created_at": pool_created_at,
                    "transactions_24h": pool_transactions,
                }

                tokens.append(token_info)

        logger.info(
            f"Extracted {len(tokens)} unique tokens from {len(pools)} pools "
            f"(order_by={order_by.value}, min_fdv=${min_fdv:,.0f})"
        )
        return tokens

    async def get_tokens_multi_sort(
        self,
        network: str = "bsc",
        limit_per_sort: int = 100,
        min_fdv: float = 0,
        exclude_symbols: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get tokens using multiple sorting strategies and deduplicate.

        This method fetches tokens using:
        1. Top by volume (most liquid/active)
        2. Top by transactions (most popular)

        Args:
            network: Network slug (default: "bsc")
            limit_per_sort: Number of pools per sorting strategy (default: 100)
            min_fdv: Minimum FDV in USD (default: 0)
            exclude_symbols: Token symbols to exclude

        Returns:
            List of unique token data dictionaries
        """
        logger.info(
            f"Fetching tokens from {network} using multiple sorting strategies "
            f"(limit={limit_per_sort}, min_fdv=${min_fdv:,.0f})"
        )

        # Strategy 1: By volume (most liquid)
        tokens_by_volume = await self.get_tokens_from_pools(
            network=network,
            limit=limit_per_sort,
            order_by=OrderBy.VOLUME_USD,
            min_fdv=min_fdv,
            exclude_symbols=exclude_symbols
        )
        logger.info(f"Found {len(tokens_by_volume)} tokens by volume")

        # Strategy 2: By transactions (most active)
        tokens_by_txns = await self.get_tokens_from_pools(
            network=network,
            limit=limit_per_sort,
            order_by=OrderBy.TRANSACTIONS,
            min_fdv=min_fdv,
            exclude_symbols=exclude_symbols
        )
        logger.info(f"Found {len(tokens_by_txns)} tokens by transactions")

        # Merge and deduplicate by address
        seen_addresses = set()
        merged_tokens = []

        for token_list in [tokens_by_volume, tokens_by_txns]:
            for token in token_list:
                address = token["address"]
                if address not in seen_addresses:
                    seen_addresses.add(address)
                    merged_tokens.append(token)

        logger.info(
            f"Merged and deduplicated: {len(merged_tokens)} unique tokens "
            f"(from {len(tokens_by_volume)} + {len(tokens_by_txns)})"
        )

        return merged_tokens

    async def get_pool_details(
        self,
        network: str,
        pool_address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific pool.

        Args:
            network: Network slug
            pool_address: Pool contract address

        Returns:
            Pool data or None
        """
        endpoint = f"/networks/{network}/pools/{pool_address}"
        data = await self.get(endpoint)
        return data

    async def get_token_details(
        self,
        network: str,
        token_address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific token.

        Args:
            network: Network slug
            token_address: Token contract address

        Returns:
            Token data or None
        """
        endpoint = f"/networks/{network}/tokens/{token_address}"
        data = await self.get(endpoint)
        return data
