"""Base collector abstract class."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class BaseCollector(ABC):
    """Abstract base class for data collectors."""

    def __init__(self, name: str):
        """
        Initialize collector.

        Args:
            name: Collector name
        """
        self.name = name
        self.logger = setup_logger(f"{__name__}.{name}")

    @abstractmethod
    async def collect(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Collect data.

        Returns:
            List of collected data dictionaries
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if collector is healthy.

        Returns:
            True if healthy
        """
        pass

    async def close(self):
        """Clean up resources."""
        pass
