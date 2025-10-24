"""Database manager module."""
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, select, and_, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from .models import (
    Base, Token, TokenMetrics, TokenPair, TokenOHLCV,
    TokenDeployment, WalletTransaction, EarlyTrade,
    DexScreenerToken, PotentialToken, MonitoredToken, PriceAlert
)
from ..utils.config import config
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            database_url: Database connection URL (PostgreSQL)
        """
        self.database_url = database_url or config.DATABASE_URL
        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.AsyncSessionLocal = None

    def init_db(self):
        """Initialize database (sync)."""
        logger.info(f"Initializing database: {self.database_url}")

        # Create engine
        self.engine = create_engine(self.database_url, echo=False)

        # Create tables
        Base.metadata.create_all(bind=self.engine)

        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info("Database initialized successfully")

    async def init_async_db(self):
        """Initialize PostgreSQL database."""
        logger.info(f"Initializing PostgreSQL database: {self.database_url}")

        # Convert to async URL (postgresql:// -> postgresql+asyncpg://)
        async_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://")

        # Create async engine
        self.async_engine = create_async_engine(async_url, echo=False)

        # Create tables
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")

        # Create async session factory
        self.AsyncSessionLocal = async_sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        logger.info("PostgreSQL database initialized successfully")

    @asynccontextmanager
    async def get_session(self):
        """Get async database session."""
        if not self.AsyncSessionLocal:
            await self.init_async_db()

        async with self.AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()

    async def upsert_token(
        self,
        address: str,
        name: str,
        symbol: str,
        decimals: int = 18,
        total_supply: Optional[int] = None,
        data_source: str = "unknown"
    ) -> Token:
        """
        Insert or update token.

        Args:
            address: Token contract address
            name: Token name
            symbol: Token symbol
            decimals: Token decimals
            total_supply: Total supply
            data_source: Data source (ave, geckoterminal, dexscreener, etc.)

        Returns:
            Token instance
        """
        async with self.get_session() as session:
            # Check if token exists
            result = await session.execute(
                select(Token).where(Token.address == address.lower())
            )
            token = result.scalar_one_or_none()

            if token:
                # Update existing token (don't override data_source if already set)
                token.name = name
                token.symbol = symbol
                token.decimals = decimals
                token.total_supply = total_supply
                token.updated_at = datetime.utcnow()
            else:
                # Create new token
                token = Token(
                    address=address.lower(),
                    name=name,
                    symbol=symbol,
                    decimals=decimals,
                    total_supply=total_supply,
                    data_source=data_source
                )
                session.add(token)

            await session.flush()
            await session.refresh(token)

            logger.debug(f"Upserted token: {symbol} ({address})")
            return token

    async def add_token_metrics(
        self,
        token_id: str,
        price_usd: Optional[float] = None,
        market_cap: Optional[float] = None,
        liquidity_usd: Optional[float] = None,
        volume_24h: Optional[float] = None,
        price_change_24h: Optional[float] = None,
        holders_count: Optional[int] = None,
        transactions_24h: Optional[int] = None,
        source: Optional[str] = None
    ) -> TokenMetrics:
        """
        Add token metrics data point.

        Args:
            token_id: Token ID
            price_usd: Price in USD
            market_cap: Market cap in USD
            liquidity_usd: Liquidity in USD
            volume_24h: 24h volume in USD
            price_change_24h: 24h price change percentage
            holders_count: Number of holders
            transactions_24h: 24h transactions count
            source: Data source ('dexscreener', 'geckoterminal', or 'merged')

        Returns:
            TokenMetrics instance
        """
        async with self.get_session() as session:
            metrics = TokenMetrics(
                token_id=token_id,
                price_usd=price_usd,
                market_cap=market_cap,
                liquidity_usd=liquidity_usd,
                volume_24h=volume_24h,
                price_change_24h=price_change_24h,
                holders_count=holders_count,
                transactions_24h=transactions_24h,
                source=source,
                timestamp=datetime.utcnow()
            )
            session.add(metrics)
            await session.flush()

            logger.debug(f"Added metrics for token {token_id} from source: {source}")
            return metrics

    async def upsert_token_pair(
        self,
        token_id: str,
        dex_name: str,
        pair_address: str,
        base_token: str,
        liquidity_usd: Optional[float] = None,
        volume_24h: Optional[float] = None,
        pair_created_at: Optional[datetime] = None
    ) -> TokenPair:
        """
        Insert or update a token pair.

        Args:
            token_id: Token ID
            dex_name: DEX name (e.g., "PancakeSwap")
            pair_address: Trading pair address
            base_token: Base token symbol (e.g., "WBNB")
            liquidity_usd: Liquidity in USD
            volume_24h: 24h volume in USD
            pair_created_at: When the pair was created on blockchain

        Returns:
            TokenPair instance
        """
        async with self.get_session() as session:
            # Check if pair exists
            result = await session.execute(
                select(TokenPair).where(
                    TokenPair.token_id == token_id,
                    TokenPair.dex_name == dex_name,
                    TokenPair.pair_address == pair_address
                )
            )
            pair = result.scalar_one_or_none()

            if pair:
                # Update existing pair
                pair.base_token = base_token
                pair.liquidity_usd = liquidity_usd
                pair.volume_24h = volume_24h
                if pair_created_at:
                    pair.pair_created_at = pair_created_at
                pair.updated_at = datetime.utcnow()
                logger.debug(f"Updated token pair {pair_address} on {dex_name}")
            else:
                # Create new pair
                pair = TokenPair(
                    token_id=token_id,
                    dex_name=dex_name,
                    pair_address=pair_address,
                    base_token=base_token,
                    liquidity_usd=liquidity_usd,
                    volume_24h=volume_24h,
                    pair_created_at=pair_created_at
                )
                session.add(pair)
                logger.debug(f"Created new token pair {pair_address} on {dex_name}")

            await session.flush()
            return pair

    async def batch_insert_ohlcv(
        self,
        token_id: str,
        pool_address: str,
        timeframe: str,
        ohlcv_data: List[List[float]]
    ) -> int:
        """
        Batch insert OHLCV data.

        Args:
            token_id: Token ID
            pool_address: Pool address
            timeframe: Timeframe (minute, hour, day)
            ohlcv_data: List of [timestamp, open, high, low, close, volume]

        Returns:
            Number of records inserted
        """
        async with self.get_session() as session:
            inserted_count = 0

            for candle in ohlcv_data:
                timestamp_unix, open_price, high, low, close, volume = candle
                timestamp = datetime.fromtimestamp(timestamp_unix)

                # Check if record already exists
                result = await session.execute(
                    select(TokenOHLCV).where(
                        TokenOHLCV.token_id == token_id,
                        TokenOHLCV.pool_address == pool_address,
                        TokenOHLCV.timeframe == timeframe,
                        TokenOHLCV.timestamp == timestamp
                    )
                )
                existing = result.scalar_one_or_none()

                if not existing:
                    ohlcv = TokenOHLCV(
                        token_id=token_id,
                        pool_address=pool_address,
                        timeframe=timeframe,
                        timestamp=timestamp,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume
                    )
                    session.add(ohlcv)
                    inserted_count += 1

            await session.flush()
            logger.info(f"Inserted {inserted_count}/{len(ohlcv_data)} OHLCV records for token {token_id} ({timeframe})")
            return inserted_count

    async def upsert_token_deployment(
        self,
        token_id: str,
        deployer_address: str,
        deploy_tx_hash: str,
        deploy_block: int,
        deploy_timestamp: datetime,
        gas_used: Optional[int] = None,
        gas_price: Optional[int] = None
    ) -> TokenDeployment:
        """
        Insert or update token deployment information.

        Args:
            token_id: Token ID
            deployer_address: Deployer wallet address
            deploy_tx_hash: Deployment transaction hash
            deploy_block: Block number
            deploy_timestamp: Deployment timestamp
            gas_used: Gas used
            gas_price: Gas price in wei

        Returns:
            TokenDeployment instance
        """
        async with self.get_session() as session:
            # Check if exists
            result = await session.execute(
                select(TokenDeployment).where(TokenDeployment.token_id == token_id)
            )
            deployment = result.scalar_one_or_none()

            if deployment:
                # Update existing
                deployment.deployer_address = deployer_address
                deployment.deploy_tx_hash = deploy_tx_hash
                deployment.deploy_block = deploy_block
                deployment.deploy_timestamp = deploy_timestamp
                deployment.gas_used = gas_used
                deployment.gas_price = gas_price
                logger.debug(f"Updated deployment info for token {token_id}")
            else:
                # Create new
                deployment = TokenDeployment(
                    token_id=token_id,
                    deployer_address=deployer_address,
                    deploy_tx_hash=deploy_tx_hash,
                    deploy_block=deploy_block,
                    deploy_timestamp=deploy_timestamp,
                    gas_used=gas_used,
                    gas_price=gas_price
                )
                session.add(deployment)
                logger.debug(f"Created deployment info for token {token_id}")

            await session.flush()
            return deployment

    async def insert_wallet_transaction(
        self,
        tx_hash: str,
        block_number: int,
        timestamp: datetime,
        from_address: str,
        to_address: Optional[str],
        value: int,
        value_usd: Optional[float] = None,
        token_address: Optional[str] = None,
        token_value: Optional[int] = None,
        gas_used: Optional[int] = None,
        gas_price: Optional[int] = None,
        status: Optional[int] = None
    ) -> Optional[WalletTransaction]:
        """
        Insert wallet transaction record.

        Args:
            tx_hash: Transaction hash
            block_number: Block number
            timestamp: Transaction timestamp
            from_address: Sender address
            to_address: Receiver address
            value: BNB value in wei
            value_usd: USD value at time
            token_address: Token contract address (if token transfer)
            token_value: Token amount transferred
            gas_used: Gas used
            gas_price: Gas price in wei
            status: Transaction status (1=success, 0=failed)

        Returns:
            WalletTransaction instance or None if duplicate
        """
        async with self.get_session() as session:
            # Check if exists
            result = await session.execute(
                select(WalletTransaction).where(WalletTransaction.tx_hash == tx_hash)
            )
            existing = result.scalar_one_or_none()

            if existing:
                return None

            # Create new
            tx = WalletTransaction(
                tx_hash=tx_hash,
                block_number=block_number,
                timestamp=timestamp,
                from_address=from_address,
                to_address=to_address,
                value=value,
                value_usd=value_usd,
                token_address=token_address,
                token_value=token_value,
                gas_used=gas_used,
                gas_price=gas_price,
                status=status
            )
            session.add(tx)
            await session.flush()
            return tx

    async def insert_early_trade(
        self,
        token_id: str,
        tx_hash: str,
        block_number: int,
        timestamp: datetime,
        trader_address: str,
        trade_type: str,
        token_amount: int,
        bnb_amount: float,
        price_usd: Optional[float],
        seconds_after_deploy: int
    ) -> Optional[EarlyTrade]:
        """
        Insert early trade record.

        Args:
            token_id: Token ID
            tx_hash: Transaction hash
            block_number: Block number
            timestamp: Trade timestamp
            trader_address: Trader wallet address
            trade_type: 'buy' or 'sell'
            token_amount: Token amount (in wei)
            bnb_amount: BNB amount
            price_usd: Price in USD
            seconds_after_deploy: Seconds after deployment

        Returns:
            EarlyTrade instance or None if duplicate
        """
        async with self.get_session() as session:
            # Check if exists
            result = await session.execute(
                select(EarlyTrade).where(EarlyTrade.tx_hash == tx_hash)
            )
            existing = result.scalar_one_or_none()

            if existing:
                return None

            # Create new
            trade = EarlyTrade(
                token_id=token_id,
                tx_hash=tx_hash,
                block_number=block_number,
                timestamp=timestamp,
                trader_address=trader_address,
                trade_type=trade_type,
                token_amount=token_amount,
                bnb_amount=bnb_amount,
                price_usd=price_usd,
                seconds_after_deploy=seconds_after_deploy
            )
            session.add(trade)
            await session.flush()
            return trade

    async def get_tokens_by_market_cap(
        self,
        min_market_cap: float,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get tokens filtered by minimum market cap.

        Args:
            min_market_cap: Minimum market cap in USD
            limit: Maximum number of results

        Returns:
            List of token dictionaries with latest metrics
        """
        async with self.get_session() as session:
            # Get latest metrics for each token
            query = """
            SELECT
                t.address,
                t.name,
                t.symbol,
                tm.price_usd,
                tm.market_cap,
                tm.liquidity_usd,
                tm.volume_24h,
                tm.price_change_24h,
                tm.timestamp
            FROM tokens t
            INNER JOIN token_metrics tm ON t.id = tm.token_id
            INNER JOIN (
                SELECT token_id, MAX(timestamp) as max_timestamp
                FROM token_metrics
                GROUP BY token_id
            ) latest ON tm.token_id = latest.token_id
                AND tm.timestamp = latest.max_timestamp
            WHERE tm.market_cap >= :min_market_cap
            ORDER BY tm.market_cap DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            result = await session.execute(query, {"min_market_cap": min_market_cap})
            rows = result.fetchall()

            tokens = []
            for row in rows:
                tokens.append({
                    "address": row[0],
                    "name": row[1],
                    "symbol": row[2],
                    "price_usd": float(row[3]) if row[3] else None,
                    "market_cap": float(row[4]) if row[4] else None,
                    "liquidity_usd": float(row[5]) if row[5] else None,
                    "volume_24h": float(row[6]) if row[6] else None,
                    "price_change_24h": float(row[7]) if row[7] else None,
                    "timestamp": row[8]
                })

            logger.info(f"Found {len(tokens)} tokens with market cap >= ${min_market_cap}")
            return tokens

    async def get_token_by_address(self, address: str) -> Optional[Token]:
        """
        Get token by address.

        Args:
            address: Token address

        Returns:
            Token instance or None
        """
        async with self.get_session() as session:
            result = await session.execute(
                select(Token).where(Token.address == address.lower())
            )
            return result.scalar_one_or_none()

    async def close(self):
        """Close database connections."""
        if self.async_engine:
            await self.async_engine.dispose()
        if self.engine:
            self.engine.dispose()

        logger.info("Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()
