"""Database models."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import (
    Column, String, Integer, DateTime, Numeric,
    ForeignKey, Index, BigInteger
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Token(Base):
    """Token model - stores basic token information."""

    __tablename__ = "tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    address = Column(String(42), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    symbol = Column(String(50), nullable=False)
    decimals = Column(Integer, default=18)
    total_supply = Column(Numeric(78, 0), nullable=True)  # Large enough for uint256 blockchain values
    data_source = Column(String(50), nullable=True)  # Data source (ave, geckoterminal, dexscreener)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    metrics = relationship("TokenMetrics", back_populates="token", cascade="all, delete-orphan")
    pairs = relationship("TokenPair", back_populates="token", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Token {self.symbol} ({self.address})>"


class TokenMetrics(Base):
    """Token metrics model - stores time-series data."""

    __tablename__ = "token_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_id = Column(String(36), ForeignKey("tokens.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Price and market data
    price_usd = Column(Numeric(30, 18), nullable=True)
    market_cap = Column(Numeric(30, 2), nullable=True)
    liquidity_usd = Column(Numeric(30, 2), nullable=True)
    volume_24h = Column(Numeric(30, 2), nullable=True)
    price_change_24h = Column(Numeric(10, 2), nullable=True)

    # Token statistics
    holders_count = Column(Integer, nullable=True)
    transactions_24h = Column(Integer, nullable=True)

    # Data source tracking
    source = Column(String(50), nullable=True)  # 'dexscreener', 'geckoterminal', or 'merged'

    # Relationships
    token = relationship("Token", back_populates="metrics")

    # Indexes
    __table_args__ = (
        Index("idx_token_timestamp", "token_id", "timestamp"),
        Index("idx_market_cap", "market_cap"),
        Index("idx_source", "source"),
    )

    def __repr__(self):
        return f"<TokenMetrics {self.token_id} at {self.timestamp}>"


class TokenPair(Base):
    """Token pair model - stores DEX trading pair information."""

    __tablename__ = "token_pairs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_id = Column(String(36), ForeignKey("tokens.id"), nullable=False)
    dex_name = Column(String(50), nullable=False)  # e.g., "PancakeSwap"
    pair_address = Column(String(100), nullable=False, index=True)  # Increased to support longer pool IDs
    base_token = Column(String(50), nullable=False)  # e.g., "WBNB", "BUSD"

    # Pair metrics
    liquidity_usd = Column(Numeric(30, 2), nullable=True)
    volume_24h = Column(Numeric(30, 2), nullable=True)

    # Pair creation time on blockchain
    pair_created_at = Column(DateTime, nullable=True)  # When the pair was created on-chain

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    token = relationship("Token", back_populates="pairs")

    # Indexes
    __table_args__ = (
        Index("idx_token_dex", "token_id", "dex_name"),
    )

    def __repr__(self):
        return f"<TokenPair {self.pair_address} on {self.dex_name}>"


class TokenOHLCV(Base):
    """Token OHLCV (candlestick) model - stores historical price data."""

    __tablename__ = "token_ohlcv"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_id = Column(String(36), ForeignKey("tokens.id"), nullable=False)
    pool_address = Column(String(100), nullable=False)  # Trading pool address
    timeframe = Column(String(20), nullable=False)  # 'minute', 'hour', 'day'
    timestamp = Column(DateTime, nullable=False, index=True)

    # OHLCV data
    open = Column(Numeric(30, 18), nullable=False)
    high = Column(Numeric(30, 18), nullable=False)
    low = Column(Numeric(30, 18), nullable=False)
    close = Column(Numeric(30, 18), nullable=False)
    volume = Column(Numeric(30, 2), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    token = relationship("Token")

    # Indexes
    __table_args__ = (
        Index("idx_token_timeframe_timestamp", "token_id", "timeframe", "timestamp"),
        Index("idx_pool_timeframe_timestamp", "pool_address", "timeframe", "timestamp"),
    )

    def __repr__(self):
        return f"<TokenOHLCV {self.token_id} {self.timeframe} at {self.timestamp}>"


class TokenDeployment(Base):
    """Token deployment information - stores contract creation details."""

    __tablename__ = "token_deployments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_id = Column(String(36), ForeignKey("tokens.id"), nullable=False, unique=True)

    # Deployment info
    deployer_address = Column(String(42), nullable=False, index=True)
    deploy_tx_hash = Column(String(66), nullable=False, unique=True)
    deploy_block = Column(BigInteger, nullable=False, index=True)
    deploy_timestamp = Column(DateTime, nullable=False, index=True)

    # Gas info
    gas_used = Column(BigInteger, nullable=True)
    gas_price = Column(Numeric(30, 0), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    token = relationship("Token")

    def __repr__(self):
        return f"<TokenDeployment {self.token_id} by {self.deployer_address}>"


class WalletTransaction(Base):
    """Wallet transaction records - tracks fund flows."""

    __tablename__ = "wallet_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Transaction info
    tx_hash = Column(String(66), nullable=False, index=True)
    block_number = Column(BigInteger, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Addresses
    from_address = Column(String(42), nullable=False, index=True)
    to_address = Column(String(42), nullable=True, index=True)

    # Value
    value = Column(Numeric(30, 0), nullable=False)  # Wei
    value_usd = Column(Numeric(30, 2), nullable=True)  # USD value at time

    # Token transfer (if applicable)
    token_address = Column(String(42), nullable=True, index=True)
    token_value = Column(Numeric(30, 0), nullable=True)

    # Gas
    gas_used = Column(BigInteger, nullable=True)
    gas_price = Column(Numeric(30, 0), nullable=True)

    # Status
    status = Column(Integer, nullable=True)  # 1 = success, 0 = failed

    created_at = Column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_wallet_from_timestamp", "from_address", "timestamp"),
        Index("idx_wallet_to_timestamp", "to_address", "timestamp"),
        Index("idx_wallet_token_timestamp", "token_address", "timestamp"),
    )

    def __repr__(self):
        return f"<WalletTransaction {self.tx_hash[:10]}... from {self.from_address[:10]}>"


class EarlyTrade(Base):
    """Early trades after token deployment - first 5 minutes of trading."""

    __tablename__ = "early_trades"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_id = Column(String(36), ForeignKey("tokens.id"), nullable=False)

    # Trade info
    tx_hash = Column(String(66), nullable=False, index=True)
    block_number = Column(BigInteger, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Trader
    trader_address = Column(String(42), nullable=False, index=True)

    # Trade details
    trade_type = Column(String(10), nullable=False)  # 'buy' or 'sell'
    token_amount = Column(Numeric(30, 0), nullable=False)
    bnb_amount = Column(Numeric(30, 18), nullable=False)
    price_usd = Column(Numeric(30, 18), nullable=True)

    # Time from deployment
    seconds_after_deploy = Column(Integer, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    token = relationship("Token")

    # Indexes
    __table_args__ = (
        Index("idx_token_seconds", "token_id", "seconds_after_deploy"),
        Index("idx_trader_token", "trader_address", "token_id"),
    )

    def __repr__(self):
        return f"<EarlyTrade {self.trade_type} {self.token_id} at +{self.seconds_after_deploy}s>"


class DexScreenerToken(Base):
    """DexScreener token data - stores parsed token pair information from DexScreener."""

    __tablename__ = "dexscreener_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Chain and DEX info
    chain_id = Column(String(20), nullable=False, index=True)  # e.g., "bsc"
    dex_id = Column(String(50), nullable=False, index=True)  # e.g., "pancakeswap"
    pair_address = Column(String(100), unique=True, nullable=False, index=True)

    # Base Token (the token being traded)
    base_token_address = Column(String(42), nullable=False, index=True)
    base_token_name = Column(String(255), nullable=True)
    base_token_symbol = Column(String(50), nullable=False, index=True)

    # Quote Token (usually WBNB, BUSD, USDT)
    quote_token_address = Column(String(42), nullable=True)
    quote_token_name = Column(String(255), nullable=True)
    quote_token_symbol = Column(String(50), nullable=True)

    # Price data
    price_native = Column(Numeric(30, 18), nullable=True)  # Price in native token (e.g., BNB)
    price_usd = Column(Numeric(30, 18), nullable=True)  # Price in USD

    # Volume data
    volume_m5 = Column(Numeric(30, 2), nullable=True)  # 5 minute volume
    volume_h1 = Column(Numeric(30, 2), nullable=True)  # 1 hour volume
    volume_h6 = Column(Numeric(30, 2), nullable=True)  # 6 hour volume
    volume_h24 = Column(Numeric(30, 2), nullable=True)  # 24 hour volume

    # Transaction counts
    txns_m5_buys = Column(Integer, nullable=True)
    txns_m5_sells = Column(Integer, nullable=True)
    txns_h1_buys = Column(Integer, nullable=True)
    txns_h1_sells = Column(Integer, nullable=True)
    txns_h6_buys = Column(Integer, nullable=True)
    txns_h6_sells = Column(Integer, nullable=True)
    txns_h24_buys = Column(Integer, nullable=True)
    txns_h24_sells = Column(Integer, nullable=True)

    # Price changes
    price_change_h1 = Column(Numeric(10, 2), nullable=True)
    price_change_h6 = Column(Numeric(10, 2), nullable=True)
    price_change_h24 = Column(Numeric(10, 2), nullable=True)

    # Liquidity
    liquidity_usd = Column(Numeric(30, 2), nullable=True)
    liquidity_base = Column(Numeric(40, 2), nullable=True)  # Increased for large token amounts
    liquidity_quote = Column(Numeric(30, 2), nullable=True)

    # Market data
    fdv = Column(Numeric(30, 2), nullable=True)  # Fully Diluted Valuation
    market_cap = Column(Numeric(30, 2), nullable=True)

    # Pair creation time
    pair_created_at = Column(BigInteger, nullable=True)  # Unix timestamp in milliseconds

    # Additional info
    image_url = Column(String(500), nullable=True)
    website_url = Column(String(500), nullable=True)
    twitter_url = Column(String(500), nullable=True)
    telegram_url = Column(String(500), nullable=True)

    # DexScreener URL
    dexscreener_url = Column(String(500), nullable=True)

    # Labels (stored as comma-separated string)
    labels = Column(String(200), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_dex_chain_dex", "chain_id", "dex_id"),
        Index("idx_dex_base_token", "base_token_address"),
        Index("idx_dex_market_cap", "market_cap"),
        Index("idx_dex_volume_24h", "volume_h24"),
        Index("idx_dex_liquidity", "liquidity_usd"),
    )

    def __repr__(self):
        return f"<DexScreenerToken {self.base_token_symbol} on {self.dex_id} ({self.pair_address[:10]}...)>"


class PotentialToken(Base):
    """Potential token model - stores scraped top gainers before adding to monitoring."""

    __tablename__ = "potential_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Chain info
    chain = Column(String(20), nullable=False, default='bsc', index=True)  # bsc, solana, etc.

    # Token reference
    token_address = Column(String(100), nullable=False, index=True)  # 扩展以支持 Solana (44位)
    token_symbol = Column(String(50), nullable=False)
    token_name = Column(String(255), nullable=True)

    # DEX info
    dex_id = Column(String(50), nullable=False)
    pair_address = Column(String(100), nullable=False, index=True)
    amm = Column(String(50), nullable=True)  # AMM type (cakev2, etc.)
    dex_type = Column(String(20), nullable=True)  # Solana DEX type (CPMM, DLMM, etc.)

    # Price info when scraped
    scraped_price_usd = Column(Numeric(30, 18), nullable=False)
    scraped_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Market data when scraped
    market_cap_at_scrape = Column(Numeric(30, 2), nullable=True)
    liquidity_at_scrape = Column(Numeric(30, 2), nullable=True)
    volume_24h_at_scrape = Column(Numeric(30, 2), nullable=True)
    price_change_24h_at_scrape = Column(Numeric(10, 2), nullable=True)  # The gain % when scraped

    # Current data (updated by AVE API)
    current_price_usd = Column(Numeric(30, 18), nullable=True)
    price_ath_usd = Column(Numeric(30, 18), nullable=True)  # Historical ATH
    current_tvl = Column(Numeric(30, 2), nullable=True)
    current_market_cap = Column(Numeric(30, 2), nullable=True)

    # Price changes (multiple timeframes)
    price_change_1m = Column(Numeric(10, 2), nullable=True)
    price_change_5m = Column(Numeric(10, 2), nullable=True)
    price_change_15m = Column(Numeric(10, 2), nullable=True)
    price_change_30m = Column(Numeric(10, 2), nullable=True)
    price_change_1h = Column(Numeric(10, 2), nullable=True)
    price_change_4h = Column(Numeric(10, 2), nullable=True)
    price_change_24h = Column(Numeric(10, 2), nullable=True)

    # Volume data (multiple timeframes)
    volume_1m = Column(Numeric(30, 2), nullable=True)
    volume_5m = Column(Numeric(30, 2), nullable=True)
    volume_15m = Column(Numeric(30, 2), nullable=True)
    volume_30m = Column(Numeric(30, 2), nullable=True)
    volume_1h = Column(Numeric(30, 2), nullable=True)
    volume_4h = Column(Numeric(30, 2), nullable=True)
    volume_24h = Column(Numeric(30, 2), nullable=True)

    # Transaction counts (multiple timeframes)
    tx_count_1m = Column(Integer, nullable=True)
    tx_count_5m = Column(Integer, nullable=True)
    tx_count_15m = Column(Integer, nullable=True)
    tx_count_30m = Column(Integer, nullable=True)
    tx_count_1h = Column(Integer, nullable=True)
    tx_count_4h = Column(Integer, nullable=True)
    tx_count_24h = Column(Integer, nullable=True)

    # Buy/Sell transaction counts (24h)
    buys_24h = Column(Integer, nullable=True)
    sells_24h = Column(Integer, nullable=True)

    # Traders data (24h)
    makers_24h = Column(Integer, nullable=True)
    buyers_24h = Column(Integer, nullable=True)
    sellers_24h = Column(Integer, nullable=True)

    # Price range (24h)
    price_24h_high = Column(Numeric(30, 18), nullable=True)
    price_24h_low = Column(Numeric(30, 18), nullable=True)
    open_price_24h = Column(Numeric(30, 18), nullable=True)

    # Token creation info
    token_created_at = Column(DateTime, nullable=True)
    first_trade_at = Column(DateTime, nullable=True)
    creation_block_number = Column(BigInteger, nullable=True)
    creation_tx_hash = Column(String(66), nullable=True)

    # LP and security info
    lp_holders = Column(Integer, nullable=True)
    lp_locked_percent = Column(Numeric(5, 2), nullable=True)
    lp_lock_platform = Column(String(100), nullable=True)

    # Early trading metrics
    rusher_tx_count = Column(Integer, nullable=True)
    sniper_tx_count = Column(Integer, nullable=True)

    # Status tracking
    is_added_to_monitoring = Column(Integer, nullable=False, default=0)  # 0 = not added, 1 = added
    added_to_monitoring_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_ave_update = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete timestamp

    # Indexes
    __table_args__ = (
        Index("idx_potential_scraped_time", "scraped_timestamp"),
        Index("idx_potential_is_added", "is_added_to_monitoring"),
        Index("idx_potential_pair", "pair_address"),
        Index("idx_potential_deleted_at", "deleted_at"),
    )

    def __repr__(self):
        return f"<PotentialToken {self.token_symbol} (added={self.is_added_to_monitoring})>"


class MonitoredToken(Base):
    """Monitored token model - stores top gainers for price monitoring."""

    __tablename__ = "monitored_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Token reference (can link to tokens table or store independently)
    token_address = Column(String(100), nullable=False, index=True)  # Extended for Solana
    token_symbol = Column(String(50), nullable=False)
    token_name = Column(String(255), nullable=True)

    # Chain info
    chain = Column(String(20), nullable=False, default='bsc', index=True)  # bsc, solana, etc.

    # DEX info
    dex_id = Column(String(50), nullable=False)
    pair_address = Column(String(100), nullable=False, index=True)
    amm = Column(String(50), nullable=True)  # AMM type (cakev2, etc.)
    dex_type = Column(String(20), nullable=True)  # Solana DEX type (CPMM, DLMM, etc.)

    # Entry price (when added to monitoring)
    entry_price_usd = Column(Numeric(30, 18), nullable=False)
    entry_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Current tracking
    current_price_usd = Column(Numeric(30, 18), nullable=True)
    last_update_timestamp = Column(DateTime, nullable=True)

    # Peak tracking (highest price since entry)
    peak_price_usd = Column(Numeric(30, 18), nullable=False)  # Initially same as entry_price
    peak_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Historical all-time high (from AVE API - blockchain historical data)
    price_ath_usd = Column(Numeric(30, 18), nullable=True)  # All-time high price from chain history

    # Market data at entry
    market_cap_at_entry = Column(Numeric(30, 2), nullable=True)
    liquidity_at_entry = Column(Numeric(30, 2), nullable=True)
    volume_24h_at_entry = Column(Numeric(30, 2), nullable=True)
    price_change_24h_at_entry = Column(Numeric(10, 2), nullable=True)  # The gain % when added

    # Current market data (from latest update)
    current_tvl = Column(Numeric(30, 2), nullable=True)  # Total Value Locked
    current_market_cap = Column(Numeric(30, 2), nullable=True)

    # Price changes (multiple timeframes)
    price_change_1m = Column(Numeric(10, 2), nullable=True)
    price_change_5m = Column(Numeric(10, 2), nullable=True)
    price_change_15m = Column(Numeric(10, 2), nullable=True)
    price_change_30m = Column(Numeric(10, 2), nullable=True)
    price_change_1h = Column(Numeric(10, 2), nullable=True)
    price_change_4h = Column(Numeric(10, 2), nullable=True)
    price_change_24h = Column(Numeric(10, 2), nullable=True)

    # Volume data (multiple timeframes)
    volume_1m = Column(Numeric(30, 2), nullable=True)
    volume_5m = Column(Numeric(30, 2), nullable=True)
    volume_15m = Column(Numeric(30, 2), nullable=True)
    volume_30m = Column(Numeric(30, 2), nullable=True)
    volume_1h = Column(Numeric(30, 2), nullable=True)
    volume_4h = Column(Numeric(30, 2), nullable=True)
    volume_24h = Column(Numeric(30, 2), nullable=True)

    # Transaction counts (multiple timeframes)
    tx_count_1m = Column(Integer, nullable=True)
    tx_count_5m = Column(Integer, nullable=True)
    tx_count_15m = Column(Integer, nullable=True)
    tx_count_30m = Column(Integer, nullable=True)
    tx_count_1h = Column(Integer, nullable=True)
    tx_count_4h = Column(Integer, nullable=True)
    tx_count_24h = Column(Integer, nullable=True)

    # Buy/Sell transaction counts (24h)
    buys_24h = Column(Integer, nullable=True)
    sells_24h = Column(Integer, nullable=True)

    # Traders data (24h)
    makers_24h = Column(Integer, nullable=True)  # Total unique makers
    buyers_24h = Column(Integer, nullable=True)  # Total unique buyers
    sellers_24h = Column(Integer, nullable=True)  # Total unique sellers

    # Price range (24h)
    price_24h_high = Column(Numeric(30, 18), nullable=True)
    price_24h_low = Column(Numeric(30, 18), nullable=True)
    open_price_24h = Column(Numeric(30, 18), nullable=True)

    # Token creation info
    token_created_at = Column(DateTime, nullable=True)  # Blockchain creation time
    first_trade_at = Column(DateTime, nullable=True)
    creation_block_number = Column(BigInteger, nullable=True)
    creation_tx_hash = Column(String(66), nullable=True)

    # LP and security info
    lp_holders = Column(Integer, nullable=True)
    lp_locked_percent = Column(Numeric(5, 2), nullable=True)  # LP lock percentage
    lp_lock_platform = Column(String(100), nullable=True)

    # Early trading metrics
    rusher_tx_count = Column(Integer, nullable=True)  # Rush transactions
    sniper_tx_count = Column(Integer, nullable=True)  # Sniper transactions

    # Monitoring status
    status = Column(String(20), nullable=False, default="active")  # active, alerted, stopped

    # Alert settings (can be customized per token)
    drop_threshold_percent = Column(Numeric(5, 2), nullable=False, default=20.0)  # e.g., 20% drop
    alert_thresholds = Column(JSONB, nullable=False, default=[70, 80, 90])  # Custom alert thresholds list [70, 80, 90]

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    stopped_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete timestamp

    # Relationships
    alerts = relationship("PriceAlert", back_populates="monitored_token", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_monitored_status", "status"),
        Index("idx_monitored_entry_time", "entry_timestamp"),
        Index("idx_monitored_token_status", "token_address", "status"),
        Index("idx_monitored_deleted_at", "deleted_at"),
    )

    def __repr__(self):
        return f"<MonitoredToken {self.token_symbol} ({self.status})>"


class PriceAlert(Base):
    """Price alert model - stores triggered alerts when price drops."""

    __tablename__ = "price_alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    monitored_token_id = Column(String(36), ForeignKey("monitored_tokens.id"), nullable=False)

    # Alert trigger info
    alert_type = Column(String(20), nullable=False, default="price_drop")  # price_drop, custom
    triggered_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Price data at alert time
    trigger_price_usd = Column(Numeric(30, 18), nullable=False)
    peak_price_usd = Column(Numeric(30, 18), nullable=False)
    entry_price_usd = Column(Numeric(30, 18), nullable=False)

    # Drop calculations
    drop_from_peak_percent = Column(Numeric(10, 2), nullable=False)  # % drop from peak
    drop_from_entry_percent = Column(Numeric(10, 2), nullable=False)  # % drop from entry

    # Market data at alert time
    market_cap = Column(Numeric(30, 2), nullable=True)
    liquidity_usd = Column(Numeric(30, 2), nullable=True)
    volume_24h = Column(Numeric(30, 2), nullable=True)

    # Alert message
    message = Column(String(500), nullable=True)

    # Alert status
    acknowledged = Column(Integer, nullable=False, default=0)  # 0 = not acknowledged, 1 = acknowledged
    acknowledged_at = Column(DateTime, nullable=True)

    # Severity level
    severity = Column(String(10), nullable=False, default="medium")  # low, medium, high, critical

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    monitored_token = relationship("MonitoredToken", back_populates="alerts")

    # Indexes
    __table_args__ = (
        Index("idx_alert_triggered", "triggered_at"),
        Index("idx_alert_severity", "severity"),
        Index("idx_alert_acknowledged", "acknowledged"),
        Index("idx_alert_token_time", "monitored_token_id", "triggered_at"),
    )

    def __repr__(self):
        return f"<PriceAlert {self.alert_type} -{self.drop_from_peak_percent}% at {self.triggered_at}>"
