"""DexScreener API client."""
from typing import Optional, List, Dict, Any

from .base_client import BaseAPIClient
from ..utils.config import config
from ..utils.logger import setup_logger
from ..utils.helpers import safe_get

logger = setup_logger(__name__)


class DexScreenerClient(BaseAPIClient):
    """Client for DexScreener API."""

    def __init__(self):
        """Initialize DexScreener client."""
        super().__init__(
            base_url=config.DEXSCREENER_BASE_URL,
            rate_limit=config.DEXSCREENER_RATE_LIMIT
        )

    async def health_check(self) -> bool:
        """Check if API is accessible."""
        try:
            # Try a simple request
            data = await self.get("/search?q=BNB")
            return data is not None
        except Exception as e:
            logger.error(f"DexScreener health check failed: {e}")
            return False

    async def get_token_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Get token data by address.

        Args:
            token_address: Token contract address

        Returns:
            Token data dictionary or None
        """
        endpoint = f"/tokens/{token_address}"
        data = await self.get(endpoint)

        if not data or "pairs" not in data:
            logger.warning(f"No data found for token {token_address}")
            return None

        # Get the best pair (highest liquidity)
        pairs = data.get("pairs", [])
        if not pairs:
            return None

        # Filter BSC pairs only
        bsc_pairs = [p for p in pairs if p.get("chainId") == "bsc"]
        if not bsc_pairs:
            return None

        # Sort by liquidity
        bsc_pairs.sort(
            key=lambda x: float(safe_get(x, "liquidity", "usd", default=0)),
            reverse=True
        )

        best_pair = bsc_pairs[0]

        # Extract token info
        token_info = {
            "address": token_address.lower(),
            "name": safe_get(best_pair, "baseToken", "name", default="Unknown"),
            "symbol": safe_get(best_pair, "baseToken", "symbol", default="Unknown"),
            "decimals": 18,  # DexScreener doesn't provide decimals, default to 18
            "total_supply": None,  # DexScreener doesn't provide total supply
            "price_usd": float(safe_get(best_pair, "priceUsd", default=0)),
            "market_cap": float(safe_get(best_pair, "fdv", default=0)),  # FDV as market cap
            "liquidity_usd": float(safe_get(best_pair, "liquidity", "usd", default=0)),
            "volume_24h": float(safe_get(best_pair, "volume", "h24", default=0)),
            "price_change_24h": float(safe_get(best_pair, "priceChange", "h24", default=0)),
            "dex_name": safe_get(best_pair, "dexId", default="Unknown"),
            "pair_address": safe_get(best_pair, "pairAddress", default=""),
            "pair_created_at": best_pair.get("pairCreatedAt"),  # Unix timestamp in milliseconds
        }

        logger.debug(f"Fetched data for {token_info['symbol']} from DexScreener")
        return token_info

    async def _get_root_endpoint(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Get data from a root-level endpoint (not under /latest/dex).

        Args:
            endpoint: The endpoint path (e.g., "/token-profiles/latest/v1")

        Returns:
            Response data or None
        """
        # Temporarily override base_url for root-level endpoints
        original_base_url = self.base_url
        try:
            self.base_url = "https://api.dexscreener.com"
            return await self.get(endpoint)
        finally:
            self.base_url = original_base_url

    async def search_tokens(
        self,
        chain: str = "bsc",
        min_liquidity: float = 0,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Search for latest tokens on a chain using token profiles.

        Args:
            chain: Blockchain name (default: "bsc")
            min_liquidity: Minimum liquidity in USD
            limit: Maximum number of tokens to return (default: 30)

        Returns:
            List of token data dictionaries
        """
        # Step 1: Get latest token profiles
        profiles_endpoint = "/token-profiles/latest/v1"
        profiles_data = await self._get_root_endpoint(profiles_endpoint)

        if not profiles_data:
            logger.warning("No token profiles found")
            return []

        # Filter by chain
        chain_profiles = [p for p in profiles_data if p.get("chainId") == chain]
        logger.info(f"Found {len(chain_profiles)} {chain} token profiles")

        if not chain_profiles:
            return []

        # Step 2: Get trading data for these tokens (batch up to 30 addresses)
        token_addresses = [p["tokenAddress"] for p in chain_profiles[:limit]]

        # DexScreener supports comma-separated addresses
        batch_size = 30
        tokens = []

        for i in range(0, len(token_addresses), batch_size):
            batch = token_addresses[i:i + batch_size]
            addresses_str = ",".join(batch)

            # Use the normal /latest/dex prefix for token data
            endpoint = f"/tokens/{addresses_str}"
            data = await self.get(endpoint)

            if not data or "pairs" not in data:
                continue

            # Process pairs and group by token address
            token_pairs = {}
            for pair in data.get("pairs", []):
                if pair.get("chainId") != chain:
                    continue

                token_address = safe_get(pair, "baseToken", "address")
                if not token_address:
                    continue

                token_address = token_address.lower()

                # Keep only the best pair (highest liquidity) per token
                liquidity = float(safe_get(pair, "liquidity", "usd", default=0))

                if token_address not in token_pairs or liquidity > token_pairs[token_address].get("liquidity_usd", 0):
                    token_pairs[token_address] = {
                        "address": token_address,
                        "name": safe_get(pair, "baseToken", "name", default="Unknown"),
                        "symbol": safe_get(pair, "baseToken", "symbol", default="Unknown"),
                        "decimals": 18,  # DexScreener doesn't provide decimals
                        "total_supply": None,
                        "price_usd": float(safe_get(pair, "priceUsd", default=0)),
                        "market_cap": float(safe_get(pair, "fdv", default=0)),
                        "liquidity_usd": liquidity,
                        "volume_24h": float(safe_get(pair, "volume", "h24", default=0)),
                        "price_change_24h": float(safe_get(pair, "priceChange", "h24", default=0)),
                        "dex_name": safe_get(pair, "dexId", default="Unknown"),
                        "pair_address": safe_get(pair, "pairAddress", default=""),
                        "pair_created_at": pair.get("pairCreatedAt"),
                    }

            # Filter by liquidity
            for token_info in token_pairs.values():
                if token_info["liquidity_usd"] >= min_liquidity:
                    tokens.append(token_info)

        logger.info(f"Found {len(tokens)} tokens on {chain} with liquidity >= ${min_liquidity:,.0f}")
        return tokens

    async def get_trending_tokens(self, min_liquidity: float = 10000) -> List[Dict[str, Any]]:
        """
        Get trending tokens from latest token profiles.

        Args:
            min_liquidity: Minimum liquidity in USD (default: 10000)

        Returns:
            List of trending token data
        """
        # Use the latest token profiles and filter by liquidity
        return await self.search_tokens(chain="bsc", min_liquidity=min_liquidity)
