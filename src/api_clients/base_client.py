"""Base API client with rate limiting and error handling."""
import asyncio
import os
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import time

import aiohttp

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate_limit: int):
        """
        Initialize rate limiter.

        Args:
            rate_limit: Maximum requests per minute
        """
        self.rate_limit = rate_limit
        self.tokens = rate_limit
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Acquire permission to make a request."""
        async with self.lock:
            now = time.time()
            time_passed = now - self.last_update
            self.last_update = now

            # Refill tokens based on time passed
            self.tokens += time_passed * (self.rate_limit / 60.0)
            if self.tokens > self.rate_limit:
                self.tokens = self.rate_limit

            # Wait if no tokens available
            if self.tokens < 1:
                sleep_time = (1 - self.tokens) / (self.rate_limit / 60.0)
                logger.debug(f"Rate limit reached, waiting {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class BaseAPIClient(ABC):
    """Base API client with common functionality."""

    def __init__(
        self,
        base_url: str,
        rate_limit: int,
        timeout: int = 30
    ):
        """
        Initialize API client.

        Args:
            base_url: API base URL
            rate_limit: Requests per minute
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.rate_limiter = RateLimiter(rate_limit)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        # Get proxy from environment variables
        proxy = os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY') or os.getenv('http_proxy') or os.getenv('https_proxy')

        connector = None
        # Only create custom connector if proxy is set
        # Note: We keep SSL verification enabled for security
        # If proxy SSL issues occur, set ssl=False only when proxy is used

        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=connector
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request with rate limiting and retry.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            headers: Request headers
            retry_count: Number of retries on failure

        Returns:
            Response JSON data or None on failure
        """
        if not self.session:
            # Create session with default SSL verification
            self.session = aiohttp.ClientSession(timeout=self.timeout)

        url = f"{self.base_url}{endpoint}"

        # Get proxy for this request
        proxy = os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY') or os.getenv('http_proxy') or os.getenv('https_proxy')

        for attempt in range(retry_count):
            try:
                # Rate limiting
                await self.rate_limiter.acquire()

                # Make request
                async with self.session.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    proxy=proxy
                ) as response:
                    # Check status
                    if response.status == 429:
                        # Rate limited
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue

                    if response.status >= 500:
                        # Server error, retry
                        logger.warning(
                            f"Server error {response.status}, "
                            f"attempt {attempt + 1}/{retry_count}"
                        )
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue

                    if response.status >= 400:
                        # Client error
                        logger.error(f"Client error {response.status}: {url}")
                        return None

                    # Success
                    data = await response.json()
                    return data

            except asyncio.TimeoutError:
                logger.warning(f"Timeout on {url}, attempt {attempt + 1}/{retry_count}")
                await asyncio.sleep(2 ** attempt)

            except aiohttp.ClientError as e:
                logger.error(f"Request error on {url}: {e}")
                await asyncio.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"Unexpected error on {url}: {e}")
                return None

        logger.error(f"Failed after {retry_count} attempts: {url}")
        return None

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make GET request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Request headers

        Returns:
            Response JSON data
        """
        return await self._request("GET", endpoint, params, headers)

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if API is accessible.

        Returns:
            True if API is healthy
        """
        pass

    async def close(self):
        """Close client session."""
        if self.session:
            await self.session.close()
