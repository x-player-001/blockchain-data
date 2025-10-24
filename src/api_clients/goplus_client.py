"""GoPlus Labs API client for token security checks."""
import asyncio
from typing import Dict, List, Any, Optional

from .base_client import BaseAPIClient
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class GoPlusClient(BaseAPIClient):
    """Client for GoPlus Labs token security API."""

    BASE_URL = "https://api.gopluslabs.io/api/v1"

    def __init__(self, rate_limit: int = 10):
        """
        Initialize GoPlus client.

        Args:
            rate_limit: Maximum requests per second (default: 10)
        """
        super().__init__(base_url=self.BASE_URL, rate_limit=rate_limit)

    async def health_check(self) -> bool:
        """
        Check if GoPlus API is accessible.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Test with a known token (WBNB on BSC)
            result = await self.check_token_security(
                "56",
                "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
            )
            return result is not None
        except Exception as e:
            logger.error(f"GoPlus API health check failed: {e}")
            return False

    async def get_token_security(
        self,
        chain_id: str,
        contract_addresses: List[str]
    ) -> Dict[str, Any]:
        """
        Get token security information.

        Args:
            chain_id: Blockchain ID (e.g., "56" for BSC, "1" for Ethereum)
            contract_addresses: List of token contract addresses

        Returns:
            Token security data for each address
        """
        if not contract_addresses:
            return {}

        # GoPlus API supports batch queries (comma-separated)
        addresses_param = ",".join(contract_addresses)

        endpoint = f"/token_security/{chain_id}"
        params = {"contract_addresses": addresses_param}

        try:
            response = await self._request("GET", endpoint, params=params)

            if response.get("code") == 1 and response.get("message") == "OK":
                return response.get("result", {})
            else:
                logger.warning(f"GoPlus API returned error: {response.get('message')}")
                return {}

        except Exception as e:
            logger.error(f"Error fetching token security: {e}")
            return {}

    async def check_token_security(
        self,
        chain_id: str,
        contract_address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check security for a single token.

        Args:
            chain_id: Blockchain ID
            contract_address: Token contract address

        Returns:
            Token security data or None if failed
        """
        result = await self.get_token_security(chain_id, [contract_address])

        # GoPlus returns addresses in lowercase
        addr_lower = contract_address.lower()
        return result.get(addr_lower)

    async def batch_check_security(
        self,
        chain_id: str,
        contract_addresses: List[str],
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """
        Check security for multiple tokens in batches.

        Args:
            chain_id: Blockchain ID
            contract_addresses: List of contract addresses
            batch_size: Number of addresses per batch (default: 10)

        Returns:
            Combined security data for all addresses
        """
        all_results = {}

        # Split into batches
        for i in range(0, len(contract_addresses), batch_size):
            batch = contract_addresses[i:i + batch_size]

            logger.info(f"Checking security for batch {i//batch_size + 1} ({len(batch)} tokens)...")

            result = await self.get_token_security(chain_id, batch)
            all_results.update(result)

            # Rate limiting: wait between batches
            if i + batch_size < len(contract_addresses):
                await asyncio.sleep(1)

        return all_results

    def is_open_source(self, security_data: Dict[str, Any]) -> bool:
        """
        Check if token contract is open source.

        Args:
            security_data: Token security data from GoPlus API

        Returns:
            True if contract is open source, False otherwise
        """
        return security_data.get("is_open_source") == "1"

    def is_safe_token(
        self,
        security_data: Dict[str, Any],
        require_open_source: bool = True
    ) -> bool:
        """
        Determine if a token is considered safe based on security checks.

        Args:
            security_data: Token security data from GoPlus API
            require_open_source: Require contract to be open source

        Returns:
            True if token passes safety checks, False otherwise
        """
        if not security_data:
            return False

        # Check open source requirement
        if require_open_source and not self.is_open_source(security_data):
            logger.debug(f"Token {security_data.get('token_symbol')} is not open source")
            return False

        # Check for honeypot indicators
        if security_data.get("is_honeypot") == "1":
            logger.debug(f"Token {security_data.get('token_symbol')} is a honeypot")
            return False

        # Check if cannot buy
        if security_data.get("cannot_buy") == "1":
            logger.debug(f"Token {security_data.get('token_symbol')} cannot be bought")
            return False

        # Check if cannot sell all
        if security_data.get("cannot_sell_all") == "1":
            logger.debug(f"Token {security_data.get('token_symbol')} cannot sell all")
            return False

        # Check for same creator honeypot history
        if security_data.get("honeypot_with_same_creator") == "1":
            logger.debug(f"Token {security_data.get('token_symbol')} creator has honeypot history")
            return False

        return True

    def get_security_summary(self, security_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a summary of key security metrics.

        Args:
            security_data: Token security data from GoPlus API

        Returns:
            Summary dict with key security metrics
        """
        return {
            "token_name": security_data.get("token_name"),
            "token_symbol": security_data.get("token_symbol"),
            "is_open_source": self.is_open_source(security_data),
            "buy_tax": security_data.get("buy_tax", "unknown"),
            "sell_tax": security_data.get("sell_tax", "unknown"),
            "cannot_buy": security_data.get("cannot_buy") == "1",
            "cannot_sell_all": security_data.get("cannot_sell_all") == "1",
            "is_honeypot": security_data.get("is_honeypot") == "1",
            "honeypot_with_same_creator": security_data.get("honeypot_with_same_creator") == "1",
            "creator_percent": float(security_data.get("creator_percent", 0)),
            "holder_count": int(security_data.get("holder_count", 0)),
            "lp_holder_count": int(security_data.get("lp_holder_count", 0)),
            "is_in_dex": security_data.get("is_in_dex") == "1",
        }
