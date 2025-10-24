"""BscScan API client for blockchain data."""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base_client import BaseAPIClient
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class BscScanClient(BaseAPIClient):
    """Client for BscScan API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize BscScan client.

        Args:
            api_key: BscScan API key (optional, can use free tier without key)
        """
        # Use Etherscan API V2 for BSC (chainid=56)
        base_url = "https://api.etherscan.io/v2/api"
        super().__init__(base_url, rate_limit=5)  # 5 requests per second for free tier
        # Use Etherscan V2 API key for V2 endpoints
        self.api_key = api_key or os.getenv("Etherscan_V2_API_KEY") or os.getenv("BSCSCAN_API_KEY", "YourApiKeyToken")
        self.chainid = 56  # BSC mainnet

    async def get_contract_creator(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """
        Get contract creation transaction and creator address.

        Args:
            contract_address: Token contract address

        Returns:
            Dict with creator address, tx hash, and block number
        """
        params = {
            "chainid": self.chainid,
            "module": "contract",
            "action": "getcontractcreation",
            "contractaddresses": contract_address,
            "apikey": self.api_key
        }

        data = await self.get("", params=params)

        if not data or data.get("status") != "1":
            logger.warning(f"Failed to get creator for {contract_address}: {data.get('message')}")
            return None

        result = data.get("result", [])
        if not result or len(result) == 0:
            return None

        creator_info = result[0]
        return {
            "creator_address": creator_info.get("contractCreator"),
            "tx_hash": creator_info.get("txHash"),
            "contract_address": contract_address
        }

    async def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get transaction receipt including block number and timestamp.

        Args:
            tx_hash: Transaction hash

        Returns:
            Transaction receipt data
        """
        params = {
            "chainid": self.chainid,
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash,
            "apikey": self.api_key
        }

        data = await self.get("", params=params)

        if not data or not data.get("result"):
            logger.warning(f"Failed to get receipt for {tx_hash}")
            return None

        return data.get("result")

    async def get_block_by_number(self, block_number: int) -> Optional[Dict[str, Any]]:
        """
        Get block information including timestamp.

        Args:
            block_number: Block number

        Returns:
            Block data
        """
        params = {
            "chainid": self.chainid,
            "module": "proxy",
            "action": "eth_getBlockByNumber",
            "tag": hex(block_number),
            "boolean": "true",
            "apikey": self.api_key
        }

        data = await self.get("", params=params)

        if not data or not data.get("result"):
            logger.warning(f"Failed to get block {block_number}")
            return None

        return data.get("result")

    async def get_normal_transactions(
        self,
        address: str,
        start_block: int = 0,
        end_block: int = 99999999,
        page: int = 1,
        offset: int = 100,
        sort: str = "asc"
    ) -> List[Dict[str, Any]]:
        """
        Get normal transactions for an address.

        Args:
            address: Wallet address
            start_block: Starting block number
            end_block: Ending block number
            page: Page number
            offset: Number of transactions per page (max 10000)
            sort: Sort order ('asc' or 'desc')

        Returns:
            List of transactions
        """
        params = {
            "chainid": self.chainid,
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort,
            "apikey": self.api_key
        }

        data = await self.get("", params=params)

        if not data or data.get("status") != "1":
            logger.warning(f"Failed to get transactions for {address}: {data.get('message')}")
            return []

        return data.get("result", [])

    async def get_token_transfers(
        self,
        contract_address: Optional[str] = None,
        address: Optional[str] = None,
        start_block: int = 0,
        end_block: int = 99999999,
        page: int = 1,
        offset: int = 100,
        sort: str = "asc"
    ) -> List[Dict[str, Any]]:
        """
        Get ERC20 token transfer events.

        Args:
            contract_address: Token contract address (optional)
            address: Wallet address (optional)
            start_block: Starting block number
            end_block: Ending block number
            page: Page number
            offset: Number of records per page (max 10000)
            sort: Sort order ('asc' or 'desc')

        Returns:
            List of token transfer events
        """
        params = {
            "chainid": self.chainid,
            "module": "account",
            "action": "tokentx",
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort,
            "apikey": self.api_key
        }

        if contract_address:
            params["contractaddress"] = contract_address
        if address:
            params["address"] = address

        data = await self.get("", params=params)

        if not data or data.get("status") != "1":
            logger.warning(f"Failed to get token transfers: {data.get('message')}")
            return []

        return data.get("result", [])

    async def get_internal_transactions(
        self,
        address: Optional[str] = None,
        tx_hash: Optional[str] = None,
        start_block: int = 0,
        end_block: int = 99999999,
        page: int = 1,
        offset: int = 100,
        sort: str = "asc"
    ) -> List[Dict[str, Any]]:
        """
        Get internal transactions (contract calls).

        Args:
            address: Wallet address (optional)
            tx_hash: Transaction hash (optional)
            start_block: Starting block number
            end_block: Ending block number
            page: Page number
            offset: Number of records per page
            sort: Sort order ('asc' or 'desc')

        Returns:
            List of internal transactions
        """
        params = {
            "chainid": self.chainid,
            "module": "account",
            "action": "txlistinternal",
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort,
            "apikey": self.api_key
        }

        if address:
            params["address"] = address
        if tx_hash:
            params["txhash"] = tx_hash

        data = await self.get("", params=params)

        if not data or data.get("status") != "1":
            return []

        return data.get("result", [])

    async def health_check(self) -> bool:
        """
        Check if the API is healthy.

        Returns:
            True if API is responding
        """
        try:
            # Simple health check - get BSC supply
            params = {
                "chainid": self.chainid,
                "module": "stats",
                "action": "bnbsupply",
                "apikey": self.api_key
            }
            data = await self.get("", params=params)
            return data is not None and data.get("status") == "1"
        except Exception:
            return False

    def parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        Parse Unix timestamp to datetime.

        Args:
            timestamp_str: Unix timestamp string

        Returns:
            datetime object
        """
        return datetime.fromtimestamp(int(timestamp_str))
