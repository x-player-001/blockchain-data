"""Helper utility functions."""
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal


def get_current_timestamp() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


def to_decimal(value: Optional[Any]) -> Optional[Decimal]:
    """
    Convert value to Decimal safely.

    Args:
        value: Value to convert

    Returns:
        Decimal value or None
    """
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


def format_token_address(address: str) -> str:
    """
    Format token address to lowercase with 0x prefix.

    Args:
        address: Token address

    Returns:
        Formatted address
    """
    if not address:
        return ""

    address = address.lower()
    if not address.startswith("0x"):
        address = "0x" + address

    return address


def format_market_cap(market_cap: float) -> str:
    """
    Format market cap to readable string.

    Args:
        market_cap: Market cap value

    Returns:
        Formatted string (e.g., "$1.5M", "$3.2B")
    """
    if market_cap >= 1_000_000_000:
        return f"${market_cap / 1_000_000_000:.2f}B"
    elif market_cap >= 1_000_000:
        return f"${market_cap / 1_000_000:.2f}M"
    elif market_cap >= 1_000:
        return f"${market_cap / 1_000:.2f}K"
    else:
        return f"${market_cap:.2f}"


def format_percentage(value: Optional[float]) -> str:
    """
    Format percentage value.

    Args:
        value: Percentage value

    Returns:
        Formatted string with + or - prefix
    """
    if value is None:
        return "N/A"

    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def safe_get(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value.

    Args:
        data: Dictionary to search
        *keys: Nested keys
        default: Default value if not found

    Returns:
        Value or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default

    return current
