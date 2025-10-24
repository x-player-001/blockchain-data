"""Configuration management module."""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""

    # BSC Configuration
    BSC_RPC_URL: str = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")

    # API Keys
    BSCSCAN_API_KEY: Optional[str] = os.getenv("BSCSCAN_API_KEY")

    # Database Configuration (PostgreSQL + TimescaleDB)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/blockchain_data")

    # Cache Configuration
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    USE_REDIS: bool = os.getenv("USE_REDIS", "false").lower() == "true"

    # Application Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    UPDATE_INTERVAL: int = int(os.getenv("UPDATE_INTERVAL", "300"))
    MIN_MARKET_CAP: float = float(os.getenv("MIN_MARKET_CAP", "1000000"))
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))

    # Rate Limiting (requests per minute)
    DEXSCREENER_RATE_LIMIT: int = int(os.getenv("DEXSCREENER_RATE_LIMIT", "300"))
    GECKOTERMINAL_RATE_LIMIT: int = int(os.getenv("GECKOTERMINAL_RATE_LIMIT", "30"))
    BSCSCAN_RATE_LIMIT: int = int(os.getenv("BSCSCAN_RATE_LIMIT", "5"))
    DEXPAPRIKA_RATE_LIMIT: int = int(os.getenv("DEXPAPRIKA_RATE_LIMIT", "7"))  # 10k per day ≈ 7 per minute

    # API Endpoints
    DEXSCREENER_BASE_URL: str = "https://api.dexscreener.com/latest/dex"
    GECKOTERMINAL_BASE_URL: str = "https://api.geckoterminal.com/api/v2"
    BSCSCAN_BASE_URL: str = "https://api.bscscan.com/api"
    DEXPAPRIKA_BASE_URL: str = "https://api.dexpaprika.com"

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration."""
        # Check required settings
        if not cls.BSC_RPC_URL:
            raise ValueError("BSC_RPC_URL is required")

        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")

        return True



config = Config()
