"""DexScreener API data collector."""
import asyncio
from typing import List, Dict, Any, Optional

from ..api_clients.dexscreener_client import DexScreenerClient
from ..storage.db_manager import db_manager
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class DexScreenerCollector:
    """Collects blockchain data from DexScreener API."""

    def __init__(self):
        """Initialize DexScreener collector."""
        self.client = DexScreenerClient()

    async def collect_tokens(
        self,
        min_liquidity: float = 50000,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Collect tokens from DexScreener.

        Args:
            min_liquidity: Minimum liquidity in USD
            limit: Maximum number of tokens

        Returns:
            List of collected token data
        """
        logger.info(f"Collecting tokens from DexScreener (min_liq=${min_liquidity:,.0f}, limit={limit})")

        async with self.client:
            # Get trending/popular tokens
            tokens = await self.client.search_tokens(
                chain="bsc",
                min_liquidity=min_liquidity
            )

            if not tokens:
                logger.warning("No tokens found from DexScreener")
                return []

            # Limit results
            tokens = tokens[:limit]

            logger.info(f"Collected {len(tokens)} tokens from DexScreener")

            # Save to database
            saved_count = await self._save_tokens(tokens)
            logger.info(f"Saved {saved_count}/{len(tokens)} tokens to database")

            return tokens

    async def _save_tokens(self, tokens: List[Dict[str, Any]]) -> int:
        """
        Save tokens to database.

        Args:
            tokens: List of token data dictionaries

        Returns:
            Number of successfully saved tokens
        """
        saved_count = 0

        for token_data in tokens:
            try:
                token_info = token_data.copy()

                # Save basic token info
                token = await db_manager.upsert_token(
                    address=token_info["address"],
                    name=token_info["name"],
                    symbol=token_info["symbol"],
                    decimals=token_info.get("decimals", 18),
                    total_supply=token_info.get("total_supply"),
                    data_source="dexscreener"
                )

                # Save market metrics
                if token_info.get("price_usd") or token_info.get("market_cap"):
                    await db_manager.add_token_metrics(
                        token_id=token.id,
                        price_usd=token_info.get("price_usd"),
                        market_cap=token_info.get("market_cap"),
                        liquidity_usd=token_info.get("liquidity_usd"),
                        volume_24h=token_info.get("volume_24h"),
                        price_change_24h=token_info.get("price_change_24h"),
                        source="dexscreener"
                    )

                # Save trading pair
                if token_info.get("pair_address"):
                    await db_manager.upsert_token_pair(
                        token_id=token.id,
                        dex_name=token_info.get("dex_name", "unknown"),
                        pair_address=token_info["pair_address"],
                        base_token="WBNB",
                        liquidity_usd=token_info.get("liquidity_usd"),
                        volume_24h=token_info.get("volume_24h")
                    )

                saved_count += 1

            except Exception as e:
                logger.error(f"Error saving token {token_data.get('address')}: {e}")
                continue

        return saved_count
