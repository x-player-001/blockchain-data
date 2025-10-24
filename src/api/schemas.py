"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class TokenBase(BaseModel):
    """代币基础信息"""
    address: str = Field(..., description="代币合约地址")
    name: str = Field(..., description="代币名称")
    symbol: str = Field(..., description="代币符号")
    decimals: int = Field(18, description="代币精度")

    class Config:
        from_attributes = True


class TokenResponse(TokenBase):
    """代币详情响应"""
    id: str
    total_supply: Optional[str] = Field(None, description="总供应量")
    data_source: Optional[str] = Field(None, description="数据来源")
    created_at: datetime
    updated_at: datetime

    # 市场数据（来自 token_metrics 表的最新数据）
    price_usd: Optional[float] = Field(None, description="当前价格（美元）")
    market_cap: Optional[float] = Field(None, description="市值（美元）")
    liquidity_usd: Optional[float] = Field(None, description="流动性（美元）")
    volume_24h: Optional[float] = Field(None, description="24小时交易量（美元）")
    price_change_24h: Optional[float] = Field(None, description="24小时价格变化（%）")
    holders_count: Optional[int] = Field(None, description="持有者数量")
    metrics_updated_at: Optional[datetime] = Field(None, description="市场数据更新时间")

    # 交易对数据（来自 token_pairs 表）
    pair_address: Optional[str] = Field(None, description="主要交易对地址")
    dex_name: Optional[str] = Field(None, description="DEX名称")
    pair_created_at: Optional[datetime] = Field(None, description="交易对创建时间")

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class TokenListResponse(BaseModel):
    """代币列表响应"""
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    data: List[TokenResponse] = Field(..., description="代币列表")


class OHLCVResponse(BaseModel):
    """OHLCV数据响应"""
    token_id: str
    token_address: str
    timestamp: datetime
    open_price: Optional[float] = Field(None, description="开盘价")
    high_price: Optional[float] = Field(None, description="最高价")
    low_price: Optional[float] = Field(None, description="最低价")
    close_price: Optional[float] = Field(None, description="收盘价")
    volume: Optional[float] = Field(None, description="成交量")
    interval: Optional[str] = Field(None, description="时间间隔")

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float,
            datetime: lambda v: v.isoformat()
        }


class PairResponse(BaseModel):
    """交易对响应"""
    id: str
    pair_address: str
    dex_name: Optional[str]
    base_token: Optional[str]
    liquidity_usd: Optional[float]
    volume_24h: Optional[float]

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class DataSourceStats(BaseModel):
    """数据源统计"""
    source: str = Field(..., description="数据源名称")
    token_count: int = Field(..., description="代币数量")
    ohlcv_count: int = Field(..., description="OHLCV记录数")


class StatsResponse(BaseModel):
    """统计信息响应"""
    total_tokens: int = Field(..., description="总代币数")
    total_ohlcv: int = Field(..., description="总OHLCV记录数")
    sources: List[DataSourceStats] = Field(..., description="各数据源统计")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str = Field(..., description="错误详情")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DexScreenerTokenResponse(BaseModel):
    """DexScreener代币响应"""
    id: str
    chain_id: str = Field(..., description="链ID")
    dex_id: str = Field(..., description="DEX ID")
    pair_address: str = Field(..., description="交易对地址")

    # Token info
    base_token_address: str = Field(..., description="代币地址")
    base_token_name: Optional[str] = Field(None, description="代币名称")
    base_token_symbol: str = Field(..., description="代币符号")

    quote_token_address: Optional[str] = Field(None, description="报价代币地址")
    quote_token_name: Optional[str] = Field(None, description="报价代币名称")
    quote_token_symbol: Optional[str] = Field(None, description="报价代币符号")

    # Prices
    price_native: Optional[float] = Field(None, description="原生代币价格")
    price_usd: Optional[float] = Field(None, description="USD价格")

    # Volumes
    volume_h24: Optional[float] = Field(None, description="24小时交易量")
    volume_h6: Optional[float] = Field(None, description="6小时交易量")
    volume_h1: Optional[float] = Field(None, description="1小时交易量")

    # Transactions
    txns_h24_buys: Optional[int] = Field(None, description="24小时买入次数")
    txns_h24_sells: Optional[int] = Field(None, description="24小时卖出次数")

    # Price changes
    price_change_h24: Optional[float] = Field(None, description="24小时价格变化(%)")
    price_change_h6: Optional[float] = Field(None, description="6小时价格变化(%)")
    price_change_h1: Optional[float] = Field(None, description="1小时价格变化(%)")

    # Market data
    liquidity_usd: Optional[float] = Field(None, description="流动性(USD)")
    market_cap: Optional[float] = Field(None, description="市值")
    fdv: Optional[float] = Field(None, description="完全稀释估值")

    # Additional info
    dexscreener_url: Optional[str] = Field(None, description="DexScreener链接")
    image_url: Optional[str] = Field(None, description="代币图标")
    website_url: Optional[str] = Field(None, description="官网")
    twitter_url: Optional[str] = Field(None, description="Twitter")
    telegram_url: Optional[str] = Field(None, description="Telegram")

    labels: Optional[str] = Field(None, description="标签")
    pair_created_at: Optional[int] = Field(None, description="交易对创建时间")

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float,
            datetime: lambda v: v.isoformat()
        }


class DexScreenerTokenListResponse(BaseModel):
    """DexScreener代币列表响应"""
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    data: List[DexScreenerTokenResponse] = Field(..., description="代币列表")


class PriceSwingResponse(BaseModel):
    """价格波动响应"""
    id: str
    token_id: str = Field(..., description="代币ID")
    token_symbol: Optional[str] = Field(None, description="代币符号")
    token_name: Optional[str] = Field(None, description="代币名称")

    swing_type: str = Field(..., description="波动类型：rise或fall")
    swing_pct: float = Field(..., description="涨跌幅百分比")

    start_time: datetime = Field(..., description="起始时间")
    end_time: datetime = Field(..., description="结束时间")
    duration_hours: float = Field(..., description="持续时长（小时）")

    start_price: float = Field(..., description="起始价格")
    end_price: float = Field(..., description="结束价格")

    min_swing_threshold: Optional[float] = Field(None, description="分析阈值")
    timeframe: Optional[str] = Field(None, description="K线周期")

    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float,
            datetime: lambda v: v.isoformat()
        }


class PriceSwingListResponse(BaseModel):
    """价格波动列表响应"""
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    data: List[PriceSwingResponse] = Field(..., description="波动列表")


class TokenSwingStats(BaseModel):
    """代币波动统计"""
    token_id: str
    token_symbol: str = Field(..., description="代币符号")
    token_name: Optional[str] = Field(None, description="代币名称")

    total_swings: int = Field(..., description="总波动次数")
    rises: int = Field(..., description="上涨次数")
    falls: int = Field(..., description="下跌次数")

    max_rise_pct: Optional[float] = Field(None, description="最大涨幅(%)")
    max_fall_pct: Optional[float] = Field(None, description="最大跌幅(%)")
    avg_duration_hours: Optional[float] = Field(None, description="平均持续时长（小时）")

    # 市场数据
    current_price: Optional[float] = Field(None, description="当前价格")
    liquidity_usd: Optional[float] = Field(None, description="流动性(USD)")
    market_cap: Optional[float] = Field(None, description="市值")

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class TokenSwingStatsListResponse(BaseModel):
    """代币波动统计列表响应"""
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    data: List[TokenSwingStats] = Field(..., description="统计列表")


# ==================== 监控相关 Schemas ====================

class PotentialTokenResponse(BaseModel):
    """潜力代币响应（爬取的 Top Gainers）"""
    # 基础信息
    id: str
    token_address: str = Field(..., description="代币地址")
    token_symbol: str = Field(..., description="代币符号")
    token_name: Optional[str] = Field(None, description="代币名称")
    chain: str = Field(..., description="链名称 (bsc, solana等)")
    dex_id: str = Field(..., description="DEX ID")
    pair_address: str = Field(..., description="交易对地址")
    amm: Optional[str] = Field(None, description="AMM类型")
    dex_type: Optional[str] = Field(None, description="DEX类型 (Solana: CPMM, DLMM等)")

    # 爬取时的价格信息
    scraped_price_usd: float = Field(..., description="爬取时价格(USD)")
    scraped_timestamp: Optional[str] = Field(None, description="爬取时间")

    # 爬取时的市场数据
    market_cap_at_scrape: Optional[float] = Field(None, description="爬取时市值(USD)")
    liquidity_at_scrape: Optional[float] = Field(None, description="爬取时流动性(USD)")
    volume_24h_at_scrape: Optional[float] = Field(None, description="爬取时24h交易量(USD)")
    price_change_24h_at_scrape: Optional[float] = Field(None, description="爬取时24h涨幅(%)")

    # 当前数据（AVE API更新后的最新数据）
    current_price_usd: Optional[float] = Field(None, description="当前价格(USD)")
    price_ath_usd: Optional[float] = Field(None, description="历史最高价(USD)")
    current_tvl: Optional[float] = Field(None, description="当前TVL(USD)")
    current_market_cap: Optional[float] = Field(None, description="当前市值(USD)")

    # 时间戳
    token_created_at: Optional[str] = Field(None, description="代币创建时间")
    first_trade_at: Optional[str] = Field(None, description="首次交易时间")
    last_ave_update: Optional[str] = Field(None, description="AVE数据最后更新时间")

    # 价格变化（多时间段）
    price_change_1m: Optional[float] = Field(None, description="1分钟价格变化(%)")
    price_change_5m: Optional[float] = Field(None, description="5分钟价格变化(%)")
    price_change_15m: Optional[float] = Field(None, description="15分钟价格变化(%)")
    price_change_30m: Optional[float] = Field(None, description="30分钟价格变化(%)")
    price_change_1h: Optional[float] = Field(None, description="1小时价格变化(%)")
    price_change_4h: Optional[float] = Field(None, description="4小时价格变化(%)")
    price_change_24h: Optional[float] = Field(None, description="24小时价格变化(%)")

    # 交易量（多时间段）
    volume_1m: Optional[float] = Field(None, description="1分钟交易量(USD)")
    volume_5m: Optional[float] = Field(None, description="5分钟交易量(USD)")
    volume_15m: Optional[float] = Field(None, description="15分钟交易量(USD)")
    volume_30m: Optional[float] = Field(None, description="30分钟交易量(USD)")
    volume_1h: Optional[float] = Field(None, description="1小时交易量(USD)")
    volume_4h: Optional[float] = Field(None, description="4小时交易量(USD)")
    volume_24h: Optional[float] = Field(None, description="24小时交易量(USD)")

    # 交易次数（多时间段）
    tx_count_1m: Optional[int] = Field(None, description="1分钟交易次数")
    tx_count_5m: Optional[int] = Field(None, description="5分钟交易次数")
    tx_count_15m: Optional[int] = Field(None, description="15分钟交易次数")
    tx_count_30m: Optional[int] = Field(None, description="30分钟交易次数")
    tx_count_1h: Optional[int] = Field(None, description="1小时交易次数")
    tx_count_4h: Optional[int] = Field(None, description="4小时交易次数")
    tx_count_24h: Optional[int] = Field(None, description="24小时交易次数")

    # 买卖数据
    buys_24h: Optional[int] = Field(None, description="24小时买入次数")
    sells_24h: Optional[int] = Field(None, description="24小时卖出次数")

    # 交易者数据
    makers_24h: Optional[int] = Field(None, description="24小时做市商数量")
    buyers_24h: Optional[int] = Field(None, description="24小时买家数量")
    sellers_24h: Optional[int] = Field(None, description="24小时卖家数量")

    # 24小时价格范围
    price_24h_high: Optional[float] = Field(None, description="24小时最高价(USD)")
    price_24h_low: Optional[float] = Field(None, description="24小时最低价(USD)")
    open_price_24h: Optional[float] = Field(None, description="24小时开盘价(USD)")

    # LP信息
    lp_holders: Optional[int] = Field(None, description="LP持有人数量")
    lp_locked_percent: Optional[float] = Field(None, description="LP锁仓比例(%)")
    lp_lock_platform: Optional[str] = Field(None, description="LP锁仓平台")

    # 安全指标
    rusher_tx_count: Optional[int] = Field(None, description="Rush交易数量")
    sniper_tx_count: Optional[int] = Field(None, description="Sniper交易数量")

    # Token创建信息
    creation_block_number: Optional[int] = Field(None, description="创建区块号")
    creation_tx_hash: Optional[str] = Field(None, description="创建交易哈希")

    # 是否已添加到监控
    is_added_to_monitoring: bool = Field(..., description="是否已添加到监控")
    added_to_monitoring_at: Optional[str] = Field(None, description="添加到监控的时间")

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float,
            datetime: lambda v: v.isoformat()
        }


class PotentialTokenListResponse(BaseModel):
    """潜力代币列表响应"""
    total: int = Field(..., description="总数量")
    data: List[PotentialTokenResponse] = Field(..., description="潜力代币列表")


class AddToMonitoringRequest(BaseModel):
    """添加到监控请求"""
    potential_token_id: str = Field(..., description="潜力代币ID")
    drop_threshold_percent: Optional[float] = Field(20.0, description="跌幅报警阈值(%)")


class MonitoredTokenResponse(BaseModel):
    """监控代币响应（包含完整AVE API数据）"""
    # 基础信息
    id: str
    token_address: str = Field(..., description="代币地址")
    token_symbol: str = Field(..., description="代币符号")
    token_name: Optional[str] = Field(None, description="代币名称")
    chain: str = Field(..., description="链名称 (bsc, solana等)")
    dex_id: str = Field(..., description="DEX ID")
    pair_address: str = Field(..., description="交易对地址")
    amm: Optional[str] = Field(None, description="AMM类型")
    dex_type: Optional[str] = Field(None, description="DEX类型 (Solana: CPMM, DLMM等)")

    # 价格信息
    entry_price_usd: float = Field(..., description="入场价格(USD)")
    current_price_usd: Optional[float] = Field(None, description="当前价格(USD)")
    peak_price_usd: float = Field(..., description="监控期间最高价格(USD)")
    price_ath_usd: Optional[float] = Field(None, description="历史最高价(USD, 区块链数据)")

    # 计算字段（从峰值到当前）
    drop_from_peak_percent: Optional[float] = Field(None, description="从峰值到当前的跌幅(%)")
    multiplier_to_peak: Optional[float] = Field(None, description="从当前价到峰值需要涨的倍数")

    # 时间戳
    entry_timestamp: Optional[str] = Field(None, description="入场时间")
    last_update_timestamp: Optional[str] = Field(None, description="最后更新时间")
    peak_timestamp: Optional[str] = Field(None, description="监控期间最高价时间")
    token_created_at: Optional[str] = Field(None, description="代币创建时间")
    first_trade_at: Optional[str] = Field(None, description="首次交易时间")

    # 市场数据
    current_tvl: Optional[float] = Field(None, description="当前TVL(USD)")
    current_market_cap: Optional[float] = Field(None, description="当前市值(USD)")
    market_cap_at_entry: Optional[float] = Field(None, description="入场时市值(USD)")
    liquidity_at_entry: Optional[float] = Field(None, description="入场时流动性(USD)")
    volume_24h_at_entry: Optional[float] = Field(None, description="入场时24h交易量(USD)")
    price_change_24h_at_entry: Optional[float] = Field(None, description="入场时24h涨幅(%)")

    # 价格变化（多时间段）
    price_change_1m: Optional[float] = Field(None, description="1分钟价格变化(%)")
    price_change_5m: Optional[float] = Field(None, description="5分钟价格变化(%)")
    price_change_15m: Optional[float] = Field(None, description="15分钟价格变化(%)")
    price_change_30m: Optional[float] = Field(None, description="30分钟价格变化(%)")
    price_change_1h: Optional[float] = Field(None, description="1小时价格变化(%)")
    price_change_4h: Optional[float] = Field(None, description="4小时价格变化(%)")
    price_change_24h: Optional[float] = Field(None, description="24小时价格变化(%)")

    # 交易量（多时间段）
    volume_1m: Optional[float] = Field(None, description="1分钟交易量(USD)")
    volume_5m: Optional[float] = Field(None, description="5分钟交易量(USD)")
    volume_15m: Optional[float] = Field(None, description="15分钟交易量(USD)")
    volume_30m: Optional[float] = Field(None, description="30分钟交易量(USD)")
    volume_1h: Optional[float] = Field(None, description="1小时交易量(USD)")
    volume_4h: Optional[float] = Field(None, description="4小时交易量(USD)")
    volume_24h: Optional[float] = Field(None, description="24小时交易量(USD)")

    # 交易次数（多时间段）
    tx_count_1m: Optional[int] = Field(None, description="1分钟交易次数")
    tx_count_5m: Optional[int] = Field(None, description="5分钟交易次数")
    tx_count_15m: Optional[int] = Field(None, description="15分钟交易次数")
    tx_count_30m: Optional[int] = Field(None, description="30分钟交易次数")
    tx_count_1h: Optional[int] = Field(None, description="1小时交易次数")
    tx_count_4h: Optional[int] = Field(None, description="4小时交易次数")
    tx_count_24h: Optional[int] = Field(None, description="24小时交易次数")

    # 买卖数据
    buys_24h: Optional[int] = Field(None, description="24小时买入次数")
    sells_24h: Optional[int] = Field(None, description="24小时卖出次数")

    # 交易者数据
    makers_24h: Optional[int] = Field(None, description="24小时做市商数量")
    buyers_24h: Optional[int] = Field(None, description="24小时买家数量")
    sellers_24h: Optional[int] = Field(None, description="24小时卖家数量")

    # 24小时价格范围
    price_24h_high: Optional[float] = Field(None, description="24小时最高价(USD)")
    price_24h_low: Optional[float] = Field(None, description="24小时最低价(USD)")
    open_price_24h: Optional[float] = Field(None, description="24小时开盘价(USD)")

    # LP信息
    lp_holders: Optional[int] = Field(None, description="LP持有人数量")
    lp_locked_percent: Optional[float] = Field(None, description="LP锁仓比例(%)")
    lp_lock_platform: Optional[str] = Field(None, description="LP锁仓平台")

    # 安全指标
    rusher_tx_count: Optional[int] = Field(None, description="Rush交易数量")
    sniper_tx_count: Optional[int] = Field(None, description="Sniper交易数量")

    # Token创建信息
    creation_block_number: Optional[int] = Field(None, description="创建区块号")
    creation_tx_hash: Optional[str] = Field(None, description="创建交易哈希")

    # 监控状态
    status: str = Field(..., description="状态: active/alerted/stopped")
    drop_threshold_percent: float = Field(..., description="跌幅报警阈值(%)")
    alert_thresholds: List[float] = Field(default=[70, 80, 90], description="自定义报警阈值列表，如[70, 80, 90]表示跌70%、80%、90%时报警")

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float,
            datetime: lambda v: v.isoformat()
        }


class MonitoredTokenListResponse(BaseModel):
    """监控代币列表响应"""
    total: int = Field(..., description="总数量")
    data: List[MonitoredTokenResponse] = Field(..., description="监控代币列表")


class UpdateAlertThresholdsRequest(BaseModel):
    """更新报警阈值请求"""
    alert_thresholds: List[float] = Field(..., description="自定义报警阈值列表，如[70, 80, 90]", min_items=1)

    class Config:
        json_schema_extra = {
            "example": {
                "alert_thresholds": [70, 80, 90]
            }
        }


class PriceAlertResponse(BaseModel):
    """价格报警响应"""
    id: str
    token_symbol: str = Field(..., description="代币符号")
    token_address: Optional[str] = Field(None, description="代币地址")

    alert_type: str = Field(..., description="报警类型")
    triggered_at: datetime = Field(..., description="触发时间")

    trigger_price_usd: float = Field(..., description="触发价格(USD)")
    peak_price_usd: float = Field(..., description="峰值价格(USD)")
    entry_price_usd: float = Field(..., description="入场价格(USD)")

    drop_from_peak_percent: float = Field(..., description="距峰值跌幅(%)")
    drop_from_entry_percent: float = Field(..., description="距入场跌幅(%)")

    message: Optional[str] = Field(None, description="报警消息")
    severity: str = Field(..., description="严重程度: low/medium/high/critical")
    acknowledged: bool = Field(..., description="是否已确认")

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float,
            datetime: lambda v: v.isoformat()
        }


class PriceAlertListResponse(BaseModel):
    """价格报警列表响应"""
    total: int = Field(..., description="总数量")
    data: List[PriceAlertResponse] = Field(..., description="报警列表")


class ScrapeTopGainersRequest(BaseModel):
    """抓取涨幅榜请求"""
    count: int = Field(100, ge=10, le=500, description="抓取数量")
    top_n: int = Field(10, ge=1, le=50, description="取前N名")
    drop_threshold: float = Field(20.0, ge=5.0, le=50.0, description="跌幅报警阈值(%)")
    headless: bool = Field(True, description="是否无头浏览器模式")


class ScrapeTopGainersResponse(BaseModel):
    """抓取涨幅榜响应"""
    scraped: int = Field(..., description="已抓取数量")
    detailed: int = Field(..., description="获取详情数量")
    top_gainers: int = Field(..., description="涨幅榜数量")
    added_to_monitor: int = Field(..., description="已添加监控数量")


class UpdateMonitoredPricesResponse(BaseModel):
    """更新监控价格响应"""
    updated: int = Field(..., description="已更新数量")
    alerts_triggered: int = Field(..., description="触发报警数量")
    total_monitored: int = Field(..., description="总监控数量")
