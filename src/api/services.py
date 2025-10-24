"""
Service layer for API endpoints.
Handles business logic and database queries.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.storage.db_manager import DatabaseManager
from src.storage.models import Token, TokenOHLCV, TokenPair, TokenMetrics, DexScreenerToken
from src.api.schemas import (
    TokenResponse,
    TokenListResponse,
    OHLCVResponse,
    StatsResponse,
    DataSourceStats,
    DexScreenerTokenResponse,
    DexScreenerTokenListResponse,
    PriceSwingResponse,
    PriceSwingListResponse,
    TokenSwingStats,
    TokenSwingStatsListResponse
)
from sqlalchemy import text

logger = logging.getLogger(__name__)

# 全局数据库管理器实例
db_manager = DatabaseManager()


async def initialize_db():
    """初始化数据库连接"""
    await db_manager.init_async_db()


async def _get_latest_metrics(session: AsyncSession, token_id: str) -> Optional[Dict[str, Any]]:
    """
    获取代币的最新市场数据

    Args:
        session: 数据库会话
        token_id: 代币ID

    Returns:
        最新的市场数据字典，如果没有则返回 None
    """
    # 查询该代币最新的 metrics 记录
    query = select(TokenMetrics).where(
        TokenMetrics.token_id == token_id
    ).order_by(desc(TokenMetrics.timestamp)).limit(1)

    result = await session.execute(query)
    metrics = result.scalar_one_or_none()

    if not metrics:
        return None

    return {
        "price_usd": float(metrics.price_usd) if metrics.price_usd else None,
        "market_cap": float(metrics.market_cap) if metrics.market_cap else None,
        "liquidity_usd": float(metrics.liquidity_usd) if metrics.liquidity_usd else None,
        "volume_24h": float(metrics.volume_24h) if metrics.volume_24h else None,
        "price_change_24h": float(metrics.price_change_24h) if metrics.price_change_24h else None,
        "holders_count": metrics.holders_count,
        "metrics_updated_at": metrics.timestamp
    }


async def _get_main_pair(session: AsyncSession, token_id: str) -> Optional[Dict[str, Any]]:
    """
    获取代币的主要交易对信息

    Args:
        session: 数据库会话
        token_id: 代币ID

    Returns:
        交易对信息字典，如果没有则返回 None
    """
    # 查询该代币的第一个交易对（通常是主要交易对）
    query = select(TokenPair).where(
        TokenPair.token_id == token_id
    ).limit(1)

    result = await session.execute(query)
    pair = result.scalar_one_or_none()

    if not pair:
        return None

    return {
        "pair_address": pair.pair_address,
        "dex_name": pair.dex_name,
        "pair_created_at": pair.pair_created_at
    }


async def get_tokens(
    page: int = 1,
    page_size: int = 20,
    data_source: Optional[str] = None,
    min_market_cap: Optional[float] = None,
    symbol: Optional[str] = None
) -> TokenListResponse:
    """
    获取代币列表（分页）

    Args:
        page: 页码
        page_size: 每页数量
        data_source: 数据源过滤
        min_market_cap: 最小市值
        symbol: 代币符号

    Returns:
        TokenListResponse
    """
    async with db_manager.get_session() as session:
        # 构建查询
        query = select(Token)

        # 应用过滤条件
        if data_source:
            query = query.where(Token.data_source == data_source)

        if symbol:
            query = query.where(Token.symbol.ilike(f"%{symbol}%"))

        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await session.scalar(count_query)

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # 按更新时间降序排序
        query = query.order_by(desc(Token.updated_at))

        # 执行查询
        result = await session.execute(query)
        tokens = result.scalars().all()

        # 转换为响应模型，并附加最新的市场数据和交易对信息
        token_responses = []
        for token in tokens:
            # 获取最新的市场数据
            metrics = await _get_latest_metrics(session, token.id)

            # 获取主要交易对信息
            pair_info = await _get_main_pair(session, token.id)

            token_data = {
                "id": token.id,
                "address": token.address,
                "name": token.name,
                "symbol": token.symbol,
                "decimals": token.decimals,
                "total_supply": str(token.total_supply) if token.total_supply else None,
                "data_source": token.data_source,
                "created_at": token.created_at,
                "updated_at": token.updated_at
            }

            # 如果有市场数据，添加到响应中
            if metrics:
                token_data.update(metrics)

            # 如果有交易对信息，添加到响应中
            if pair_info:
                token_data.update(pair_info)

            token_responses.append(TokenResponse(**token_data))

        return TokenListResponse(
            total=total or 0,
            page=page,
            page_size=page_size,
            data=token_responses
        )


async def get_token_by_address(address: str) -> Optional[TokenResponse]:
    """
    根据地址获取代币详情

    Args:
        address: 代币地址

    Returns:
        TokenResponse 或 None
    """
    async with db_manager.get_session() as session:
        query = select(Token).where(func.lower(Token.address) == address.lower())
        result = await session.execute(query)
        token = result.scalar_one_or_none()

        if not token:
            return None

        # 获取最新的市场数据
        metrics = await _get_latest_metrics(session, token.id)

        # 获取主要交易对信息
        pair_info = await _get_main_pair(session, token.id)

        token_data = {
            "id": token.id,
            "address": token.address,
            "name": token.name,
            "symbol": token.symbol,
            "decimals": token.decimals,
            "total_supply": str(token.total_supply) if token.total_supply else None,
            "data_source": token.data_source,
            "created_at": token.created_at,
            "updated_at": token.updated_at
        }

        # 如果有市场数据，添加到响应中
        if metrics:
            token_data.update(metrics)

        # 如果有交易对信息，添加到响应中
        if pair_info:
            token_data.update(pair_info)

        return TokenResponse(**token_data)


async def get_token_ohlcv(
    address: str,
    interval: str = "1d",
    limit: int = 100
) -> List[OHLCVResponse]:
    """
    获取代币的OHLCV数据

    Args:
        address: 代币地址
        interval: 时间间隔
        limit: 返回数量

    Returns:
        OHLCV数据列表
    """
    async with db_manager.get_session() as session:
        # 先获取代币
        token_query = select(Token).where(func.lower(Token.address) == address.lower())
        token_result = await session.execute(token_query)
        token = token_result.scalar_one_or_none()

        if not token:
            return []

        # 查询OHLCV数据
        query = select(TokenOHLCV).where(TokenOHLCV.token_id == token.id)

        if interval:
            query = query.where(TokenOHLCV.timeframe == interval)

        # 按时间戳降序排序，最新的在前
        query = query.order_by(desc(TokenOHLCV.timestamp)).limit(limit)

        result = await session.execute(query)
        ohlcv_records = result.scalars().all()

        # 转换为响应模型
        return [
            OHLCVResponse(
                token_id=record.token_id,
                token_address=token.address,
                timestamp=record.timestamp,
                open_price=float(record.open) if record.open else None,
                high_price=float(record.high) if record.high else None,
                low_price=float(record.low) if record.low else None,
                close_price=float(record.close) if record.close else None,
                volume=float(record.volume) if record.volume else None,
                interval=record.timeframe
            )
            for record in reversed(ohlcv_records)  # 反转顺序，最旧的在前
        ]


async def search_tokens(
    query: str,
    page: int = 1,
    page_size: int = 20
) -> TokenListResponse:
    """
    搜索代币（按名称、符号或地址）

    Args:
        query: 搜索关键词
        page: 页码
        page_size: 每页数量

    Returns:
        TokenListResponse
    """
    async with db_manager.get_session() as session:
        # 构建搜索查询 - 支持名称、符号、地址
        search_query = select(Token).where(
            or_(
                Token.name.ilike(f"%{query}%"),
                Token.symbol.ilike(f"%{query}%"),
                Token.address.ilike(f"%{query}%")
            )
        )

        # 获取总数
        count_query = select(func.count()).select_from(search_query.subquery())
        total = await session.scalar(count_query)

        # 分页
        offset = (page - 1) * page_size
        search_query = search_query.offset(offset).limit(page_size)

        # 按更新时间降序排序
        search_query = search_query.order_by(desc(Token.updated_at))

        # 执行查询
        result = await session.execute(search_query)
        tokens = result.scalars().all()

        # 转换为响应模型，并附加最新的市场数据和交易对信息
        token_responses = []
        for token in tokens:
            # 获取最新的市场数据
            metrics = await _get_latest_metrics(session, token.id)

            # 获取主要交易对信息
            pair_info = await _get_main_pair(session, token.id)

            token_data = {
                "id": token.id,
                "address": token.address,
                "name": token.name,
                "symbol": token.symbol,
                "decimals": token.decimals,
                "total_supply": str(token.total_supply) if token.total_supply else None,
                "data_source": token.data_source,
                "created_at": token.created_at,
                "updated_at": token.updated_at
            }

            # 如果有市场数据，添加到响应中
            if metrics:
                token_data.update(metrics)

            # 如果有交易对信息，添加到响应中
            if pair_info:
                token_data.update(pair_info)

            token_responses.append(TokenResponse(**token_data))

        return TokenListResponse(
            total=total or 0,
            page=page,
            page_size=page_size,
            data=token_responses
        )


async def get_data_source_stats() -> StatsResponse:
    """
    获取数据源统计信息

    Returns:
        StatsResponse
    """
    async with db_manager.get_session() as session:
        # 总代币数
        total_tokens_query = select(func.count(Token.id))
        total_tokens = await session.scalar(total_tokens_query) or 0

        # 总OHLCV记录数
        total_ohlcv_query = select(func.count(TokenOHLCV.id))
        total_ohlcv = await session.scalar(total_ohlcv_query) or 0

        # 按数据源统计
        sources_stats = []

        # 获取所有唯一的数据源
        sources_query = select(Token.data_source).distinct()
        result = await session.execute(sources_query)
        sources = [row[0] for row in result.all() if row[0]]

        for source in sources:
            # 该数据源的代币数
            token_count_query = select(func.count(Token.id)).where(
                Token.data_source == source
            )
            token_count = await session.scalar(token_count_query) or 0

            # 该数据源的OHLCV记录数
            ohlcv_count_query = select(func.count(TokenOHLCV.id)).join(
                Token, TokenOHLCV.token_id == Token.id
            ).where(Token.data_source == source)
            ohlcv_count = await session.scalar(ohlcv_count_query) or 0

            sources_stats.append(
                DataSourceStats(
                    source=source,
                    token_count=token_count,
                    ohlcv_count=ohlcv_count
                )
            )

        return StatsResponse(
            total_tokens=total_tokens,
            total_ohlcv=total_ohlcv,
            sources=sources_stats
        )


async def get_dexscreener_tokens(
    page: int = 1,
    page_size: int = 20,
    chain_id: Optional[str] = None,
    dex_id: Optional[str] = None,
    min_liquidity: Optional[float] = None,
    min_market_cap: Optional[float] = None,
    symbol: Optional[str] = None,
    sort_by: str = "market_cap",
    sort_order: str = "desc"
) -> DexScreenerTokenListResponse:
    """
    获取DexScreener代币列表（分页）

    Args:
        page: 页码
        page_size: 每页数量
        chain_id: 链ID过滤
        dex_id: DEX ID过滤
        min_liquidity: 最小流动性
        min_market_cap: 最小市值
        symbol: 代币符号
        sort_by: 排序字段 (market_cap, liquidity_usd, volume_h24, price_change_h24)
        sort_order: 排序方向 (asc, desc)

    Returns:
        DexScreenerTokenListResponse
    """
    async with db_manager.get_session() as session:
        # 构建查询
        query = select(DexScreenerToken)

        # 应用过滤条件
        if chain_id:
            query = query.where(DexScreenerToken.chain_id == chain_id)

        if dex_id:
            query = query.where(DexScreenerToken.dex_id == dex_id)

        if min_liquidity:
            query = query.where(DexScreenerToken.liquidity_usd >= min_liquidity)

        if min_market_cap:
            query = query.where(DexScreenerToken.market_cap >= min_market_cap)

        if symbol:
            query = query.where(DexScreenerToken.base_token_symbol.ilike(f"%{symbol}%"))

        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await session.scalar(count_query)

        # 排序
        sort_column = getattr(DexScreenerToken, sort_by, DexScreenerToken.market_cap)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # 执行查询
        result = await session.execute(query)
        tokens = result.scalars().all()

        # 转换为响应模型
        token_responses = []
        for token in tokens:
            token_responses.append(
                DexScreenerTokenResponse(
                    id=token.id,
                    chain_id=token.chain_id,
                    dex_id=token.dex_id,
                    pair_address=token.pair_address,
                    base_token_address=token.base_token_address,
                    base_token_name=token.base_token_name,
                    base_token_symbol=token.base_token_symbol,
                    quote_token_address=token.quote_token_address,
                    quote_token_name=token.quote_token_name,
                    quote_token_symbol=token.quote_token_symbol,
                    price_native=float(token.price_native) if token.price_native else None,
                    price_usd=float(token.price_usd) if token.price_usd else None,
                    volume_h24=float(token.volume_h24) if token.volume_h24 else None,
                    volume_h6=float(token.volume_h6) if token.volume_h6 else None,
                    volume_h1=float(token.volume_h1) if token.volume_h1 else None,
                    txns_h24_buys=token.txns_h24_buys,
                    txns_h24_sells=token.txns_h24_sells,
                    price_change_h24=float(token.price_change_h24) if token.price_change_h24 else None,
                    price_change_h6=float(token.price_change_h6) if token.price_change_h6 else None,
                    price_change_h1=float(token.price_change_h1) if token.price_change_h1 else None,
                    liquidity_usd=float(token.liquidity_usd) if token.liquidity_usd else None,
                    market_cap=float(token.market_cap) if token.market_cap else None,
                    fdv=float(token.fdv) if token.fdv else None,
                    dexscreener_url=token.dexscreener_url,
                    image_url=token.image_url,
                    website_url=token.website_url,
                    twitter_url=token.twitter_url,
                    telegram_url=token.telegram_url,
                    labels=token.labels,
                    pair_created_at=token.pair_created_at,
                    created_at=token.created_at,
                    updated_at=token.updated_at
                )
            )

        return DexScreenerTokenListResponse(
            total=total or 0,
            page=page,
            page_size=page_size,
            data=token_responses
        )


async def get_dexscreener_token_by_pair(pair_address: str) -> Optional[DexScreenerTokenResponse]:
    """
    根据交易对地址获取DexScreener代币详情

    Args:
        pair_address: 交易对地址

    Returns:
        DexScreenerTokenResponse 或 None
    """
    async with db_manager.get_session() as session:
        query = select(DexScreenerToken).where(
            func.lower(DexScreenerToken.pair_address) == pair_address.lower()
        )
        result = await session.execute(query)
        token = result.scalar_one_or_none()

        if not token:
            return None

        return DexScreenerTokenResponse(
            id=token.id,
            chain_id=token.chain_id,
            dex_id=token.dex_id,
            pair_address=token.pair_address,
            base_token_address=token.base_token_address,
            base_token_name=token.base_token_name,
            base_token_symbol=token.base_token_symbol,
            quote_token_address=token.quote_token_address,
            quote_token_name=token.quote_token_name,
            quote_token_symbol=token.quote_token_symbol,
            price_native=float(token.price_native) if token.price_native else None,
            price_usd=float(token.price_usd) if token.price_usd else None,
            volume_h24=float(token.volume_h24) if token.volume_h24 else None,
            volume_h6=float(token.volume_h6) if token.volume_h6 else None,
            volume_h1=float(token.volume_h1) if token.volume_h1 else None,
            txns_h24_buys=token.txns_h24_buys,
            txns_h24_sells=token.txns_h24_sells,
            price_change_h24=float(token.price_change_h24) if token.price_change_h24 else None,
            price_change_h6=float(token.price_change_h6) if token.price_change_h6 else None,
            price_change_h1=float(token.price_change_h1) if token.price_change_h1 else None,
            liquidity_usd=float(token.liquidity_usd) if token.liquidity_usd else None,
            market_cap=float(token.market_cap) if token.market_cap else None,
            fdv=float(token.fdv) if token.fdv else None,
            dexscreener_url=token.dexscreener_url,
            image_url=token.image_url,
            website_url=token.website_url,
            twitter_url=token.twitter_url,
            telegram_url=token.telegram_url,
            labels=token.labels,
            pair_created_at=token.pair_created_at,
            created_at=token.created_at,
            updated_at=token.updated_at
        )


async def search_dexscreener_tokens(
    query: str,
    page: int = 1,
    page_size: int = 20
) -> DexScreenerTokenListResponse:
    """
    搜索DexScreener代币（按名称、符号或地址）

    Args:
        query: 搜索关键词
        page: 页码
        page_size: 每页数量

    Returns:
        DexScreenerTokenListResponse
    """
    async with db_manager.get_session() as session:
        # 构建搜索查询 - 支持名称、符号、地址
        search_query = select(DexScreenerToken).where(
            or_(
                DexScreenerToken.base_token_name.ilike(f"%{query}%"),
                DexScreenerToken.base_token_symbol.ilike(f"%{query}%"),
                DexScreenerToken.base_token_address.ilike(f"%{query}%"),
                DexScreenerToken.pair_address.ilike(f"%{query}%")
            )
        )

        # 获取总数
        count_query = select(func.count()).select_from(search_query.subquery())
        total = await session.scalar(count_query)

        # 分页
        offset = (page - 1) * page_size
        search_query = search_query.offset(offset).limit(page_size)

        # 按市值降序排序
        search_query = search_query.order_by(desc(DexScreenerToken.market_cap))

        # 执行查询
        result = await session.execute(search_query)
        tokens = result.scalars().all()

        # 转换为响应模型
        token_responses = []
        for token in tokens:
            token_responses.append(
                DexScreenerTokenResponse(
                    id=token.id,
                    chain_id=token.chain_id,
                    dex_id=token.dex_id,
                    pair_address=token.pair_address,
                    base_token_address=token.base_token_address,
                    base_token_name=token.base_token_name,
                    base_token_symbol=token.base_token_symbol,
                    quote_token_address=token.quote_token_address,
                    quote_token_name=token.quote_token_name,
                    quote_token_symbol=token.quote_token_symbol,
                    price_native=float(token.price_native) if token.price_native else None,
                    price_usd=float(token.price_usd) if token.price_usd else None,
                    volume_h24=float(token.volume_h24) if token.volume_h24 else None,
                    volume_h6=float(token.volume_h6) if token.volume_h6 else None,
                    volume_h1=float(token.volume_h1) if token.volume_h1 else None,
                    txns_h24_buys=token.txns_h24_buys,
                    txns_h24_sells=token.txns_h24_sells,
                    price_change_h24=float(token.price_change_h24) if token.price_change_h24 else None,
                    price_change_h6=float(token.price_change_h6) if token.price_change_h6 else None,
                    price_change_h1=float(token.price_change_h1) if token.price_change_h1 else None,
                    liquidity_usd=float(token.liquidity_usd) if token.liquidity_usd else None,
                    market_cap=float(token.market_cap) if token.market_cap else None,
                    fdv=float(token.fdv) if token.fdv else None,
                    dexscreener_url=token.dexscreener_url,
                    image_url=token.image_url,
                    website_url=token.website_url,
                    twitter_url=token.twitter_url,
                    telegram_url=token.telegram_url,
                    labels=token.labels,
                    pair_created_at=token.pair_created_at,
                    created_at=token.created_at,
                    updated_at=token.updated_at
                )
            )

        return DexScreenerTokenListResponse(
            total=total or 0,
            page=page,
            page_size=page_size,
            data=token_responses
        )


# ==================== Price Swings API ====================

async def get_price_swings(
    page: int = 1,
    page_size: int = 20,
    token_id: Optional[str] = None,
    symbol: Optional[str] = None,
    swing_type: Optional[str] = None,
    min_swing_pct: Optional[float] = None,
    sort_by: str = "start_time",
    sort_order: str = "desc"
) -> PriceSwingListResponse:
    """
    获取价格波动列表

    Args:
        page: 页码
        page_size: 每页数量
        token_id: 代币ID过滤
        symbol: 代币符号过滤
        swing_type: 波动类型过滤 (rise/fall)
        min_swing_pct: 最小波动幅度过滤
        sort_by: 排序字段 (start_time, swing_pct, duration_hours)
        sort_order: 排序方向 (asc, desc)

    Returns:
        PriceSwingListResponse
    """
    async with db_manager.get_session() as session:
        # 构建查询
        query_str = """
            SELECT
                ps.id,
                ps.token_id,
                ps.swing_type,
                ps.swing_pct,
                ps.start_time,
                ps.end_time,
                ps.duration_hours,
                ps.start_price,
                ps.end_price,
                ps.min_swing_threshold,
                ps.timeframe,
                ps.created_at,
                d.base_token_symbol as token_symbol,
                d.base_token_name as token_name
            FROM price_swings ps
            LEFT JOIN dexscreener_tokens d ON ps.token_id = d.id
            WHERE 1=1
        """

        params = {}

        # 过滤条件
        if token_id:
            query_str += " AND ps.token_id = :token_id"
            params["token_id"] = token_id

        if symbol:
            query_str += " AND d.base_token_symbol ILIKE :symbol"
            params["symbol"] = f"%{symbol}%"

        if swing_type:
            query_str += " AND ps.swing_type = :swing_type"
            params["swing_type"] = swing_type

        if min_swing_pct is not None:
            query_str += " AND ABS(ps.swing_pct) >= :min_swing_pct"
            params["min_swing_pct"] = min_swing_pct

        # 获取总数
        count_query = f"SELECT COUNT(*) FROM ({query_str}) as subq"
        total_result = await session.execute(text(count_query), params)
        total = total_result.scalar()

        # 排序
        valid_sort_fields = ["start_time", "swing_pct", "duration_hours", "created_at"]
        if sort_by not in valid_sort_fields:
            sort_by = "start_time"

        sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"
        query_str += f" ORDER BY ps.{sort_by} {sort_direction}"

        # 分页
        offset = (page - 1) * page_size
        query_str += " LIMIT :limit OFFSET :offset"
        params["limit"] = page_size
        params["offset"] = offset

        # 执行查询
        result = await session.execute(text(query_str), params)
        rows = result.fetchall()

        # 转换为响应模型
        swing_responses = []
        for row in rows:
            swing_responses.append(
                PriceSwingResponse(
                    id=row.id,
                    token_id=row.token_id,
                    token_symbol=row.token_symbol,
                    token_name=row.token_name,
                    swing_type=row.swing_type,
                    swing_pct=float(row.swing_pct),
                    start_time=row.start_time,
                    end_time=row.end_time,
                    duration_hours=float(row.duration_hours),
                    start_price=float(row.start_price),
                    end_price=float(row.end_price),
                    min_swing_threshold=float(row.min_swing_threshold) if row.min_swing_threshold else None,
                    timeframe=row.timeframe,
                    created_at=row.created_at
                )
            )

        return PriceSwingListResponse(
            total=total or 0,
            page=page,
            page_size=page_size,
            data=swing_responses
        )


async def get_token_swing_stats_list(
    page: int = 1,
    page_size: int = 20,
    min_swings: Optional[int] = None,
    min_liquidity: Optional[float] = None,
    sort_by: str = "total_swings",
    sort_order: str = "desc"
) -> TokenSwingStatsListResponse:
    """
    获取代币波动统计列表

    Args:
        page: 页码
        page_size: 每页数量
        min_swings: 最小波动次数过滤
        min_liquidity: 最小流动性过滤
        sort_by: 排序字段 (total_swings, max_rise_pct, max_fall_pct, liquidity_usd)
        sort_order: 排序方向 (asc, desc)

    Returns:
        TokenSwingStatsListResponse
    """
    async with db_manager.get_session() as session:
        query_str = """
            SELECT
                d.id as token_id,
                d.base_token_symbol as token_symbol,
                d.base_token_name as token_name,
                COUNT(*) as total_swings,
                COUNT(CASE WHEN ps.swing_type = 'rise' THEN 1 END) as rises,
                COUNT(CASE WHEN ps.swing_type = 'fall' THEN 1 END) as falls,
                MAX(CASE WHEN ps.swing_type = 'rise' THEN ps.swing_pct END) as max_rise_pct,
                MIN(CASE WHEN ps.swing_type = 'fall' THEN ps.swing_pct END) as max_fall_pct,
                AVG(ps.duration_hours) as avg_duration_hours,
                d.price_usd as current_price,
                d.liquidity_usd,
                d.market_cap
            FROM price_swings ps
            JOIN dexscreener_tokens d ON ps.token_id = d.id
            WHERE 1=1
        """

        params = {}

        if min_liquidity:
            query_str += " AND d.liquidity_usd >= :min_liquidity"
            params["min_liquidity"] = min_liquidity

        query_str += " GROUP BY d.id, d.base_token_symbol, d.base_token_name, d.price_usd, d.liquidity_usd, d.market_cap"

        if min_swings:
            query_str += " HAVING COUNT(*) >= :min_swings"
            params["min_swings"] = min_swings

        # 获取总数
        count_query = f"SELECT COUNT(*) FROM ({query_str}) as subq"
        total_result = await session.execute(text(count_query), params)
        total = total_result.scalar()

        # 排序
        valid_sort_fields = {
            "total_swings": "total_swings",
            "max_rise_pct": "max_rise_pct",
            "max_fall_pct": "max_fall_pct",
            "liquidity_usd": "liquidity_usd",
            "market_cap": "market_cap"
        }
        sort_field = valid_sort_fields.get(sort_by, "total_swings")
        sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"
        query_str += f" ORDER BY {sort_field} {sort_direction}"

        # 分页
        offset = (page - 1) * page_size
        query_str += " LIMIT :limit OFFSET :offset"
        params["limit"] = page_size
        params["offset"] = offset

        # 执行查询
        result = await session.execute(text(query_str), params)
        rows = result.fetchall()

        # 转换为响应模型
        stats_responses = []
        for row in rows:
            stats_responses.append(
                TokenSwingStats(
                    token_id=row.token_id,
                    token_symbol=row.token_symbol,
                    token_name=row.token_name,
                    total_swings=row.total_swings,
                    rises=row.rises,
                    falls=row.falls,
                    max_rise_pct=float(row.max_rise_pct) if row.max_rise_pct else None,
                    max_fall_pct=float(row.max_fall_pct) if row.max_fall_pct else None,
                    avg_duration_hours=float(row.avg_duration_hours) if row.avg_duration_hours else None,
                    current_price=float(row.current_price) if row.current_price else None,
                    liquidity_usd=float(row.liquidity_usd) if row.liquidity_usd else None,
                    market_cap=float(row.market_cap) if row.market_cap else None
                )
            )

        return TokenSwingStatsListResponse(
            total=total or 0,
            page=page,
            page_size=page_size,
            data=stats_responses
        )


async def get_largest_swings(
    swing_type: str,
    limit: int = 10
) -> List[PriceSwingResponse]:
    """
    获取最大涨幅或跌幅记录

    Args:
        swing_type: 波动类型 (rise/fall)
        limit: 返回数量

    Returns:
        List[PriceSwingResponse]
    """
    async with db_manager.get_session() as session:
        query_str = """
            SELECT
                ps.id,
                ps.token_id,
                ps.swing_type,
                ps.swing_pct,
                ps.start_time,
                ps.end_time,
                ps.duration_hours,
                ps.start_price,
                ps.end_price,
                ps.min_swing_threshold,
                ps.timeframe,
                ps.created_at,
                d.base_token_symbol as token_symbol,
                d.base_token_name as token_name
            FROM price_swings ps
            LEFT JOIN dexscreener_tokens d ON ps.token_id = d.id
            WHERE ps.swing_type = :swing_type
        """

        if swing_type == "rise":
            query_str += " ORDER BY ps.swing_pct DESC"
        else:
            query_str += " ORDER BY ps.swing_pct ASC"

        query_str += " LIMIT :limit"

        result = await session.execute(
            text(query_str),
            {"swing_type": swing_type, "limit": limit}
        )
        rows = result.fetchall()

        swing_responses = []
        for row in rows:
            swing_responses.append(
                PriceSwingResponse(
                    id=row.id,
                    token_id=row.token_id,
                    token_symbol=row.token_symbol,
                    token_name=row.token_name,
                    swing_type=row.swing_type,
                    swing_pct=float(row.swing_pct),
                    start_time=row.start_time,
                    end_time=row.end_time,
                    duration_hours=float(row.duration_hours),
                    start_price=float(row.start_price),
                    end_price=float(row.end_price),
                    min_swing_threshold=float(row.min_swing_threshold) if row.min_swing_threshold else None,
                    timeframe=row.timeframe,
                    created_at=row.created_at
                )
            )

        return swing_responses
