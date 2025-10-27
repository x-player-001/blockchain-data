"""
FastAPI application for blockchain data service.
Provides REST API endpoints for querying token and market data.
"""

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
import logging

from src.api.schemas import (
    TokenResponse,
    TokenListResponse,
    OHLCVResponse,
    StatsResponse,
    PairResponse,
    DexScreenerTokenResponse,
    DexScreenerTokenListResponse,
    PriceSwingResponse,
    PriceSwingListResponse,
    TokenSwingStatsListResponse,
    MonitoredTokenResponse,
    MonitoredTokenListResponse,
    PriceAlertResponse,
    PriceAlertListResponse,
    PotentialTokenResponse,
    PotentialTokenListResponse,
    AddToMonitoringRequest,
    UpdateAlertThresholdsRequest,
    ScrapeTopGainersRequest,
    ScrapeTopGainersResponse,
    UpdateMonitoredPricesResponse
)
from src.api.services import (
    get_tokens,
    get_token_by_address,
    get_token_ohlcv,
    get_data_source_stats,
    search_tokens,
    initialize_db,
    get_dexscreener_tokens,
    get_dexscreener_token_by_pair,
    search_dexscreener_tokens,
    get_price_swings,
    get_token_swing_stats_list,
    get_largest_swings
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    logger.info("Initializing database connection...")
    await initialize_db()
    logger.info("Database initialized successfully")
    yield
    # 关闭时的清理工作（如果需要）
    logger.info("Shutting down...")


# 创建 FastAPI 应用
app = FastAPI(
    title="Blockchain Data API",
    description="REST API for querying BSC token and market data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置 CORS - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """API 根路径"""
    return {
        "name": "Blockchain Data API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "tokens": "/api/tokens",
            "token_detail": "/api/tokens/{address}",
            "ohlcv": "/api/tokens/{address}/ohlcv",
            "search": "/api/search",
            "stats": "/api/stats",
            "dexscreener_tokens": "/api/dexscreener/tokens",
            "price_swings": "/api/price-swings",
            "price_swings_stats": "/api/price-swings/stats",
            "top_rises": "/api/price-swings/top-rises",
            "top_falls": "/api/price-swings/top-falls"
        }
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


@app.get("/api/tokens", response_model=TokenListResponse)
async def list_tokens(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量，最大100"),
    data_source: Optional[str] = Query(None, description="数据来源过滤：ave, legacy等"),
    min_market_cap: Optional[float] = Query(None, description="最小市值（美元）"),
    symbol: Optional[str] = Query(None, description="代币符号过滤")
):
    """
    获取代币列表

    支持分页和多种过滤条件：
    - data_source: 按数据来源过滤
    - min_market_cap: 按最小市值过滤
    - symbol: 按代币符号过滤
    """
    try:
        result = await get_tokens(
            page=page,
            page_size=page_size,
            data_source=data_source,
            min_market_cap=min_market_cap,
            symbol=symbol
        )
        return result
    except Exception as e:
        logger.error(f"Error getting tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tokens/{address}", response_model=TokenResponse)
async def get_token_detail(address: str):
    """
    根据地址获取代币详情

    参数:
    - address: 代币合约地址
    """
    try:
        token = await get_token_by_address(address)
        if not token:
            raise HTTPException(status_code=404, detail=f"Token {address} not found")
        return token
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting token {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tokens/{address}/ohlcv", response_model=List[OHLCVResponse])
async def get_token_klines(
    address: str,
    interval: Optional[str] = Query("1d", description="时间间隔：1h, 4h, 1d等"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量，最大1000")
):
    """
    获取代币的OHLCV（K线）数据

    参数:
    - address: 代币合约地址
    - interval: 时间间隔
    - limit: 返回的K线数量
    """
    try:
        ohlcv_data = await get_token_ohlcv(address, interval, limit)
        if not ohlcv_data:
            raise HTTPException(
                status_code=404,
                detail=f"No OHLCV data found for token {address}"
            )
        return ohlcv_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting OHLCV for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search", response_model=TokenListResponse)
async def search_tokens_endpoint(
    q: str = Query(..., min_length=1, description="搜索关键词：代币名称、符号或地址"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """
    搜索代币

    支持按名称、符号、地址搜索
    """
    try:
        result = await search_tokens(q, page, page_size)
        return result
    except Exception as e:
        logger.error(f"Error searching tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", response_model=StatsResponse)
async def get_statistics():
    """
    获取数据统计信息

    返回各数据源的代币数量、OHLCV记录数等统计信息
    """
    try:
        stats = await get_data_source_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== DexScreener API Endpoints ====================

@app.get("/api/dexscreener/tokens", response_model=DexScreenerTokenListResponse)
async def list_dexscreener_tokens(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量，最大100"),
    chain_id: Optional[str] = Query(None, description="链ID过滤：bsc, eth等"),
    dex_id: Optional[str] = Query(None, description="DEX ID过滤：pancakeswap, uniswap等"),
    min_liquidity: Optional[float] = Query(None, description="最小流动性（美元）"),
    min_market_cap: Optional[float] = Query(None, description="最小市值（美元）"),
    symbol: Optional[str] = Query(None, description="代币符号过滤"),
    sort_by: str = Query("market_cap", description="排序字段：market_cap, liquidity_usd, volume_h24, price_change_h24"),
    sort_order: str = Query("desc", description="排序方向：asc, desc")
):
    """
    获取DexScreener代币列表

    支持分页和多种过滤条件：
    - chain_id: 按链ID过滤
    - dex_id: 按DEX过滤
    - min_liquidity: 按最小流动性过滤
    - min_market_cap: 按最小市值过滤
    - symbol: 按代币符号过滤
    - sort_by: 排序字段
    - sort_order: 排序方向
    """
    try:
        result = await get_dexscreener_tokens(
            page=page,
            page_size=page_size,
            chain_id=chain_id,
            dex_id=dex_id,
            min_liquidity=min_liquidity,
            min_market_cap=min_market_cap,
            symbol=symbol,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return result
    except Exception as e:
        logger.error(f"Error getting dexscreener tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dexscreener/pairs/{pair_address}", response_model=DexScreenerTokenResponse)
async def get_dexscreener_pair_detail(pair_address: str):
    """
    根据交易对地址获取DexScreener代币详情

    参数:
    - pair_address: 交易对地址
    """
    try:
        token = await get_dexscreener_token_by_pair(pair_address)
        if not token:
            raise HTTPException(
                status_code=404,
                detail=f"Pair {pair_address} not found"
            )
        return token
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dexscreener pair {pair_address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dexscreener/search", response_model=DexScreenerTokenListResponse)
async def search_dexscreener_tokens_endpoint(
    q: str = Query(..., min_length=1, description="搜索关键词：代币名称、符号或地址"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """
    搜索DexScreener代币

    支持按名称、符号、地址搜索
    """
    try:
        result = await search_dexscreener_tokens(q, page, page_size)
        return result
    except Exception as e:
        logger.error(f"Error searching dexscreener tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ==================== Price Swings API Endpoints ====================

@app.get("/api/price-swings", response_model=PriceSwingListResponse)
async def list_price_swings(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量，最大100"),
    token_id: Optional[str] = Query(None, description="代币ID过滤"),
    symbol: Optional[str] = Query(None, description="代币符号过滤"),
    swing_type: Optional[str] = Query(None, description="波动类型过滤：rise, fall"),
    min_swing_pct: Optional[float] = Query(None, description="最小波动幅度（百分比）"),
    sort_by: str = Query("start_time", description="排序字段：start_time, swing_pct, duration_hours"),
    sort_order: str = Query("desc", description="排序方向：asc, desc")
):
    """
    获取价格波动列表

    支持多种过滤和排序条件：
    - token_id: 按代币ID过滤
    - symbol: 按代币符号过滤
    - swing_type: 按波动类型过滤（rise/fall）
    - min_swing_pct: 按最小波动幅度过滤
    - sort_by: 排序字段
    - sort_order: 排序方向
    """
    try:
        result = await get_price_swings(
            page=page,
            page_size=page_size,
            token_id=token_id,
            symbol=symbol,
            swing_type=swing_type,
            min_swing_pct=min_swing_pct,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return result
    except Exception as e:
        logger.error(f"Error getting price swings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/price-swings/stats", response_model=TokenSwingStatsListResponse)
async def list_token_swing_stats(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量，最大100"),
    min_swings: Optional[int] = Query(None, description="最小波动次数过滤"),
    min_liquidity: Optional[float] = Query(None, description="最小流动性（美元）"),
    sort_by: str = Query("total_swings", description="排序字段：total_swings, max_rise_pct, max_fall_pct, liquidity_usd"),
    sort_order: str = Query("desc", description="排序方向：asc, desc")
):
    """
    获取代币波动统计列表

    返回每个代币的波动统计信息，包括：
    - 总波动次数
    - 上涨/下跌次数
    - 最大涨幅/跌幅
    - 平均持续时长
    - 当前价格和市场数据
    """
    try:
        result = await get_token_swing_stats_list(
            page=page,
            page_size=page_size,
            min_swings=min_swings,
            min_liquidity=min_liquidity,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return result
    except Exception as e:
        logger.error(f"Error getting token swing stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/price-swings/top-rises", response_model=List[PriceSwingResponse])
async def get_top_rises(
    limit: int = Query(10, ge=1, le=100, description="返回数量，最大100")
):
    """
    获取最大涨幅TOP N

    返回历史上涨幅最大的价格波动记录
    """
    try:
        result = await get_largest_swings(swing_type="rise", limit=limit)
        return result
    except Exception as e:
        logger.error(f"Error getting top rises: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/price-swings/top-falls", response_model=List[PriceSwingResponse])
async def get_top_falls(
    limit: int = Query(10, ge=1, le=100, description="返回数量，最大100")
):
    """
    获取最大跌幅TOP N

    返回历史上跌幅最大的价格波动记录
    """
    try:
        result = await get_largest_swings(swing_type="fall", limit=limit)
        return result
    except Exception as e:
        logger.error(f"Error getting top falls: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 代币监控 API ====================

@app.post("/api/monitor/scrape-top-gainers", response_model=ScrapeTopGainersResponse)
async def scrape_top_gainers(request: ScrapeTopGainersRequest):
    """
    抓取DexScreener首页涨幅榜，添加Top N到监控列表

    流程：
    1. 爬取DexScreener BSC首页指定数量的代币
    2. 按24h涨幅排序，取前N名
    3. 将这些代币添加到监控表中

    Args:
        count: 抓取数量（10-500）
        top_n: 取前N名涨幅榜（1-50）
        drop_threshold: 跌幅报警阈值，默认20%
        headless: 是否使用无头浏览器
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        result = await monitor_service.scrape_and_add_top_gainers(
            count=request.count,
            top_n=request.top_n,
            drop_threshold=request.drop_threshold,
            headless=request.headless
        )
        return ScrapeTopGainersResponse(**result)
    except Exception as e:
        logger.error(f"Error scraping top gainers: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.post("/api/monitor/update-prices", response_model=UpdateMonitoredPricesResponse)
async def update_monitored_prices(
    batch_size: int = Query(10, ge=1, le=50, description="批处理大小"),
    delay: float = Query(0.5, ge=0.1, le=5.0, description="批次间延迟（秒）")
):
    """
    更新所有监控代币的价格，检查并触发报警

    该接口会：
    1. 获取所有active状态的监控代币
    2. 批量获取当前价格
    3. 更新最高价（peak_price）
    4. 计算跌幅，触发报警

    建议使用定时任务定期调用（如每5-10分钟）
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        result = await monitor_service.update_monitored_prices(
            batch_size=batch_size,
            delay=delay
        )
        return UpdateMonitoredPricesResponse(**result)
    except Exception as e:
        logger.error(f"Error updating monitored prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.get("/api/monitor/tokens", response_model=MonitoredTokenListResponse)
async def get_monitored_tokens(
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
    status: Optional[str] = Query(None, description="状态过滤: active/alerted/stopped，不传则返回所有")
):
    """
    获取监控代币列表

    支持按状态过滤：
    - active: 活跃监控中
    - alerted: 已触发报警
    - stopped: 已停止监控
    - 不传status参数: 返回所有状态的代币

    返回包括：
    - 入场价格、当前价格、峰值价格
    - 涨跌幅信息
    - 完整的AVE API数据（60+字段）
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        tokens = await monitor_service.get_monitored_tokens(limit=limit, status=status)
        return MonitoredTokenListResponse(
            total=len(tokens),
            data=tokens
        )
    except Exception as e:
        logger.error(f"Error getting monitored tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.patch("/api/monitor/tokens/{token_id}/thresholds", response_model=MonitoredTokenResponse)
async def update_alert_thresholds(
    token_id: str,
    request: UpdateAlertThresholdsRequest
):
    """
    更新监控代币的报警阈值

    可以为每个代币设置自定义的报警阈值列表，例如：
    - [70, 80, 90]: 在代币从ATH跌70%、80%、90%时触发报警
    - [50, 60, 70]: 自定义更低的阈值
    - [80, 90]: 只在跌80%和90%时报警

    阈值必须是0-100之间的数字，表示从历史最高价(ATH)的跌幅百分比
    """
    from src.services.token_monitor_service import TokenMonitorService
    from src.storage.models import MonitoredToken
    from sqlalchemy import select

    # 验证阈值有效性
    for threshold in request.alert_thresholds:
        if threshold < 0 or threshold > 100:
            raise HTTPException(
                status_code=400,
                detail=f"阈值必须在0-100之间，收到: {threshold}"
            )

    monitor_service = TokenMonitorService()
    try:
        async with monitor_service.db.get_session() as session:
            # 查询代币
            result = await session.execute(
                select(MonitoredToken).where(MonitoredToken.id == token_id)
            )
            token = result.scalar_one_or_none()

            if not token:
                raise HTTPException(status_code=404, detail=f"未找到ID为 {token_id} 的监控代币")

            # 更新阈值
            token.alert_thresholds = request.alert_thresholds
            await session.commit()
            await session.refresh(token)

            # 返回更新后的代币信息
            token_list = monitor_service._format_token_list([token])
            if not token_list:
                raise HTTPException(status_code=500, detail="格式化代币数据失败")

            return token_list[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新报警阈值时出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.get("/api/monitor/alerts", response_model=PriceAlertListResponse)
async def get_price_alerts(
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    acknowledged: Optional[bool] = Query(None, description="是否已确认（true/false/null=全部）"),
    severity: Optional[str] = Query(None, description="严重程度：low/medium/high/critical")
):
    """
    获取价格报警列表

    可筛选：
    - acknowledged: 是否已确认
    - severity: 严重程度

    按触发时间倒序排列
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        alerts = await monitor_service.get_alerts(
            limit=limit,
            acknowledged=acknowledged,
            severity=severity
        )
        return PriceAlertListResponse(
            total=len(alerts),
            data=alerts
        )
    except Exception as e:
        logger.error(f"Error getting price alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


# ==================== 潜力币种相关端点 ====================

@app.get("/api/potential-tokens", response_model=PotentialTokenListResponse)
async def get_potential_tokens(
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
    only_not_added: bool = Query(False, description="仅返回未添加到监控的代币")
):
    """
    获取潜力币种列表（爬取的 Top Gainers）

    - 这些是从 DexScreener 爬取的高涨幅代币
    - 保存了爬取时的价格和24h涨幅
    - 包含完整的 AVE API 数据
    - 可以选择性地添加到监控表

    参数：
    - limit: 返回数量
    - only_not_added: 仅显示未添加到监控的代币
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        tokens = await monitor_service.get_potential_tokens(
            limit=limit,
            only_not_added=only_not_added
        )
        return PotentialTokenListResponse(
            total=len(tokens),
            data=tokens
        )
    except Exception as e:
        logger.error(f"Error getting potential tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.post("/api/monitor/add-from-potential")
async def add_potential_to_monitoring(request: AddToMonitoringRequest):
    """
    从潜力币种添加到监控表

    将一个潜力币种手动添加到监控表，开始进行价格跟踪和报警。

    请求体：
    - potential_token_id: 潜力币种ID
    - drop_threshold_percent: 跌幅报警阈值（默认20%）

    响应：
    - 包含新创建的监控代币信息
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        result = await monitor_service.add_potential_to_monitoring(
            potential_token_id=request.potential_token_id,
            drop_threshold=request.drop_threshold_percent
        )
        return result
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding potential token to monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.delete("/api/potential-tokens/{potential_token_id}")
async def delete_potential_token(potential_token_id: str):
    """
    删除潜力币种

    从潜力币种表中删除一个代币（对不感兴趣的代币进行清理）

    路径参数：
    - potential_token_id: 潜力币种ID
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        result = await monitor_service.delete_potential_token(potential_token_id)
        return result
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting potential token: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.get("/api/potential-tokens/deleted", response_model=PotentialTokenListResponse)
async def get_deleted_potential_tokens(
    limit: int = Query(100, ge=1, le=500, description="返回数量")
):
    """
    获取已删除的潜力代币列表

    返回所有被软删除的潜力代币，按删除时间倒序排列

    路径参数：
    - limit: 返回数量，默认100
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        tokens = await monitor_service.get_deleted_potential_tokens(limit=limit)
        return PotentialTokenListResponse(
            total=len(tokens),
            data=tokens
        )
    except Exception as e:
        logger.error(f"Error getting deleted potential tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.post("/api/potential-tokens/{potential_token_id}/restore")
async def restore_potential_token(potential_token_id: str):
    """
    恢复已删除的潜力代币

    将已软删除的潜力代币恢复到正常状态

    路径参数：
    - potential_token_id: 潜力代币ID
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        result = await monitor_service.restore_potential_token(potential_token_id)
        return result
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error restoring potential token: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.delete("/api/monitor/tokens/{monitored_token_id}")
async def delete_monitored_token(monitored_token_id: str):
    """
    软删除监控代币

    将监控代币标记为已删除（软删除），不会真正从数据库中删除

    路径参数：
    - monitored_token_id: 监控代币ID
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        result = await monitor_service.delete_monitored_token(monitored_token_id)
        return result
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting monitored token: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.get("/api/monitor/tokens/deleted", response_model=MonitoredTokenListResponse)
async def get_deleted_monitored_tokens(
    limit: int = Query(100, ge=1, le=500, description="返回数量")
):
    """
    获取已删除的监控代币列表

    返回所有被软删除的监控代币，按删除时间倒序排列

    路径参数：
    - limit: 返回数量，默认100
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        tokens = await monitor_service.get_deleted_monitored_tokens(limit=limit)
        return MonitoredTokenListResponse(
            total=len(tokens),
            data=tokens
        )
    except Exception as e:
        logger.error(f"Error getting deleted monitored tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.post("/api/monitor/tokens/{monitored_token_id}/restore")
async def restore_monitored_token(monitored_token_id: str):
    """
    恢复已删除的监控代币

    将已软删除的监控代币恢复到正常状态

    路径参数：
    - monitored_token_id: 监控代币ID
    """
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        result = await monitor_service.restore_monitored_token(monitored_token_id)
        return result
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error restoring monitored token: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


# ==================== 爬虫配置 API ====================

@app.get("/api/scraper/config")
async def get_scraper_config():
    """获取爬虫配置"""
    from src.storage.models import ScraperConfig
    from src.storage.db_manager import DatabaseManager
    from sqlalchemy import select

    db = DatabaseManager()
    try:
        async with db.get_session() as session:
            result = await session.execute(select(ScraperConfig).limit(1))
            config = result.scalar_one_or_none()

            if not config:
                return {
                    "top_n_per_chain": 10,
                    "count_per_chain": 100,
                    "scrape_interval_min": 9,
                    "scrape_interval_max": 15,
                    "enabled_chains": ["bsc", "solana"],
                    "use_undetected_chrome": 0,
                    "enabled": 1
                }

            return {
                "id": config.id,
                "top_n_per_chain": config.top_n_per_chain,
                "count_per_chain": config.count_per_chain,
                "scrape_interval_min": config.scrape_interval_min,
                "scrape_interval_max": config.scrape_interval_max,
                "enabled_chains": config.enabled_chains,
                "min_market_cap": float(config.min_market_cap) if config.min_market_cap else None,
                "min_liquidity": float(config.min_liquidity) if config.min_liquidity else None,
                "max_token_age_days": config.max_token_age_days,
                "use_undetected_chrome": config.use_undetected_chrome,
                "enabled": config.enabled,
                "description": config.description
            }
    except Exception as e:
        logger.error(f"Error getting scraper config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/scraper/config")
async def update_scraper_config(
    top_n_per_chain: Optional[int] = Body(None, ge=1, le=50),
    count_per_chain: Optional[int] = Body(None, ge=10, le=500),
    scrape_interval_min: Optional[int] = Body(None, ge=1, le=60),
    scrape_interval_max: Optional[int] = Body(None, ge=1, le=120),
    enabled_chains: Optional[List[str]] = Body(None),
    min_market_cap: Optional[float] = Body(None, ge=0),
    min_liquidity: Optional[float] = Body(None, ge=0),
    max_token_age_days: Optional[int] = Body(None, ge=0),
    use_undetected_chrome: Optional[int] = Body(None, ge=0, le=1),
    enabled: Optional[int] = Body(None, ge=0, le=1),
    description: Optional[str] = Body(None)
):
    """更新爬虫配置（接收 JSON body）

    新增过滤条件：
    - min_market_cap: 最小市值（美元），为空则不过滤
    - min_liquidity: 最小流动性（美元），为空则不过滤
    - max_token_age_days: 最大代币年龄（天），为空则不过滤
    """
    from src.storage.models import ScraperConfig
    from src.storage.db_manager import DatabaseManager
    from sqlalchemy import select
    from datetime import datetime
    import uuid

    if scrape_interval_min and scrape_interval_max and scrape_interval_min > scrape_interval_max:
        raise HTTPException(status_code=400, detail="最小间隔不能大于最大间隔")

    db = DatabaseManager()
    try:
        async with db.get_session() as session:
            result = await session.execute(select(ScraperConfig).limit(1))
            config = result.scalar_one_or_none()

            if not config:
                config = ScraperConfig(id=str(uuid.uuid4()))
                session.add(config)

            if top_n_per_chain is not None:
                config.top_n_per_chain = top_n_per_chain
            if count_per_chain is not None:
                config.count_per_chain = count_per_chain
            if scrape_interval_min is not None:
                config.scrape_interval_min = scrape_interval_min
            if scrape_interval_max is not None:
                config.scrape_interval_max = scrape_interval_max
            if enabled_chains is not None:
                config.enabled_chains = enabled_chains
            if min_market_cap is not None:
                config.min_market_cap = min_market_cap
            if min_liquidity is not None:
                config.min_liquidity = min_liquidity
            if max_token_age_days is not None:
                config.max_token_age_days = max_token_age_days
            if use_undetected_chrome is not None:
                config.use_undetected_chrome = use_undetected_chrome
            if enabled is not None:
                config.enabled = enabled
            if description is not None:
                config.description = description

            config.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(config)

            return {"success": True, "message": "配置已更新"}
    except Exception as e:
        logger.error(f"Error updating scraper config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitor/add-by-pair")
async def add_monitoring_by_pair_address(
    pair_address: str = Body(...),
    chain: str = Body("bsc"),
    drop_threshold: float = Body(20.0, ge=0, le=100),
    alert_thresholds: Optional[str] = Body(None)
):
    """通过 pair 地址手动添加监控代币（接收 JSON body）"""
    from src.services.token_monitor_service import TokenMonitorService

    # 解析 alert_thresholds（支持逗号分隔字符串）
    custom_thresholds = None
    if alert_thresholds:
        try:
            custom_thresholds = [float(t.strip()) for t in alert_thresholds.split(',')]
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="阈值格式错误，应为逗号分隔的数字，如 '70,80,90'")

    monitor_service = TokenMonitorService()
    try:
        result = await monitor_service.add_monitoring_by_pair(
            pair_address=pair_address,
            chain=chain,
            drop_threshold=drop_threshold,
            alert_thresholds=custom_thresholds
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding monitoring by pair: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.delete("/api/monitor/tokens/{token_id}/permanent")
async def permanently_delete_monitored_token(token_id: str):
    """彻底删除监控代币（permanently_deleted=1）"""
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        result = await monitor_service.permanently_delete_monitored_token(token_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error permanently deleting monitored token: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.delete("/api/potential-tokens/{token_id}/permanent")
async def permanently_delete_potential_token(token_id: str):
    """彻底删除潜力代币（permanently_deleted=1）"""
    from src.services.token_monitor_service import TokenMonitorService

    monitor_service = TokenMonitorService()
    try:
        result = await monitor_service.permanently_delete_potential_token(token_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error permanently deleting potential token: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await monitor_service.close()


@app.get("/api/scraper/stats")
async def get_scraper_stats(limit: int = Query(20, ge=1, le=100)):
    """获取爬虫统计信息

    返回：
    - 总运行时长（天数/小时）
    - 成功/失败次数统计
    - 最近一次抓取信息
    - 最近N条抓取历史记录
    """
    from src.storage.models import ScrapeLog
    from src.storage.db_manager import DatabaseManager
    from sqlalchemy import select, func, desc, Integer
    from datetime import datetime

    db = DatabaseManager()
    try:
        async with db.get_session() as session:
            # 1. 总体统计
            total_result = await session.execute(
                select(
                    func.count(ScrapeLog.id).label('total_runs'),
                    func.sum((ScrapeLog.status == 'success').cast(Integer)).label('success_count'),
                    func.sum((ScrapeLog.status == 'failed').cast(Integer)).label('failed_count'),
                    func.sum(ScrapeLog.tokens_saved).label('total_saved'),
                    func.min(ScrapeLog.started_at).label('first_run'),
                    func.max(ScrapeLog.started_at).label('last_run')
                )
            )
            stats = total_result.one()

            # 2. 计算运行时长
            running_days = 0
            running_hours = 0
            if stats.first_run and stats.last_run:
                delta = stats.last_run - stats.first_run
                running_days = delta.days
                running_hours = delta.total_seconds() / 3600

            # 3. 获取最近一次抓取
            latest_result = await session.execute(
                select(ScrapeLog)
                .order_by(desc(ScrapeLog.started_at))
                .limit(1)
            )
            latest_log = latest_result.scalar_one_or_none()

            # 4. 获取最近N条记录
            history_result = await session.execute(
                select(ScrapeLog)
                .order_by(desc(ScrapeLog.started_at))
                .limit(limit)
            )
            history_logs = history_result.scalars().all()

            return {
                "summary": {
                    "total_runs": stats.total_runs or 0,
                    "success_count": stats.success_count or 0,
                    "failed_count": stats.failed_count or 0,
                    "success_rate": round((stats.success_count or 0) / (stats.total_runs or 1) * 100, 2),
                    "total_tokens_saved": stats.total_saved or 0,
                    "running_days": running_days,
                    "running_hours": round(running_hours, 2),
                    "first_run": stats.first_run.isoformat() if stats.first_run else None,
                    "last_run": stats.last_run.isoformat() if stats.last_run else None
                },
                "latest": {
                    "id": latest_log.id if latest_log else None,
                    "started_at": latest_log.started_at.isoformat() if latest_log and latest_log.started_at else None,
                    "status": latest_log.status if latest_log else None,
                    "chain": latest_log.chain if latest_log else None,
                    "tokens_saved": latest_log.tokens_saved if latest_log else 0,
                    "duration_seconds": latest_log.duration_seconds if latest_log else None
                } if latest_log else None,
                "history": [
                    {
                        "id": log.id,
                        "started_at": log.started_at.isoformat(),
                        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                        "duration_seconds": log.duration_seconds,
                        "status": log.status,
                        "chain": log.chain,
                        "tokens_scraped": log.tokens_scraped,
                        "tokens_filtered": log.tokens_filtered,
                        "tokens_saved": log.tokens_saved,
                        "tokens_skipped": log.tokens_skipped,
                        "filter_stats": {
                            "by_market_cap": log.filtered_by_market_cap or 0,
                            "by_liquidity": log.filtered_by_liquidity or 0,
                            "by_age": log.filtered_by_age or 0
                        },
                        "error_message": log.error_message
                    }
                    for log in history_logs
                ]
            }
    except Exception as e:
        logger.error(f"Error getting scraper stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/config")
async def get_monitor_config():
    """获取监控配置"""
    from src.storage.models import MonitorConfig
    from src.storage.db_manager import DatabaseManager
    from sqlalchemy import select

    db = DatabaseManager()
    try:
        async with db.get_session() as session:
            result = await session.execute(select(MonitorConfig).limit(1))
            config = result.scalar_one_or_none()

            if not config:
                # 返回默认配置
                return {
                    "min_monitor_market_cap": None,
                    "min_monitor_liquidity": None,
                    "update_interval_minutes": 5,
                    "enabled": 1,
                    "max_retry_count": 3,
                    "batch_size": 10,
                    "description": None
                }

            return {
                "id": config.id,
                "min_monitor_market_cap": float(config.min_monitor_market_cap) if config.min_monitor_market_cap else None,
                "min_monitor_liquidity": float(config.min_monitor_liquidity) if config.min_monitor_liquidity else None,
                "update_interval_minutes": config.update_interval_minutes,
                "enabled": config.enabled,
                "max_retry_count": config.max_retry_count,
                "batch_size": config.batch_size,
                "description": config.description,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None
            }
    except Exception as e:
        logger.error(f"Error getting monitor config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/monitor/config")
async def update_monitor_config(
    min_monitor_market_cap: Optional[float] = Body(None, ge=0),
    min_monitor_liquidity: Optional[float] = Body(None, ge=0),
    update_interval_minutes: Optional[int] = Body(None, ge=1, le=60),
    enabled: Optional[int] = Body(None, ge=0, le=1),
    max_retry_count: Optional[int] = Body(None, ge=1, le=10),
    batch_size: Optional[int] = Body(None, ge=1, le=100),
    description: Optional[str] = Body(None)
):
    """更新监控配置（接收 JSON body）

    配置说明：
    - min_monitor_market_cap: 最小市值（美元），低于此值自动删除
    - min_monitor_liquidity: 最小流动性（美元），低于此值自动删除
    - update_interval_minutes: 更新间隔（分钟）
    - enabled: 是否启用监控
    - max_retry_count: API调用失败重试次数
    - batch_size: 每批次处理的代币数量
    """
    from src.storage.models import MonitorConfig
    from src.storage.db_manager import DatabaseManager
    from sqlalchemy import select
    from datetime import datetime
    import uuid

    db = DatabaseManager()
    try:
        async with db.get_session() as session:
            result = await session.execute(select(MonitorConfig).limit(1))
            config = result.scalar_one_or_none()

            if not config:
                config = MonitorConfig(id=str(uuid.uuid4()))
                session.add(config)

            if min_monitor_market_cap is not None:
                config.min_monitor_market_cap = min_monitor_market_cap
            if min_monitor_liquidity is not None:
                config.min_monitor_liquidity = min_monitor_liquidity
            if update_interval_minutes is not None:
                config.update_interval_minutes = update_interval_minutes
            if enabled is not None:
                config.enabled = enabled
            if max_retry_count is not None:
                config.max_retry_count = max_retry_count
            if batch_size is not None:
                config.batch_size = batch_size
            if description is not None:
                config.description = description

            config.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(config)

            return {"success": True, "message": "监控配置已更新"}
    except Exception as e:
        logger.error(f"Error updating monitor config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/stats")
async def get_monitor_stats(limit: int = Query(20, ge=1, le=100)):
    """获取监控统计信息

    返回：
    - 总运行时长（天数/小时）
    - 成功/失败次数统计
    - 最近一次监控信息
    - 最近N条监控历史记录
    """
    from src.storage.models import MonitorLog
    from src.storage.db_manager import DatabaseManager
    from sqlalchemy import select, func, desc, Integer
    from datetime import datetime

    db = DatabaseManager()
    try:
        async with db.get_session() as session:
            # 1. 总体统计
            total_result = await session.execute(
                select(
                    func.count(MonitorLog.id).label('total_runs'),
                    func.sum((MonitorLog.status == 'success').cast(Integer)).label('success_count'),
                    func.sum((MonitorLog.status == 'failed').cast(Integer)).label('failed_count'),
                    func.sum(MonitorLog.tokens_updated).label('total_updated'),
                    func.sum(MonitorLog.tokens_auto_removed).label('total_removed'),
                    func.sum(MonitorLog.alerts_triggered).label('total_alerts'),
                    func.min(MonitorLog.started_at).label('first_run'),
                    func.max(MonitorLog.started_at).label('last_run')
                )
            )
            stats = total_result.one()

            # 2. 计算运行时长
            running_days = 0
            running_hours = 0
            if stats.first_run and stats.last_run:
                delta = stats.last_run - stats.first_run
                running_days = delta.days
                running_hours = delta.total_seconds() / 3600

            # 3. 获取最近一次监控
            latest_result = await session.execute(
                select(MonitorLog)
                .order_by(desc(MonitorLog.started_at))
                .limit(1)
            )
            latest_log = latest_result.scalar_one_or_none()

            # 4. 获取最近N条记录
            history_result = await session.execute(
                select(MonitorLog)
                .order_by(desc(MonitorLog.started_at))
                .limit(limit)
            )
            history_logs = history_result.scalars().all()

            return {
                "summary": {
                    "total_runs": stats.total_runs or 0,
                    "success_count": stats.success_count or 0,
                    "failed_count": stats.failed_count or 0,
                    "success_rate": round((stats.success_count or 0) / (stats.total_runs or 1) * 100, 2),
                    "total_tokens_updated": stats.total_updated or 0,
                    "total_tokens_removed": stats.total_removed or 0,
                    "total_alerts_triggered": stats.total_alerts or 0,
                    "running_days": running_days,
                    "running_hours": round(running_hours, 2),
                    "first_run": stats.first_run.isoformat() if stats.first_run else None,
                    "last_run": stats.last_run.isoformat() if stats.last_run else None
                },
                "latest": {
                    "id": latest_log.id if latest_log else None,
                    "started_at": latest_log.started_at.isoformat() if latest_log and latest_log.started_at else None,
                    "completed_at": latest_log.completed_at.isoformat() if latest_log and latest_log.completed_at else None,
                    "duration_seconds": latest_log.duration_seconds if latest_log else None,
                    "status": latest_log.status if latest_log else None,
                    "tokens_monitored": latest_log.tokens_monitored if latest_log else 0,
                    "tokens_updated": latest_log.tokens_updated if latest_log else 0,
                    "tokens_failed": latest_log.tokens_failed if latest_log else 0,
                    "tokens_auto_removed": latest_log.tokens_auto_removed if latest_log else 0,
                    "alerts_triggered": latest_log.alerts_triggered if latest_log else 0,
                    "removal_stats": {
                        "by_market_cap": latest_log.removed_by_market_cap or 0,
                        "by_liquidity": latest_log.removed_by_liquidity or 0,
                        "by_other": latest_log.removed_by_other or 0
                    } if latest_log else {"by_market_cap": 0, "by_liquidity": 0, "by_other": 0}
                } if latest_log else None,
                "history": [
                    {
                        "id": log.id,
                        "started_at": log.started_at.isoformat(),
                        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                        "duration_seconds": log.duration_seconds,
                        "status": log.status,
                        "tokens_monitored": log.tokens_monitored,
                        "tokens_updated": log.tokens_updated,
                        "tokens_failed": log.tokens_failed,
                        "tokens_auto_removed": log.tokens_auto_removed,
                        "alerts_triggered": log.alerts_triggered,
                        "removal_stats": {
                            "by_market_cap": log.removed_by_market_cap or 0,
                            "by_liquidity": log.removed_by_liquidity or 0,
                            "by_other": log.removed_by_other or 0
                        },
                        "error_message": log.error_message
                    }
                    for log in history_logs
                ]
            }
    except Exception as e:
        logger.error(f"Error getting monitor stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
