"""AVE API client for blockchain data."""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base_client import BaseAPIClient
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class AveClient(BaseAPIClient):
    """Client for AVE Cloud API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize AVE client.

        Args:
            api_key: AVE API key (required)
        """
        base_url = "https://prod.ave-api.com"
        super().__init__(base_url, rate_limit=60)  # Assume 60 requests per minute
        self.api_key = api_key or os.getenv("AVE_API_KEY")

        if not self.api_key:
            raise ValueError("AVE_API_KEY is required. Please set it in .env file or pass as parameter.")

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Override base request to add API key header.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            headers: Request headers
            retry_count: Number of retries

        Returns:
            Response JSON data or None
        """
        # Add API key to headers
        if headers is None:
            headers = {}
        headers["X-API-KEY"] = self.api_key

        return await super()._request(method, endpoint, params, headers, retry_count)

    async def get_main_tokens(
        self,
        chain: str = "bsc",
        limit: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Get main/mainstream tokens on a blockchain.

        Args:
            chain: Blockchain name (default: bsc)
            limit: Results limit (max 300)

        Returns:
            List of mainstream tokens
        """
        params = {
            "chain": chain,
            "limit": limit
        }

        data = await self.get("/v2/tokens/main", params=params)

        if not data:
            logger.warning("Failed to get main tokens from AVE API")
            return []

        # AVE API returns {status, msg, data_type, data}
        if isinstance(data, dict):
            if data.get("status") == 1:  # Success
                return data.get("data", [])
            else:
                logger.warning(f"AVE API error: {data.get('msg')}")
                return []
        else:
            logger.warning(f"Unexpected response format: {type(data)}")
            return []

    async def get_trending_tokens(
        self,
        chain: str = "bsc",
        limit: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Get trending tokens on a blockchain.

        Args:
            chain: Blockchain name (default: bsc)
            limit: Results limit (max 300)

        Returns:
            List of trending tokens
        """
        params = {
            "chain": chain,
            "limit": limit
        }

        data = await self.get("/v2/tokens/trending", params=params)

        if not data:
            logger.warning("Failed to get trending tokens from AVE API")
            return []

        # AVE API returns {status, msg, data_type, data}
        if isinstance(data, dict):
            if data.get("status") == 1:  # Success
                # Trending endpoint has nested structure: data.tokens
                result_data = data.get("data", {})
                if isinstance(result_data, dict):
                    return result_data.get("tokens", [])
                else:
                    return result_data if isinstance(result_data, list) else []
            else:
                logger.warning(f"AVE API error: {data.get('msg')}")
                return []
        else:
            logger.warning(f"Unexpected response format: {type(data)}")
            return []

    async def get_tokens_by_keyword(
        self,
        keyword: str,
        chain: str = "bsc",
        orderby: str = "market_cap",
        limit: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Search tokens by keyword.

        Args:
            keyword: Token symbol or address (required)
            chain: Blockchain name (default: bsc)
            orderby: Sort field (market_cap, tx_volume_u_24h, main_pair_tvl, fdv)
            limit: Results limit (default 100, max 300)

        Returns:
            List of tokens
        """
        params = {
            "keyword": keyword,
            "chain": chain,
            "orderby": orderby,
            "limit": limit
        }

        data = await self.get("/v2/tokens", params=params)

        if not data:
            logger.warning("Failed to get tokens from AVE API")
            return []

        # AVE API returns {status, msg, data_type, data}
        if isinstance(data, dict):
            if data.get("status") == 1:  # Success
                return data.get("data", [])
            else:
                logger.warning(f"AVE API error: {data.get('msg')}")
                return []
        else:
            logger.warning(f"Unexpected response format: {type(data)}")
            return []

    async def get_tokens_by_tvl(
        self,
        min_tvl: float = 1000000,
        chain: str = "bsc"
    ) -> List[Dict[str, Any]]:
        """
        Get tokens by minimum TVL using price endpoint.

        Args:
            min_tvl: Minimum TVL in USD
            chain: Blockchain name

        Returns:
            List of tokens
        """
        # Use POST /v2/tokens/price endpoint
        payload = {
            "token_ids": [],  # Empty to get all
            "tvl_min": min_tvl
        }

        # Need to use POST method
        if not self.session:
            import aiohttp
            self.session = aiohttp.ClientSession(timeout=self.timeout)

        url = f"{self.base_url}/v2/tokens/price"
        proxy = os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY')

        try:
            await self.rate_limiter.acquire()

            import aiohttp
            headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}

            async with self.session.post(url, json=payload, headers=headers, proxy=proxy) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == 1:
                        return data.get("data", [])
                    else:
                        logger.warning(f"AVE API error: {data.get('msg')}")
                        return []
                else:
                    logger.error(f"HTTP {response.status}: {url}")
                    return []
        except Exception as e:
            logger.error(f"Error getting tokens by TVL: {e}")
            return []

    async def get_token_detail(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Get individual token details.

        Args:
            token_id: Token address

        Returns:
            Token details including top 5 trading pairs
        """
        data = await self.get(f"/v2/tokens/{token_id}")

        if not data:
            logger.warning(f"Failed to get token detail for {token_id}")
            return None

        if isinstance(data, dict) and "data" in data:
            return data.get("data")
        return data

    async def get_token_klines(
        self,
        token_id: str,
        interval: int = 1440,  # 1 day in minutes
        limit: int = 1000,
        from_time: Optional[int] = None,
        to_time: Optional[int] = None
    ) -> List[List[Any]]:
        """
        Get kline/OHLCV data for a token.

        Args:
            token_id: Token address
            interval: Time interval in minutes
                     1, 5, 15, 30, 60, 120, 240, 1440 (day), 4320 (3day),
                     10080 (week), 43200 (month), 525600 (year)
            limit: Number of candles (default 300, max 1000)
            from_time: Start timestamp (optional)
            to_time: End timestamp (optional)

        Returns:
            List of OHLCV candles
            Format: [[timestamp, open, high, low, close, volume], ...]
        """
        params = {
            "interval": interval,
            "limit": limit
        }

        if from_time:
            params["from_time"] = from_time
        if to_time:
            params["to_time"] = to_time

        data = await self.get(f"/v2/klines/token/{token_id}", params=params)

        if not data:
            logger.warning(f"Failed to get klines for {token_id}")
            return []

        # Extract klines data from response
        if isinstance(data, dict) and "data" in data:
            klines = data.get("data", [])
        elif isinstance(data, list):
            klines = data
        else:
            logger.warning(f"Unexpected klines response format: {type(data)}")
            return []

        return klines

    async def get_pair_klines(
        self,
        pair_id: str,
        interval: int = 1440,
        limit: int = 1000,
        category: str = "",  # Empty for BSC pairs (usdt causes 500 error)
        from_time: Optional[int] = None,
        to_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get kline/OHLCV data for a trading pair.

        Args:
            pair_id: Pair address (will auto-append -bsc if not present)
            interval: Time interval in minutes
            limit: Number of candles (default 300, max 1000)
            category: Price type (usdt, base, main)
            from_time: Start timestamp in seconds (optional)
            to_time: End timestamp in seconds (optional)

        Returns:
            List of OHLCV candles in dict format
            Format: [{"open": "110652.17", "high": "111989.54", "low": "107452.42",
                     "close": "108199.14", "volume": "53851652.08", "time": 1760572800}, ...]
        """
        # Ensure pair_id has -bsc suffix
        if not pair_id.endswith('-bsc'):
            pair_id = f"{pair_id}-bsc"

        params = {
            "interval": interval,
            "limit": limit,
            "category": category
        }

        if from_time:
            params["from_time"] = from_time
        if to_time:
            params["to_time"] = to_time

        data = await self.get(f"/v2/klines/pair/{pair_id}", params=params)

        if not data:
            logger.warning(f"Failed to get pair klines for {pair_id}")
            return []

        # AVE API returns: {status: 1, msg: "SUCCESS", data: {points: [...], total_count: X}}
        if isinstance(data, dict):
            if data.get("status") == 1:
                result_data = data.get("data", {})
                if isinstance(result_data, dict):
                    return result_data.get("points", [])
                return []
            else:
                logger.warning(f"AVE API error for {pair_id}: {data.get('msg')}")
                return []

        return []

    async def filter_tokens_by_market_cap(
        self,
        chain: str = "bsc",
        min_market_cap: float = 1000000,  # 1M USD
        limit: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Filter tokens by minimum market cap.

        Uses /v2/tokens/trending endpoint to get token list, then filters by market cap.

        Args:
            chain: Blockchain name
            min_market_cap: Minimum market cap in USD (default 1M)
            limit: Maximum results

        Returns:
            List of tokens with market cap >= min_market_cap
        """
        logger.info(f"Collecting tokens from AVE API (trending only)...")

        all_tokens = []
        seen_addresses = set()

        try:
            # Get trending tokens
            logger.info("Fetching trending tokens...")
            trending_tokens = await self.get_trending_tokens(chain=chain, limit=300)

            for token in trending_tokens:
                address = token.get("token") or token.get("address")
                if address and address.lower() not in seen_addresses:
                    market_cap = token.get("market_cap")
                    if market_cap and float(market_cap) >= min_market_cap:
                        all_tokens.append(token)
                        seen_addresses.add(address.lower())

                        if len(all_tokens) >= limit:
                            break

            logger.info(f"Found {len(all_tokens)} tokens with market cap >= ${min_market_cap:,.0f}")

        except Exception as e:
            logger.error(f"Error fetching tokens from AVE API: {e}")

        return all_tokens[:limit]

    async def health_check(self) -> bool:
        """
        Check if the API is healthy.

        Returns:
            True if API is responding
        """
        try:
            # Try to get a small list of tokens
            tokens = await self.get_tokens(chain="bsc", limit=1)
            return tokens is not None and len(tokens) >= 0
        except Exception as e:
            logger.error(f"AVE API health check failed: {e}")
            return False
