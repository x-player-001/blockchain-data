#!/usr/bin/env python3
"""
Token Monitor Service
监控代币价格变化，触发报警
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.db_manager import DatabaseManager
from src.storage.models import MonitoredToken, PriceAlert, DexScreenerToken, PotentialToken, ScraperConfig, MonitorConfig
from src.services.dexscreener_service import DexScreenerService
from src.services.ave_api_service import ave_api_service
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class TokenMonitorService:
    """Token monitoring service for price drop alerts."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize monitor service.

        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self._db_created = False
        self.dex_service = DexScreenerService(db_manager=db_manager)

    async def _ensure_db(self):
        """Ensure database manager is initialized."""
        if self.db_manager is None:
            self.db_manager = DatabaseManager()
            await self.db_manager.init_async_db()
            self._db_created = True

    async def close(self):
        """Close database connection."""
        if self._db_created and self.db_manager:
            await self.db_manager.close()

    def _format_token_list(self, tokens: list) -> List[Dict[str, Any]]:
        """
        Format a list of MonitoredToken objects to dictionaries with all AVE API fields.

        Args:
            tokens: List of MonitoredToken objects

        Returns:
            List of token dictionaries
        """
        return [
            {
                # 基础信息
                "id": token.id,
                "token_address": token.token_address,
                "token_symbol": token.token_symbol,
                "token_name": token.token_name,
                "chain": getattr(token, 'chain', 'bsc'),  # 兼容旧数据
                "dex_id": token.dex_id,
                "pair_address": token.pair_address,
                "amm": token.amm,
                "dex_type": getattr(token, 'dex_type', None),  # 兼容旧数据

                # 价格信息
                "entry_price_usd": float(token.entry_price_usd),
                "current_price_usd": float(token.current_price_usd) if token.current_price_usd else None,
                "peak_price_usd": float(token.peak_price_usd),
                "price_ath_usd": float(token.price_ath_usd) if token.price_ath_usd else None,

                # 计算字段（从历史ATH到当前）
                "drop_from_peak_percent": (
                    float((token.price_ath_usd - token.current_price_usd) / token.price_ath_usd * 100)
                    if token.current_price_usd and token.price_ath_usd and token.price_ath_usd > 0
                    else (
                        float((token.peak_price_usd - token.current_price_usd) / token.peak_price_usd * 100)
                        if token.current_price_usd and token.peak_price_usd > 0 else None
                    )
                ),
                "multiplier_to_peak": (
                    float(token.price_ath_usd / token.current_price_usd)
                    if token.current_price_usd and token.price_ath_usd and token.current_price_usd > 0
                    else (
                        float(token.peak_price_usd / token.current_price_usd)
                        if token.current_price_usd and token.current_price_usd > 0 else None
                    )
                ),

                # 时间戳
                "entry_timestamp": token.entry_timestamp.isoformat() if token.entry_timestamp else None,
                "last_update_timestamp": token.last_update_timestamp.isoformat() if token.last_update_timestamp else None,
                "peak_timestamp": token.peak_timestamp.isoformat() if token.peak_timestamp else None,
                "token_created_at": token.token_created_at.isoformat() if token.token_created_at else None,
                "first_trade_at": token.first_trade_at.isoformat() if token.first_trade_at else None,

                # 市场数据
                "current_tvl": float(token.current_tvl) if token.current_tvl else None,
                "current_market_cap": float(token.current_market_cap) if token.current_market_cap else None,
                "market_cap_at_entry": float(token.market_cap_at_entry) if token.market_cap_at_entry else None,
                "liquidity_at_entry": float(token.liquidity_at_entry) if token.liquidity_at_entry else None,
                "volume_24h_at_entry": float(token.volume_24h_at_entry) if token.volume_24h_at_entry else None,
                "price_change_24h_at_entry": float(token.price_change_24h_at_entry) if token.price_change_24h_at_entry else None,

                # 价格变化（多时间段）
                "price_change_1m": float(token.price_change_1m) if token.price_change_1m else None,
                "price_change_5m": float(token.price_change_5m) if token.price_change_5m else None,
                "price_change_15m": float(token.price_change_15m) if token.price_change_15m else None,
                "price_change_30m": float(token.price_change_30m) if token.price_change_30m else None,
                "price_change_1h": float(token.price_change_1h) if token.price_change_1h else None,
                "price_change_4h": float(token.price_change_4h) if token.price_change_4h else None,
                "price_change_24h": float(token.price_change_24h) if token.price_change_24h else None,

                # 交易量（多时间段）
                "volume_1m": float(token.volume_1m) if token.volume_1m else None,
                "volume_5m": float(token.volume_5m) if token.volume_5m else None,
                "volume_15m": float(token.volume_15m) if token.volume_15m else None,
                "volume_30m": float(token.volume_30m) if token.volume_30m else None,
                "volume_1h": float(token.volume_1h) if token.volume_1h else None,
                "volume_4h": float(token.volume_4h) if token.volume_4h else None,
                "volume_24h": float(token.volume_24h) if token.volume_24h else None,

                # 交易次数（多时间段）
                "tx_count_1m": token.tx_count_1m,
                "tx_count_5m": token.tx_count_5m,
                "tx_count_15m": token.tx_count_15m,
                "tx_count_30m": token.tx_count_30m,
                "tx_count_1h": token.tx_count_1h,
                "tx_count_4h": token.tx_count_4h,
                "tx_count_24h": token.tx_count_24h,

                # 买卖数据
                "buys_24h": token.buys_24h,
                "sells_24h": token.sells_24h,

                # 交易者数据
                "makers_24h": token.makers_24h,
                "buyers_24h": token.buyers_24h,
                "sellers_24h": token.sellers_24h,

                # 24小时价格范围
                "price_24h_high": float(token.price_24h_high) if token.price_24h_high else None,
                "price_24h_low": float(token.price_24h_low) if token.price_24h_low else None,
                "open_price_24h": float(token.open_price_24h) if token.open_price_24h else None,

                # LP信息
                "lp_holders": token.lp_holders,
                "lp_locked_percent": float(token.lp_locked_percent) if token.lp_locked_percent else None,
                "lp_lock_platform": token.lp_lock_platform,

                # 安全指标
                "rusher_tx_count": token.rusher_tx_count,
                "sniper_tx_count": token.sniper_tx_count,

                # Token创建信息
                "creation_block_number": token.creation_block_number,
                "creation_tx_hash": token.creation_tx_hash,

                # 监控状态
                "status": token.status,
                "drop_threshold_percent": float(token.drop_threshold_percent),
                "alert_thresholds": token.alert_thresholds if token.alert_thresholds else [70, 80, 90],
            }
            for token in tokens
        ]

    def _apply_token_filters(
        self,
        tokens: List[Dict[str, Any]],
        filter_config: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        应用代币过滤条件

        Args:
            tokens: 代币列表（DexScreener格式）
            filter_config: 过滤配置

        Returns:
            (过滤后的代币列表, 过滤统计信息)
        """
        min_market_cap = filter_config.get('min_market_cap')
        min_liquidity = filter_config.get('min_liquidity')
        max_token_age_days = filter_config.get('max_token_age_days')

        filtered_tokens = []
        stats = {
            'by_market_cap': 0,
            'by_liquidity': 0,
            'by_age': 0
        }

        current_time = datetime.utcnow()

        for token in tokens:
            # 检查市值
            if min_market_cap is not None:
                market_cap = token.get('fdv') or token.get('marketCap')
                if market_cap is None or float(market_cap) < float(min_market_cap):
                    stats['by_market_cap'] += 1
                    continue

            # 检查流动性
            if min_liquidity is not None:
                liquidity = token.get('liquidity', {}).get('usd')
                if liquidity is None or float(liquidity) < float(min_liquidity):
                    stats['by_liquidity'] += 1
                    continue

            # 检查代币年龄
            if max_token_age_days is not None:
                pair_created_at = token.get('pairCreatedAt')
                if pair_created_at:
                    try:
                        # pairCreatedAt 可能是时间戳（毫秒）
                        created_timestamp = int(pair_created_at) / 1000 if pair_created_at > 1000000000000 else int(pair_created_at)
                        created_time = datetime.fromtimestamp(created_timestamp)
                        age_days = (current_time - created_time).total_seconds() / 86400

                        if age_days > max_token_age_days:
                            stats['by_age'] += 1
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to parse pairCreatedAt: {pair_created_at}, error: {e}")

            # 通过所有过滤条件
            filtered_tokens.append(token)

        return filtered_tokens, stats

    def scrape_and_filter_top_gainers(
        self,
        count: int = 100,
        top_n: int = 10,
        headless: bool = False,
        filter_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        【独立功能1】只负责爬取和筛选Top涨幅代币，不添加到监控表

        Args:
            count: 爬取代币数量
            top_n: 筛选前N名
            headless: 是否使用无头浏览器（建议False以绕过Cloudflare）
            filter_config: 过滤配置 {min_market_cap, min_liquidity, max_token_age_days}

        Returns:
            字典包含：top_gainers（前N名代币列表）和过滤统计信息
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"【爬取筛选】开始爬取并筛选 Top {top_n} 涨幅代币")
        logger.info(f"{'='*60}\n")

        # 一次性从页面解析完整数据
        detailed_tokens = self.dex_service.scrape_bsc_page_with_details(
            target_count=count,
            headless=headless
        )

        if not detailed_tokens:
            logger.warning("未获取到代币数据")
            return {
                "top_gainers": [],
                "scraped_count": 0,
                "filtered_count": 0,
                "filter_stats": {}
            }

        logger.info(f"✓ 已爬取 {len(detailed_tokens)} 个代币（含完整数据）")

        # 过滤出有24h涨幅数据的代币
        tokens_with_change = [
            t for t in detailed_tokens
            if t.get('priceChange', {}).get('h24') is not None
        ]

        logger.info(f"✓ 其中 {len(tokens_with_change)} 个有24h涨幅数据")

        # 【新增】应用过滤条件
        filtered_tokens, filter_stats = self._apply_token_filters(
            tokens_with_change,
            filter_config or {}
        )

        logger.info(f"✓ 过滤后剩余 {len(filtered_tokens)} 个代币")
        if filter_stats:
            logger.info(f"   - 因市值过滤: {filter_stats.get('by_market_cap', 0)} 个")
            logger.info(f"   - 因流动性过滤: {filter_stats.get('by_liquidity', 0)} 个")
            logger.info(f"   - 因年龄过滤: {filter_stats.get('by_age', 0)} 个")

        # 按24h涨幅排序
        sorted_tokens = sorted(
            filtered_tokens,
            key=lambda x: float(x.get('priceChange', {}).get('h24', 0)),
            reverse=True
        )

        top_gainers = sorted_tokens[:top_n]

        logger.info(f"\n{'='*60}")
        logger.info(f"Top {len(top_gainers)} 涨幅榜:")
        logger.info(f"{'='*60}")
        for idx, token in enumerate(top_gainers, 1):
            symbol = token.get('baseToken', {}).get('symbol', 'UNKNOWN')
            change = token.get('priceChange', {}).get('h24', 0)
            price = token.get('priceUsd', '0')
            logger.info(f"{idx:2d}. {symbol:12s} +{change:>7.2f}%  价格: ${price}")
        logger.info(f"{'='*60}\n")

        return {
            "top_gainers": top_gainers,
            "scraped_count": len(detailed_tokens),
            "filtered_count": len(filtered_tokens),
            "filter_stats": filter_stats
        }

    async def add_tokens_to_monitor(
        self,
        tokens: List[Dict[str, Any]],
        drop_threshold: float = 20.0
    ) -> Dict[str, int]:
        """
        【独立功能2】将代币列表添加到监控表

        Args:
            tokens: 代币数据列表（可以来自 scrape_and_filter_top_gainers 的返回值）
            drop_threshold: 跌幅阈值（百分比）

        Returns:
            统计信息 {"total": int, "added": int, "skipped": int}
        """
        await self._ensure_db()

        logger.info(f"\n{'='*60}")
        logger.info(f"【添加监控】开始添加 {len(tokens)} 个代币到监控表")
        logger.info(f"{'='*60}\n")

        added_count = 0
        skipped_count = 0

        async with self.db_manager.get_session() as session:
            for token in tokens:
                try:
                    # 提取代币数据
                    base_token = token.get('baseToken', {})
                    token_address = base_token.get('address', '').lower()
                    token_symbol = base_token.get('symbol', 'UNKNOWN')
                    token_name = base_token.get('name', 'Unknown')

                    pair_address = token.get('pairAddress', '')
                    dex_id = token.get('dexId', 'unknown')

                    price_usd = float(token.get('priceUsd', 0))
                    price_change_24h = float(token.get('priceChange', {}).get('h24', 0))
                    market_cap = float(token.get('fdv', 0)) if token.get('fdv') else None
                    liquidity = float(token.get('liquidity', {}).get('usd', 0)) if token.get('liquidity') else None
                    volume_24h = float(token.get('volume', {}).get('h24', 0)) if token.get('volume') else None

                    if not token_address or not pair_address or price_usd <= 0:
                        logger.warning(f"数据无效: {token_symbol}, 跳过")
                        skipped_count += 1
                        continue

                    # 检查是否已在监控中
                    existing = await session.execute(
                        select(MonitoredToken).where(
                            and_(
                                MonitoredToken.token_address == token_address,
                                MonitoredToken.status == "active"
                            )
                        )
                    )
                    if existing.scalar_one_or_none():
                        logger.info(f"  {token_symbol} 已在监控中，跳过")
                        skipped_count += 1
                        continue

                    # 创建监控记录
                    monitored = MonitoredToken(
                        token_address=token_address,
                        token_symbol=token_symbol,
                        token_name=token_name,
                        dex_id=dex_id,
                        pair_address=pair_address,
                        entry_price_usd=Decimal(str(price_usd)),
                        entry_timestamp=datetime.utcnow(),
                        current_price_usd=Decimal(str(price_usd)),
                        peak_price_usd=Decimal(str(price_usd)),
                        peak_timestamp=datetime.utcnow(),
                        market_cap_at_entry=Decimal(str(market_cap)) if market_cap else None,
                        liquidity_at_entry=Decimal(str(liquidity)) if liquidity else None,
                        volume_24h_at_entry=Decimal(str(volume_24h)) if volume_24h else None,
                        price_change_24h_at_entry=Decimal(str(price_change_24h)),
                        status="active",
                        drop_threshold_percent=Decimal(str(drop_threshold))
                    )

                    session.add(monitored)
                    added_count += 1

                    logger.info(
                        f"  ✓ {token_symbol:12s} 入场价=${price_usd:.8f}, 涨幅=+{price_change_24h:.2f}%"
                    )

                except Exception as e:
                    logger.error(f"添加代币时出错: {e}")
                    skipped_count += 1
                    continue

            await session.commit()

        logger.info(f"\n{'='*60}")
        logger.info(f"添加完成: {added_count}/{len(tokens)} 成功, {skipped_count} 跳过")
        logger.info(f"{'='*60}\n")

        return {
            "total": len(tokens),
            "added": added_count,
            "skipped": skipped_count
        }

    async def scrape_and_add_top_gainers(
        self,
        count: int = 100,
        top_n: int = 10,
        drop_threshold: float = 20.0,
        headless: bool = False
    ) -> Dict[str, Any]:
        """
        【一键操作】爬取 + 筛选 + 添加监控（便捷方法）

        如果想分开执行，请使用：
        - scrape_and_filter_top_gainers() - 只爬取筛选
        - add_tokens_to_monitor() - 只添加监控

        Args:
            count: 爬取代币数量
            top_n: 筛选前N名
            drop_threshold: 跌幅阈值
            headless: 是否使用无头浏览器

        Returns:
            统计信息字典
        """
        logger.info("\n" + "="*60)
        logger.info("【一键操作】爬取 + 筛选 + 添加监控")
        logger.info("="*60)

        # 步骤1: 爬取和筛选
        scrape_result = self.scrape_and_filter_top_gainers(
            count=count,
            top_n=top_n,
            headless=headless
        )

        top_gainers = scrape_result["top_gainers"]
        if not top_gainers:
            return {
                "scraped": scrape_result["scraped_count"],
                "top_gainers": 0,
                "saved": 0,
                "skipped": 0,
                "filter_stats": scrape_result.get("filter_stats", {})
            }

        # 步骤2: 添加到监控
        add_result = await self.add_tokens_to_monitor(
            tokens=top_gainers,
            drop_threshold=drop_threshold
        )

        return {
            "scraped": scrape_result["scraped_count"],
            "filtered": scrape_result["filtered_count"],
            "top_gainers": len(top_gainers),
            "added": add_result["added"],
            "skipped": add_result["skipped"],
            "filter_stats": scrape_result.get("filter_stats", {})
        }

    async def update_monitored_prices(
        self,
        batch_size: int = 10,
        delay: float = 0.3
    ) -> Dict[str, Any]:
        """
        Update current prices and detailed data for all active monitored tokens using AVE API.

        Args:
            batch_size: Number of pairs to fetch at once (not used with AVE API, kept for compatibility)
            delay: Delay between API calls (seconds)

        Returns:
            Update statistics including removal counts
        """
        await self._ensure_db()

        logger.info("Updating prices for monitored tokens using AVE API...")

        # Load monitor configuration
        monitor_config = None
        async with self.db_manager.get_session() as session:
            config_result = await session.execute(
                select(MonitorConfig).limit(1)
            )
            monitor_config = config_result.scalar_one_or_none()

        min_market_cap = None
        min_liquidity = None
        if monitor_config:
            min_market_cap = float(monitor_config.min_monitor_market_cap) if monitor_config.min_monitor_market_cap else None
            min_liquidity = float(monitor_config.min_monitor_liquidity) if monitor_config.min_monitor_liquidity else None
            if min_market_cap or min_liquidity:
                logger.info(f"监控过滤阈值: 市值 >= {min_market_cap}, 流动性 >= {min_liquidity}")

        # Get all monitored tokens (active and alerted, but not stopped or deleted)
        # 已触发报警的代币也要继续更新，因为可能有多级阈值
        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(MonitoredToken).where(
                    MonitoredToken.status != "stopped",
                    MonitoredToken.deleted_at.is_(None),
                    MonitoredToken.permanently_deleted == 0
                )
            )
            monitored_tokens = result.scalars().all()

        if not monitored_tokens:
            logger.info("No monitored tokens to update")
            return {"updated": 0, "alerts_triggered": 0, "removed": 0}

        logger.info(f"Found {len(monitored_tokens)} monitored tokens (including alerted)")

        # Update prices and check for alerts
        updated_count = 0
        alerts_triggered = 0
        removed_count = 0
        removed_by_market_cap = 0
        removed_by_liquidity = 0
        import time

        async with self.db_manager.get_session() as session:
            for token in monitored_tokens:
                try:
                    # Fetch detailed data from AVE API
                    # 使用代币的 chain 字段（bsc 或 solana）
                    chain = getattr(token, 'chain', 'bsc')  # 兼容旧数据，默认 bsc
                    pair_data = ave_api_service.get_pair_detail_parsed(
                        pair_address=token.pair_address,
                        chain=chain
                    )

                    if not pair_data or not pair_data.get('current_price_usd'):
                        logger.warning(f"No price data for {token.token_symbol}")
                        time.sleep(delay)
                        continue

                    current_price = pair_data['current_price_usd']

                    # Update current price
                    token.current_price_usd = current_price
                    token.last_update_timestamp = datetime.utcnow()

                    # Update historical ATH (all-time high from blockchain)
                    if pair_data.get('price_ath_usd'):
                        old_ath = token.price_ath_usd
                        token.price_ath_usd = pair_data['price_ath_usd']
                        # 如果创新高，记录日志
                        if old_ath and token.price_ath_usd > old_ath:
                            logger.info(f"{token.token_symbol} new ATH: ${token.price_ath_usd} (was ${old_ath})")

                    # 同步 peak_price_usd = price_ath_usd（保持字段一致性）
                    if token.price_ath_usd:
                        token.peak_price_usd = token.price_ath_usd
                        token.peak_timestamp = datetime.utcnow()

                    if pair_data.get('amm'):
                        token.amm = pair_data['amm']

                    if pair_data.get('current_tvl'):
                        token.current_tvl = pair_data['current_tvl']

                    if pair_data.get('current_market_cap'):
                        token.current_market_cap = pair_data['current_market_cap']

                    # Price changes
                    for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '24h']:
                        field = f'price_change_{timeframe}'
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # Volumes
                    for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '24h']:
                        field = f'volume_{timeframe}'
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # Transaction counts
                    for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '24h']:
                        field = f'tx_count_{timeframe}'
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # Buy/sell data
                    if pair_data.get('buys_24h') is not None:
                        token.buys_24h = pair_data['buys_24h']
                    if pair_data.get('sells_24h') is not None:
                        token.sells_24h = pair_data['sells_24h']

                    # Traders
                    if pair_data.get('makers_24h') is not None:
                        token.makers_24h = pair_data['makers_24h']
                    if pair_data.get('buyers_24h') is not None:
                        token.buyers_24h = pair_data['buyers_24h']
                    if pair_data.get('sellers_24h') is not None:
                        token.sellers_24h = pair_data['sellers_24h']

                    # 24h price range
                    if pair_data.get('price_24h_high') is not None:
                        token.price_24h_high = pair_data['price_24h_high']
                    if pair_data.get('price_24h_low') is not None:
                        token.price_24h_low = pair_data['price_24h_low']
                    if pair_data.get('open_price_24h') is not None:
                        token.open_price_24h = pair_data['open_price_24h']

                    # LP info
                    if pair_data.get('lp_holders') is not None:
                        token.lp_holders = pair_data['lp_holders']
                    if pair_data.get('lp_locked_percent') is not None:
                        token.lp_locked_percent = pair_data['lp_locked_percent']
                    if pair_data.get('lp_lock_platform'):
                        token.lp_lock_platform = pair_data['lp_lock_platform']

                    # Early trading metrics
                    if pair_data.get('rusher_tx_count') is not None:
                        token.rusher_tx_count = pair_data['rusher_tx_count']
                    if pair_data.get('sniper_tx_count') is not None:
                        token.sniper_tx_count = pair_data['sniper_tx_count']

                    session.add(token)
                    updated_count += 1
                    # 不再打印每个代币的成功更新，最后汇总

                    # Check for price drop alert (using simple price data dict for compatibility)
                    price_data_dict = {
                        'price_usd': float(current_price),
                        'market_cap': float(pair_data.get('current_market_cap', 0)) if pair_data.get('current_market_cap') else None,
                        'liquidity': float(pair_data.get('current_tvl', 0)) if pair_data.get('current_tvl') else None,
                        'volume_24h': float(pair_data.get('volume_24h', 0)) if pair_data.get('volume_24h') else None,
                    }
                    if await self._check_and_trigger_alert(session, token, price_data_dict):
                        alerts_triggered += 1

                    # 使用通用方法检查是否需要删除
                    should_remove, removal_reason, removal_threshold = self._check_and_remove_by_thresholds(
                        token, min_market_cap, min_liquidity
                    )

                    if should_remove:
                        # 标记删除
                        token.permanently_deleted = 1
                        token.removal_reason = removal_reason
                        token.removal_threshold_value = removal_threshold
                        token.deleted_at = datetime.utcnow()
                        removed_count += 1

                        # 统计分类
                        if removal_reason == "low_market_cap":
                            removed_by_market_cap += 1
                        elif removal_reason == "low_liquidity":
                            removed_by_liquidity += 1

                        # 日志
                        logger.warning(
                            f"🗑️ Auto-removed {token.token_symbol}: {removal_reason} "
                            f"(value: {removal_threshold:.2f}, threshold: "
                            f"{min_market_cap if removal_reason == 'low_market_cap' else min_liquidity:.2f})"
                        )

                    # Delay to avoid rate limiting
                    time.sleep(delay)

                except Exception as e:
                    logger.error(f"Error updating {token.token_symbol}: {e}")
                    time.sleep(delay)
                    continue

            await session.commit()

        # 汇总成功日志
        if updated_count > 0:
            logger.info(
                f"✅ 成功更新 {updated_count}/{len(monitored_tokens)} 个监控代币, "
                f"触发报警 {alerts_triggered} 次"
            )
            if removed_count > 0:
                logger.info(
                    f"🗑️ 自动删除 {removed_count} 个代币 "
                    f"(市值: {removed_by_market_cap}, 流动性: {removed_by_liquidity})"
                )
        else:
            logger.info(f"未更新任何代币 (总共 {len(monitored_tokens)} 个)")

        return {
            "updated": updated_count,
            "alerts_triggered": alerts_triggered,
            "total_monitored": len(monitored_tokens),
            "removed": removed_count,
            "removed_by_market_cap": removed_by_market_cap,
            "removed_by_liquidity": removed_by_liquidity
        }

    def _check_and_remove_by_thresholds(
        self,
        token,
        min_market_cap: Optional[float],
        min_liquidity: Optional[float]
    ) -> tuple[bool, Optional[str], Optional[float]]:
        """
        检查代币是否应该被删除（通用筛选逻辑）

        Args:
            token: MonitoredToken 或 PotentialToken 对象
            min_market_cap: 最小市值阈值（美元）
            min_liquidity: 最小流动性阈值（美元）

        Returns:
            (should_remove, removal_reason, removal_threshold_value)
        """
        should_remove = False
        removal_reason = None
        removal_threshold = None

        # 检查市值阈值
        if min_market_cap is not None and token.current_market_cap is not None:
            if float(token.current_market_cap) < min_market_cap:
                should_remove = True
                removal_reason = "low_market_cap"
                removal_threshold = float(token.current_market_cap)

        # 检查流动性阈值（只有在未被市值筛掉的情况下才检查）
        if not should_remove and min_liquidity is not None and token.current_tvl is not None:
            if float(token.current_tvl) < min_liquidity:
                should_remove = True
                removal_reason = "low_liquidity"
                removal_threshold = float(token.current_tvl)

        return should_remove, removal_reason, removal_threshold

    async def _check_and_trigger_alert(
        self,
        session: AsyncSession,
        token: MonitoredToken,
        price_data: Dict[str, Any]
    ) -> bool:
        """
        Check if alert should be triggered and create alert record.

        计算逻辑：从历史最高价(ATH)计算跌幅，支持多级阈值报警

        多级阈值设计：
        - 使用token.alert_thresholds自定义阈值列表（默认 [70, 80, 90]）
        - 每个代币可以有自己的阈值列表
        - 每个阈值只报警一次，避免重复

        Args:
            session: Database session
            token: Monitored token instance
            price_data: Current price data

        Returns:
            True if alert was triggered
        """
        current_price = token.current_price_usd
        ath_price = token.price_ath_usd or token.peak_price_usd  # 优先使用历史ATH
        entry_price = token.entry_price_usd

        # Calculate drop from ATH (历史最高点)
        drop_from_ath = ((ath_price - current_price) / ath_price) * 100
        drop_from_entry = ((entry_price - current_price) / entry_price) * 100

        # 使用自定义阈值列表（每个代币有自己的阈值配置）
        thresholds = token.alert_thresholds if token.alert_thresholds else [70, 80, 90]
        # 转换为float列表（JSONB可能返回其他类型）
        thresholds = [float(t) for t in thresholds]

        # 找出当前跌幅达到的最高阈值
        triggered_threshold = None
        for threshold in sorted(thresholds, reverse=True):
            if drop_from_ath >= threshold:
                triggered_threshold = threshold
                break

        # 如果没有达到任何阈值，不报警
        if triggered_threshold is None:
            return False

        # 查询该代币所有历史报警，检查这个阈值是否已经报警过
        all_alerts = await session.execute(
            select(PriceAlert).where(
                PriceAlert.monitored_token_id == token.id
            ).order_by(desc(PriceAlert.triggered_at))
        )
        existing_alerts = all_alerts.scalars().all()

        # 检查是否已经在这个阈值级别报警过
        # 逻辑：对于每条历史报警，计算它属于哪个阈值级别
        for existing_alert in existing_alerts:
            existing_drop = float(existing_alert.drop_from_peak_percent)

            # 计算该历史报警应该属于哪个阈值级别
            existing_threshold = None
            for threshold in sorted(thresholds, reverse=True):
                if existing_drop >= threshold:
                    existing_threshold = threshold
                    break

            # 如果历史报警的阈值级别与当前要触发的阈值相同，则不重复报警
            if existing_threshold == triggered_threshold:
                return False

        # Determine severity (基于ATH跌幅)
        severity = "low"
        if drop_from_ath >= 70:
            severity = "critical"
        elif drop_from_ath >= 50:
            severity = "high"
        elif drop_from_ath >= 30:
            severity = "medium"

        # Create alert
        alert = PriceAlert(
            monitored_token_id=token.id,
            alert_type="price_drop",
            triggered_at=datetime.utcnow(),
            trigger_price_usd=current_price,
            peak_price_usd=ath_price,  # 存储ATH而不是监控期间峰值
            entry_price_usd=entry_price,
            drop_from_peak_percent=Decimal(str(drop_from_ath)),  # 从ATH的跌幅
            drop_from_entry_percent=Decimal(str(drop_from_entry)),
            market_cap=Decimal(str(price_data['market_cap'])) if price_data.get('market_cap') else None,
            liquidity_usd=Decimal(str(price_data['liquidity'])) if price_data.get('liquidity') else None,
            volume_24h=Decimal(str(price_data['volume_24h'])) if price_data.get('volume_24h') else None,
            message=f"{token.token_symbol} dropped {drop_from_ath:.2f}% from ATH ${ath_price} (threshold: {triggered_threshold}%)",
            severity=severity,
            acknowledged=0
        )

        session.add(alert)

        # Update token status to alerted (但会继续监控)
        token.status = "alerted"

        logger.warning(
            f"🚨 ALERT [{severity.upper()}]: {token.token_symbol} dropped {drop_from_ath:.2f}% from ATH! "
            f"ATH: ${ath_price}, Current: ${current_price}, Threshold: {triggered_threshold}%"
        )

        return True

    async def get_monitored_tokens(
        self,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of monitored tokens with optional status filter.

        Args:
            limit: Maximum number of tokens to return
            status: Filter by status (active/alerted/stopped), None returns all

        Returns:
            List of monitored token data
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            # 默认排除已删除和彻底删除的代币
            query = select(MonitoredToken).where(
                MonitoredToken.deleted_at.is_(None),
                MonitoredToken.permanently_deleted == 0
            )

            # Apply status filter if provided
            if status:
                query = query.where(MonitoredToken.status == status)

            query = query.order_by(desc(MonitoredToken.entry_timestamp)).limit(limit)

            result = await session.execute(query)
            tokens = result.scalars().all()

            return self._format_token_list(tokens)

    async def get_active_monitored_tokens(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get list of active monitored tokens.

        Args:
            limit: Maximum number of tokens to return

        Returns:
            List of monitored token data
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(MonitoredToken)
                .where(MonitoredToken.status == "active")
                .order_by(desc(MonitoredToken.entry_timestamp))
                .limit(limit)
            )
            tokens = result.scalars().all()

            return self._format_token_list(tokens)

    async def get_alerts(
        self,
        limit: int = 50,
        acknowledged: Optional[bool] = None,
        severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get price alerts.

        Args:
            limit: Maximum number of alerts to return
            acknowledged: Filter by acknowledged status (None = all)
            severity: Filter by severity level

        Returns:
            List of alert data
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            query = select(PriceAlert).join(MonitoredToken)

            # Apply filters
            conditions = []
            if acknowledged is not None:
                conditions.append(PriceAlert.acknowledged == (1 if acknowledged else 0))
            if severity:
                conditions.append(PriceAlert.severity == severity)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.order_by(desc(PriceAlert.triggered_at)).limit(limit)

            result = await session.execute(query)
            alerts = result.scalars().all()

            # Fetch related monitored tokens
            alert_data = []
            for alert in alerts:
                token = await session.get(MonitoredToken, alert.monitored_token_id)
                alert_data.append({
                    "id": alert.id,
                    "token_symbol": token.token_symbol if token else "UNKNOWN",
                    "token_address": token.token_address if token else None,
                    "alert_type": alert.alert_type,
                    "triggered_at": alert.triggered_at.isoformat(),
                    "trigger_price_usd": float(alert.trigger_price_usd),
                    "peak_price_usd": float(alert.peak_price_usd),
                    "entry_price_usd": float(alert.entry_price_usd),
                    "drop_from_peak_percent": float(alert.drop_from_peak_percent),
                    "drop_from_entry_percent": float(alert.drop_from_entry_percent),
                    "message": alert.message,
                    "severity": alert.severity,
                    "acknowledged": bool(alert.acknowledged),
                })

            return alert_data

    # ==================== 潜力币种相关方法 ====================

    async def scrape_and_save_to_potential(
        self,
        count: int = 100,
        top_n: int = 10,
        headless: bool = False
    ) -> Dict[str, Any]:
        """
        爬取Top涨幅代币并保存到潜力币种表

        更新策略：
        - 如果代币不存在：创建新记录
        - 如果代币已存在：
          - 新涨幅 > 原涨幅：更新所有爬取字段（价格、涨幅、市值等）
          - 新涨幅 <= 原涨幅：跳过，保留原记录的最高涨幅

        Args:
            count: 爬取代币数量
            top_n: 筛选前N名
            headless: 是否使用无头浏览器

        Returns:
            统计信息字典 {scraped, top_gainers, saved, skipped}
        """
        logger.info("\n" + "="*60)
        logger.info("【爬取潜力币种】保存到 potential_tokens 表")
        logger.info("="*60)

        # 步骤1: 爬取和筛选
        scrape_result = self.scrape_and_filter_top_gainers(
            count=count,
            top_n=top_n,
            headless=headless
        )

        top_gainers = scrape_result["top_gainers"]
        if not top_gainers:
            return {
                "scraped": scrape_result["scraped_count"],
                "top_gainers": 0,
                "saved": 0,
                "skipped": 0,
                "filter_stats": scrape_result.get("filter_stats", {})
            }

        # 步骤2: 保存到 potential_tokens 表
        await self._ensure_db()

        added_count = 0
        skipped_count = 0

        async with self.db_manager.get_session() as session:
            for token_data in top_gainers:
                try:
                    # 从 DexScreener 数据结构中提取字段
                    base_token = token_data.get('baseToken', {})
                    token_address = base_token.get('address', '').lower()
                    token_symbol = base_token.get('symbol', 'UNKNOWN')
                    token_name = base_token.get('name', 'Unknown')

                    pair_address = token_data.get('pairAddress', '')
                    dex_id = token_data.get('dexId', 'unknown')

                    price_usd = float(token_data.get('priceUsd', 0))
                    price_change_24h = float(token_data.get('priceChange', {}).get('h24', 0))

                    market_cap = float(token_data.get('fdv', 0) or token_data.get('marketCap', 0) or 0)
                    liquidity_usd = float(token_data.get('liquidity', {}).get('usd', 0) or 0)
                    volume_24h = float(token_data.get('volume', {}).get('h24', 0) or 0)

                    # 检查是否已存在（使用 pair_address）
                    result = await session.execute(
                        select(PotentialToken).where(
                            PotentialToken.pair_address == pair_address
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        # 代币已存在，检查是否需要更新
                        old_change = existing.price_change_24h_at_scrape or 0

                        # 如果新涨幅更高，更新爬取数据
                        if price_change_24h > old_change:
                            existing.scraped_price_usd = price_usd
                            existing.scraped_timestamp = datetime.utcnow()
                            existing.market_cap_at_scrape = market_cap if market_cap > 0 else None
                            existing.liquidity_at_scrape = liquidity_usd if liquidity_usd > 0 else None
                            existing.volume_24h_at_scrape = volume_24h if volume_24h > 0 else None
                            existing.price_change_24h_at_scrape = price_change_24h

                            await session.flush()
                            logger.info(
                                f"🔄 Updated {token_symbol}: 涨幅从 {old_change:.1f}% → {price_change_24h:.1f}% "
                                f"(+{price_change_24h - old_change:.1f}%)"
                            )
                            added_count += 1
                        else:
                            # 涨幅未提高，跳过更新
                            logger.info(
                                f"⏭️  {token_symbol} 涨幅未提高 "
                                f"(当前: {price_change_24h:.1f}%, 最高: {old_change:.1f}%)"
                            )
                            skipped_count += 1
                        continue

                    # 创建新的潜力币种记录
                    potential_token = PotentialToken(
                        token_address=token_address,
                        token_symbol=token_symbol,
                        token_name=token_name,
                        dex_id=dex_id,
                        pair_address=pair_address,
                        amm=None,  # 页面数据暂时没有 AMM 字段
                        scraped_price_usd=price_usd,
                        scraped_timestamp=datetime.utcnow(),
                        market_cap_at_scrape=market_cap if market_cap > 0 else None,
                        liquidity_at_scrape=liquidity_usd if liquidity_usd > 0 else None,
                        volume_24h_at_scrape=volume_24h if volume_24h > 0 else None,
                        price_change_24h_at_scrape=price_change_24h,
                        is_added_to_monitoring=0
                    )
                    session.add(potential_token)
                    await session.flush()

                    logger.info(f"✅ Added {token_symbol} to potential_tokens (+{price_change_24h:.1f}%)")
                    added_count += 1

                except Exception as e:
                    logger.error(f"Error adding {token_data.get('baseToken', {}).get('symbol', 'UNKNOWN')}: {e}")
                    skipped_count += 1

        logger.info(
            f"\n✅ Saved to potential_tokens: {added_count} added/updated, {skipped_count} skipped"
        )

        return {
            "scraped": scrape_result["scraped_count"],
            "filtered": scrape_result["filtered_count"],
            "top_gainers": len(top_gainers),
            "saved": added_count,  # 包含新增和更新的数量
            "skipped": skipped_count,
            "filter_stats": scrape_result.get("filter_stats", {})
        }

    async def get_potential_tokens(
        self,
        limit: int = 100,
        only_not_added: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取潜力币种列表

        Args:
            limit: 返回数量
            only_not_added: 仅返回未添加到监控的

        Returns:
            潜力币种列表
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            # 默认排除已删除和彻底删除的代币
            query = select(PotentialToken).where(
                PotentialToken.deleted_at.is_(None),
                PotentialToken.permanently_deleted == 0
            )

            if only_not_added:
                query = query.where(PotentialToken.is_added_to_monitoring == 0)

            query = query.order_by(desc(PotentialToken.scraped_timestamp)).limit(limit)

            result = await session.execute(query)
            tokens = result.scalars().all()

            return self._format_potential_token_list(tokens)

    def _format_potential_token_list(self, tokens: list) -> List[Dict[str, Any]]:
        """Format a list of PotentialToken objects to dictionaries."""
        return [
            {
                # 基础信息
                "id": token.id,
                "token_address": token.token_address,
                "token_symbol": token.token_symbol,
                "token_name": token.token_name,
                "chain": token.chain,
                "dex_id": token.dex_id,
                "pair_address": token.pair_address,
                "amm": token.amm,
                "dex_type": token.dex_type,

                # 爬取时的价格和市场数据
                "scraped_price_usd": float(token.scraped_price_usd),
                "scraped_timestamp": token.scraped_timestamp.isoformat() if token.scraped_timestamp else None,
                "market_cap_at_scrape": float(token.market_cap_at_scrape) if token.market_cap_at_scrape else None,
                "liquidity_at_scrape": float(token.liquidity_at_scrape) if token.liquidity_at_scrape else None,
                "volume_24h_at_scrape": float(token.volume_24h_at_scrape) if token.volume_24h_at_scrape else None,
                "price_change_24h_at_scrape": float(token.price_change_24h_at_scrape) if token.price_change_24h_at_scrape else None,

                # 当前数据（AVE API更新后）
                "current_price_usd": float(token.current_price_usd) if token.current_price_usd else None,
                "price_ath_usd": float(token.price_ath_usd) if token.price_ath_usd else None,
                "current_tvl": float(token.current_tvl) if token.current_tvl else None,
                "current_market_cap": float(token.current_market_cap) if token.current_market_cap else None,

                # 时间戳
                "token_created_at": token.token_created_at.isoformat() if token.token_created_at else None,
                "first_trade_at": token.first_trade_at.isoformat() if token.first_trade_at else None,
                "last_ave_update": token.last_ave_update.isoformat() if token.last_ave_update else None,

                # 价格变化
                "price_change_1m": float(token.price_change_1m) if token.price_change_1m else None,
                "price_change_5m": float(token.price_change_5m) if token.price_change_5m else None,
                "price_change_15m": float(token.price_change_15m) if token.price_change_15m else None,
                "price_change_30m": float(token.price_change_30m) if token.price_change_30m else None,
                "price_change_1h": float(token.price_change_1h) if token.price_change_1h else None,
                "price_change_4h": float(token.price_change_4h) if token.price_change_4h else None,
                "price_change_24h": float(token.price_change_24h) if token.price_change_24h else None,

                # 交易量
                "volume_1m": float(token.volume_1m) if token.volume_1m else None,
                "volume_5m": float(token.volume_5m) if token.volume_5m else None,
                "volume_15m": float(token.volume_15m) if token.volume_15m else None,
                "volume_30m": float(token.volume_30m) if token.volume_30m else None,
                "volume_1h": float(token.volume_1h) if token.volume_1h else None,
                "volume_4h": float(token.volume_4h) if token.volume_4h else None,
                "volume_24h": float(token.volume_24h) if token.volume_24h else None,

                # 交易次数
                "tx_count_1m": token.tx_count_1m,
                "tx_count_5m": token.tx_count_5m,
                "tx_count_15m": token.tx_count_15m,
                "tx_count_30m": token.tx_count_30m,
                "tx_count_1h": token.tx_count_1h,
                "tx_count_4h": token.tx_count_4h,
                "tx_count_24h": token.tx_count_24h,

                # 买卖数据
                "buys_24h": token.buys_24h,
                "sells_24h": token.sells_24h,

                # 交易者数据
                "makers_24h": token.makers_24h,
                "buyers_24h": token.buyers_24h,
                "sellers_24h": token.sellers_24h,

                # 24小时价格范围
                "price_24h_high": float(token.price_24h_high) if token.price_24h_high else None,
                "price_24h_low": float(token.price_24h_low) if token.price_24h_low else None,
                "open_price_24h": float(token.open_price_24h) if token.open_price_24h else None,

                # LP信息
                "lp_holders": token.lp_holders,
                "lp_locked_percent": float(token.lp_locked_percent) if token.lp_locked_percent else None,
                "lp_lock_platform": token.lp_lock_platform,

                # 安全指标
                "rusher_tx_count": token.rusher_tx_count,
                "sniper_tx_count": token.sniper_tx_count,

                # Token创建信息
                "creation_block_number": token.creation_block_number,
                "creation_tx_hash": token.creation_tx_hash,

                # 状态
                "is_added_to_monitoring": bool(token.is_added_to_monitoring),
                "added_to_monitoring_at": token.added_to_monitoring_at.isoformat() if token.added_to_monitoring_at else None,
            }
            for token in tokens
        ]

    async def add_potential_to_monitoring(
        self,
        potential_token_id: str,
        drop_threshold: float = 20.0
    ) -> Dict[str, Any]:
        """
        将潜力币种添加到监控表

        Args:
            potential_token_id: 潜力币种ID
            drop_threshold: 跌幅报警阈值

        Returns:
            操作结果
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            # 获取潜力币种
            potential_token = await session.get(PotentialToken, potential_token_id)
            if not potential_token:
                raise ValueError(f"Potential token not found: {potential_token_id}")

            # 检查是否已添加到监控
            if potential_token.is_added_to_monitoring:
                raise ValueError(f"Token {potential_token.token_symbol} already added to monitoring")

            # 检查监控表中是否已存在该 pair
            result = await session.execute(
                select(MonitoredToken).where(
                    MonitoredToken.pair_address == potential_token.pair_address
                )
            )
            existing_monitored = result.scalar_one_or_none()
            if existing_monitored:
                raise ValueError(f"Token {potential_token.token_symbol} already in monitored_tokens")

            # 创建监控记录（使用当前价格或爬取价格）
            entry_price = float(potential_token.current_price_usd or potential_token.scraped_price_usd)

            monitored_token = MonitoredToken(
                token_address=potential_token.token_address,
                token_symbol=potential_token.token_symbol,
                token_name=potential_token.token_name,
                chain=getattr(potential_token, 'chain', 'bsc'),  # 复制 chain 字段
                dex_id=potential_token.dex_id,
                pair_address=potential_token.pair_address,
                amm=potential_token.amm,
                dex_type=getattr(potential_token, 'dex_type', None),  # 复制 dex_type 字段
                entry_price_usd=entry_price,
                peak_price_usd=entry_price,  # 初始峰值 = 入场价
                entry_timestamp=datetime.utcnow(),
                peak_timestamp=datetime.utcnow(),
                market_cap_at_entry=float(potential_token.current_market_cap or potential_token.market_cap_at_scrape or 0),
                liquidity_at_entry=float(potential_token.liquidity_at_scrape or 0),
                volume_24h_at_entry=float(potential_token.volume_24h or potential_token.volume_24h_at_scrape or 0),
                price_change_24h_at_entry=float(potential_token.price_change_24h or potential_token.price_change_24h_at_scrape or 0),
                status="active",
                drop_threshold_percent=drop_threshold
            )

            # 复制AVE API数据
            monitored_token.current_price_usd = potential_token.current_price_usd
            monitored_token.price_ath_usd = potential_token.price_ath_usd
            monitored_token.current_tvl = potential_token.current_tvl
            monitored_token.current_market_cap = potential_token.current_market_cap

            # 复制多时间段数据
            for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '24h']:
                for prefix in ['price_change', 'volume', 'tx_count']:
                    field = f'{prefix}_{timeframe}'
                    value = getattr(potential_token, field, None)
                    if value is not None:
                        setattr(monitored_token, field, value)

            # 复制其他字段
            for field in ['buys_24h', 'sells_24h', 'makers_24h', 'buyers_24h', 'sellers_24h',
                          'price_24h_high', 'price_24h_low', 'open_price_24h',
                          'token_created_at', 'first_trade_at', 'creation_block_number', 'creation_tx_hash',
                          'lp_holders', 'lp_locked_percent', 'lp_lock_platform',
                          'rusher_tx_count', 'sniper_tx_count']:
                value = getattr(potential_token, field, None)
                if value is not None:
                    setattr(monitored_token, field, value)

            session.add(monitored_token)

            # 标记潜力币种已添加
            potential_token.is_added_to_monitoring = 1
            potential_token.added_to_monitoring_at = datetime.utcnow()

            await session.flush()

            logger.info(f"✅ Added {potential_token.token_symbol} to monitoring (entry: ${entry_price:.8f})")

            return {
                "success": True,
                "token_symbol": potential_token.token_symbol,
                "monitored_token_id": monitored_token.id,
                "entry_price_usd": entry_price
            }

    async def delete_potential_token(self, potential_token_id: str) -> Dict[str, Any]:
        """
        软删除潜力币种（设置deleted_at而不是真正删除）

        Args:
            potential_token_id: 潜力币种ID

        Returns:
            操作结果
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            potential_token = await session.get(PotentialToken, potential_token_id)
            if not potential_token:
                raise ValueError(f"Potential token not found: {potential_token_id}")

            if potential_token.deleted_at is not None:
                raise ValueError(f"Token already deleted: {potential_token.token_symbol}")

            token_symbol = potential_token.token_symbol

            # 软删除：设置 deleted_at 时间戳
            potential_token.deleted_at = datetime.utcnow()
            await session.flush()

            logger.info(f"🗑️  Soft deleted potential token: {token_symbol}")

            return {
                "success": True,
                "token_symbol": token_symbol,
                "deleted_at": potential_token.deleted_at.isoformat()
            }

    async def get_deleted_potential_tokens(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取已删除的潜力代币列表

        Args:
            limit: 最大返回数量

        Returns:
            已删除的潜力代币列表
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            # 只返回软删除（deleted_at 不为空），但未彻底删除的代币
            query = select(PotentialToken).where(
                PotentialToken.deleted_at.isnot(None),
                PotentialToken.permanently_deleted == 0
            ).order_by(desc(PotentialToken.deleted_at)).limit(limit)

            result = await session.execute(query)
            tokens = result.scalars().all()

            return self._format_potential_token_list(tokens)

    async def restore_potential_token(self, potential_token_id: str) -> Dict[str, Any]:
        """
        恢复已删除的潜力代币

        Args:
            potential_token_id: 潜力代币ID

        Returns:
            操作结果
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            potential_token = await session.get(PotentialToken, potential_token_id)
            if not potential_token:
                raise ValueError(f"Potential token not found: {potential_token_id}")

            if potential_token.deleted_at is None:
                raise ValueError(f"Token is not deleted: {potential_token.token_symbol}")

            token_symbol = potential_token.token_symbol

            # 恢复：清除 deleted_at 时间戳
            potential_token.deleted_at = None
            await session.flush()

            logger.info(f"♻️  Restored potential token: {token_symbol}")

            return {
                "success": True,
                "token_symbol": token_symbol
            }

    async def delete_monitored_token(self, monitored_token_id: str) -> Dict[str, Any]:
        """
        软删除监控代币

        Args:
            monitored_token_id: 监控代币ID

        Returns:
            操作结果
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            monitored_token = await session.get(MonitoredToken, monitored_token_id)
            if not monitored_token:
                raise ValueError(f"Monitored token not found: {monitored_token_id}")

            if monitored_token.deleted_at is not None:
                raise ValueError(f"Token already deleted: {monitored_token.token_symbol}")

            token_symbol = monitored_token.token_symbol

            # 软删除：设置 deleted_at 时间戳
            monitored_token.deleted_at = datetime.utcnow()
            await session.flush()

            logger.info(f"🗑️  Soft deleted monitored token: {token_symbol}")

            return {
                "success": True,
                "token_symbol": token_symbol,
                "deleted_at": monitored_token.deleted_at.isoformat()
            }

    async def get_deleted_monitored_tokens(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取已删除的监控代币列表

        Args:
            limit: 最大返回数量

        Returns:
            已删除的监控代币列表
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            # 只返回软删除（deleted_at 不为空），但未彻底删除的代币
            query = select(MonitoredToken).where(
                MonitoredToken.deleted_at.isnot(None),
                MonitoredToken.permanently_deleted == 0
            ).order_by(desc(MonitoredToken.deleted_at)).limit(limit)

            result = await session.execute(query)
            tokens = result.scalars().all()

            return self._format_token_list(tokens)

    async def restore_monitored_token(self, monitored_token_id: str) -> Dict[str, Any]:
        """
        恢复已删除的监控代币

        Args:
            monitored_token_id: 监控代币ID

        Returns:
            操作结果
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            monitored_token = await session.get(MonitoredToken, monitored_token_id)
            if not monitored_token:
                raise ValueError(f"Monitored token not found: {monitored_token_id}")

            if monitored_token.deleted_at is None:
                raise ValueError(f"Token is not deleted: {monitored_token.token_symbol}")

            token_symbol = monitored_token.token_symbol

            # 恢复：清除 deleted_at 时间戳
            monitored_token.deleted_at = None
            await session.flush()

            logger.info(f"♻️  Restored monitored token: {token_symbol}")

            return {
                "success": True,
                "token_symbol": token_symbol
            }

    async def update_potential_tokens_data(
        self,
        delay: float = 0.3,
        min_update_interval_minutes: int = 3
    ) -> Dict[str, Any]:
        """
        更新所有潜力币种的AVE API数据

        Args:
            delay: API调用间隔（秒）
            min_update_interval_minutes: 最小更新间隔（分钟），避免频繁调用

        Returns:
            更新统计
        """
        await self._ensure_db()

        # 加载监控配置（用于筛选阈值）
        monitor_config = None
        async with self.db_manager.get_session() as session:
            config_result = await session.execute(
                select(MonitorConfig).limit(1)
            )
            monitor_config = config_result.scalar_one_or_none()

        min_market_cap = None
        min_liquidity = None
        if monitor_config:
            min_market_cap = float(monitor_config.min_monitor_market_cap) if monitor_config.min_monitor_market_cap else None
            min_liquidity = float(monitor_config.min_monitor_liquidity) if monitor_config.min_monitor_liquidity else None
            if min_market_cap or min_liquidity:
                logger.info(f"潜力代币筛选阈值: 市值 >= {min_market_cap}, 流动性 >= {min_liquidity}")

        # 检查是否需要跳过本次更新（避免重复调用）
        async with self.db_manager.get_session() as session:
            # 查询最近更新的潜力代币
            result = await session.execute(
                select(PotentialToken)
                .where(PotentialToken.last_ave_update.isnot(None))
                .order_by(desc(PotentialToken.last_ave_update))
                .limit(1)
            )
            latest_token = result.scalar_one_or_none()

            if latest_token and latest_token.last_ave_update:
                minutes_since_update = (datetime.utcnow() - latest_token.last_ave_update).total_seconds() / 60
                if minutes_since_update < min_update_interval_minutes:
                    logger.info(
                        f"Skipping update: last update was {minutes_since_update:.1f} minutes ago "
                        f"(min interval: {min_update_interval_minutes} minutes)"
                    )
                    return {"updated": 0, "failed": 0, "skipped": True}

        logger.info("Updating potential tokens with AVE API data...")

        updated_count = 0
        failed_count = 0
        removed_count = 0
        removed_by_market_cap = 0
        removed_by_liquidity = 0
        import time

        # 在同一个 session 中查询和更新
        async with self.db_manager.get_session() as session:
            # 获取所有未添加到监控的潜力币种（排除已删除）
            result = await session.execute(
                select(PotentialToken).where(
                    PotentialToken.is_added_to_monitoring == 0,
                    PotentialToken.deleted_at.is_(None),
                    PotentialToken.permanently_deleted == 0
                )
            )
            potential_tokens = result.scalars().all()

            if not potential_tokens:
                logger.info("No potential tokens to update")
                return {"updated": 0, "failed": 0}

            logger.info(f"Found {len(potential_tokens)} potential tokens to update")

            for token in potential_tokens:
                try:
                    # 获取AVE API数据
                    # 使用代币的 chain 字段（bsc 或 solana）
                    chain = getattr(token, 'chain', 'bsc')  # 兼容旧数据，默认 bsc
                    pair_data = ave_api_service.get_pair_detail_parsed(
                        pair_address=token.pair_address,
                        chain=chain
                    )

                    if not pair_data:
                        logger.warning(f"No AVE data for {token.token_symbol}")
                        failed_count += 1
                        time.sleep(delay)
                        continue

                    # 更新所有AVE API字段（和 MonitoredToken 一样的逻辑）
                    # 更新真实的 token 合约地址（修正爬虫时使用 pair_address 的问题）
                    if pair_data.get('token_address'):
                        token.token_address = pair_data['token_address']

                    if pair_data.get('current_price_usd'):
                        token.current_price_usd = pair_data['current_price_usd']

                    if pair_data.get('price_ath_usd'):
                        token.price_ath_usd = pair_data['price_ath_usd']

                    if pair_data.get('amm'):
                        token.amm = pair_data['amm']

                    if pair_data.get('current_tvl'):
                        token.current_tvl = pair_data['current_tvl']

                    if pair_data.get('current_market_cap'):
                        token.current_market_cap = pair_data['current_market_cap']

                    # 价格变化
                    for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '24h']:
                        field = f'price_change_{timeframe}'
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # 交易量
                    for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '24h']:
                        field = f'volume_{timeframe}'
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # 交易次数
                    for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '24h']:
                        field = f'tx_count_{timeframe}'
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # 买卖数据
                    if pair_data.get('buys_24h') is not None:
                        token.buys_24h = pair_data['buys_24h']
                    if pair_data.get('sells_24h') is not None:
                        token.sells_24h = pair_data['sells_24h']

                    # 交易者数据
                    for field in ['makers_24h', 'buyers_24h', 'sellers_24h']:
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # 价格范围
                    for field in ['price_24h_high', 'price_24h_low', 'open_price_24h']:
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # Token创建信息
                    if pair_data.get('token_created_at'):
                        token.token_created_at = pair_data['token_created_at']
                    if pair_data.get('first_trade_at'):
                        token.first_trade_at = pair_data['first_trade_at']
                    if pair_data.get('creation_block_number'):
                        token.creation_block_number = pair_data['creation_block_number']
                    if pair_data.get('creation_tx_hash'):
                        token.creation_tx_hash = pair_data['creation_tx_hash']

                    # LP信息
                    if pair_data.get('lp_holders') is not None:
                        token.lp_holders = pair_data['lp_holders']
                    if pair_data.get('lp_locked_percent') is not None:
                        token.lp_locked_percent = pair_data['lp_locked_percent']
                    if pair_data.get('lp_lock_platform'):
                        token.lp_lock_platform = pair_data['lp_lock_platform']

                    # 安全指标
                    if pair_data.get('rusher_tx_count') is not None:
                        token.rusher_tx_count = pair_data['rusher_tx_count']
                    if pair_data.get('sniper_tx_count') is not None:
                        token.sniper_tx_count = pair_data['sniper_tx_count']

                    token.last_ave_update = datetime.utcnow()
                    await session.flush()

                    # 使用通用方法检查是否需要删除
                    should_remove, removal_reason, removal_threshold = self._check_and_remove_by_thresholds(
                        token, min_market_cap, min_liquidity
                    )

                    if should_remove:
                        # 标记删除
                        token.permanently_deleted = 1
                        token.removal_reason = removal_reason
                        token.removal_threshold_value = removal_threshold
                        token.deleted_at = datetime.utcnow()
                        removed_count += 1

                        # 统计分类
                        if removal_reason == "low_market_cap":
                            removed_by_market_cap += 1
                        elif removal_reason == "low_liquidity":
                            removed_by_liquidity += 1

                        # 日志
                        logger.warning(
                            f"🗑️ Auto-removed potential token {token.token_symbol}: {removal_reason} "
                            f"(value: {removal_threshold:.2f}, threshold: "
                            f"{min_market_cap if removal_reason == 'low_market_cap' else min_liquidity:.2f})"
                        )

                    # 不再打印每个代币的成功更新，最后汇总
                    updated_count += 1

                    time.sleep(delay)

                except Exception as e:
                    logger.error(f"Error updating {token.token_symbol}: {e}")
                    failed_count += 1
                    time.sleep(delay)

            # 汇总成功日志
            if updated_count > 0:
                logger.info(
                    f"✅ 成功更新 {updated_count}/{len(potential_tokens)} 个潜力代币 AVE 数据"
                    + (f", {failed_count} 个失败" if failed_count > 0 else "")
                )
                if removed_count > 0:
                    logger.info(
                        f"🗑️ 自动删除 {removed_count} 个潜力代币 "
                        f"(市值: {removed_by_market_cap}, 流动性: {removed_by_liquidity})"
                    )
            else:
                logger.info(f"未更新任何潜力代币 (总共 {len(potential_tokens)} 个, {failed_count} 个失败)")

            return {
                "updated": updated_count,
                "failed": failed_count,
                "removed": removed_count,
                "removed_by_market_cap": removed_by_market_cap,
                "removed_by_liquidity": removed_by_liquidity
            }

    async def get_monitor_config(self) -> Optional[Dict[str, Any]]:
        """
        获取监控配置

        Returns:
            配置字典，如果不存在则返回None
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            try:
                query = select(MonitorConfig).limit(1)
                result = await session.execute(query)
                config = result.scalar_one_or_none()

                if not config:
                    logger.warning("未找到监控配置，使用默认值")
                    return {
                        "enabled": True,
                        "update_interval_minutes": 5,
                        "min_monitor_market_cap": None,
                        "min_monitor_liquidity": None,
                        "max_retry_count": 3,
                        "batch_size": 10
                    }

                return {
                    "id": config.id,
                    "enabled": bool(config.enabled),
                    "update_interval_minutes": config.update_interval_minutes,
                    "min_monitor_market_cap": float(config.min_monitor_market_cap) if config.min_monitor_market_cap else None,
                    "min_monitor_liquidity": float(config.min_monitor_liquidity) if config.min_monitor_liquidity else None,
                    "max_retry_count": config.max_retry_count,
                    "batch_size": config.batch_size,
                    "description": config.description
                }

            except Exception as e:
                logger.error(f"获取监控配置失败: {e}")
                return None

    async def get_scraper_config(self) -> Optional[Dict[str, Any]]:
        """
        获取爬虫配置

        Returns:
            配置字典，如果不存在则返回None
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            try:
                query = select(ScraperConfig).where(ScraperConfig.enabled == 1).limit(1)
                result = await session.execute(query)
                config = result.scalar_one_or_none()

                if not config:
                    logger.warning("未找到启用的爬虫配置")
                    return None

                return {
                    "id": config.id,
                    "top_n_per_chain": config.top_n_per_chain,
                    "count_per_chain": config.count_per_chain,
                    "scrape_interval_min": config.scrape_interval_min,
                    "scrape_interval_max": config.scrape_interval_max,
                    "enabled_chains": config.enabled_chains,  # JSONB field, already parsed as list
                    "use_undetected_chrome": bool(config.use_undetected_chrome),
                    "enabled": bool(config.enabled),
                    "description": config.description,
                    # 筛选条件
                    "min_market_cap": float(config.min_market_cap) if config.min_market_cap else None,
                    "min_liquidity": float(config.min_liquidity) if config.min_liquidity else None,
                    "max_token_age_days": config.max_token_age_days
                }

            except Exception as e:
                logger.error(f"获取爬虫配置失败: {e}")
                return None

    async def add_monitoring_by_pair(
        self,
        pair_address: str,
        chain: str,
        drop_threshold: float = 20.0,
        alert_thresholds: Optional[List[float]] = None
    ) -> dict:
        """
        通过 pair 地址手动添加监控代币

        流程：
        1. 调用 AVE API 获取 pair 详细信息
        2. 提取代币信息并创建监控记录
        """
        from src.storage.models import MonitoredToken
        from sqlalchemy import select
        import uuid

        # 1. 调用 AVE API 获取 pair 详情
        pair_data = ave_api_service.get_pair_detail_parsed(pair_address, chain)
        if not pair_data:
            raise ValueError(
                f"无法找到 pair: {pair_address} (链: {chain})。"
                f"可能原因：1) pair 地址不正确 2) AVE API 暂未收录该 pair 3) 链名称错误"
            )

        # 2. 提取代币信息
        token_address = pair_data.get('token_address') or pair_address
        token_symbol = pair_data.get('token_symbol') or 'Unknown'
        token_name = pair_data.get('token_name') or 'Unknown'

        # 安全获取价格（可能为 None）
        price_value = pair_data.get('current_price_usd')
        if price_value is None:
            raise ValueError(
                f"无法获取 pair {pair_address} 的价格信息。"
                f"pair 数据可能不完整或 AVE API 数据异常。"
            )

        current_price = float(price_value)
        if current_price <= 0:
            raise ValueError(f"获取到的代币价格无效: {current_price}")

        await self._ensure_db()

        # 3. 检查是否已存在监控
        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(MonitoredToken).where(
                    MonitoredToken.pair_address == pair_address,
                    MonitoredToken.chain == chain,
                    MonitoredToken.permanently_deleted == 0
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                raise ValueError(f"该代币已在监控列表中（{existing.token_symbol}）")

            # 4. 创建监控记录
            # 辅助函数：安全转换Decimal
            def safe_decimal(value):
                if value is None:
                    return None
                try:
                    return float(value) if isinstance(value, (int, float, Decimal)) else float(value)
                except:
                    return None

            monitored_token = MonitoredToken(
                id=str(uuid.uuid4()),
                token_address=token_address,
                token_symbol=token_symbol,
                token_name=token_name,
                chain=chain,
                dex_id='ave',
                pair_address=pair_address,
                amm=pair_data.get('amm'),
                dex_type=pair_data.get('dex_type'),
                entry_price_usd=current_price,
                peak_price_usd=current_price,
                current_price_usd=current_price,
                drop_threshold_percent=drop_threshold,
                alert_thresholds=alert_thresholds or [70, 80, 90],
                status='active',

                # 历史最高价（ATH）
                price_ath_usd=safe_decimal(pair_data.get('price_ath_usd')),

                # 市场数据
                current_tvl=safe_decimal(pair_data.get('current_tvl')),
                current_market_cap=safe_decimal(pair_data.get('current_market_cap')),

                # 价格变化（多时间段）
                price_change_1m=safe_decimal(pair_data.get('price_change_1m')),
                price_change_5m=safe_decimal(pair_data.get('price_change_5m')),
                price_change_15m=safe_decimal(pair_data.get('price_change_15m')),
                price_change_30m=safe_decimal(pair_data.get('price_change_30m')),
                price_change_1h=safe_decimal(pair_data.get('price_change_1h')),
                price_change_4h=safe_decimal(pair_data.get('price_change_4h')),
                price_change_24h=safe_decimal(pair_data.get('price_change_24h')),

                # 交易量（多时间段）
                volume_1m=safe_decimal(pair_data.get('volume_1m')),
                volume_5m=safe_decimal(pair_data.get('volume_5m')),
                volume_15m=safe_decimal(pair_data.get('volume_15m')),
                volume_30m=safe_decimal(pair_data.get('volume_30m')),
                volume_1h=safe_decimal(pair_data.get('volume_1h')),
                volume_4h=safe_decimal(pair_data.get('volume_4h')),
                volume_24h=safe_decimal(pair_data.get('volume_24h')),

                # 交易次数（多时间段）
                tx_count_1m=pair_data.get('tx_count_1m'),
                tx_count_5m=pair_data.get('tx_count_5m'),
                tx_count_15m=pair_data.get('tx_count_15m'),
                tx_count_30m=pair_data.get('tx_count_30m'),
                tx_count_1h=pair_data.get('tx_count_1h'),
                tx_count_4h=pair_data.get('tx_count_4h'),
                tx_count_24h=pair_data.get('tx_count_24h'),

                # 买卖数据
                buys_24h=pair_data.get('buys_24h'),
                sells_24h=pair_data.get('sells_24h'),

                # 交易者数据
                makers_24h=pair_data.get('makers_24h'),
                buyers_24h=pair_data.get('buyers_24h'),
                sellers_24h=pair_data.get('sellers_24h'),

                # 24小时价格范围
                price_24h_high=safe_decimal(pair_data.get('price_24h_high')),
                price_24h_low=safe_decimal(pair_data.get('price_24h_low')),
                open_price_24h=safe_decimal(pair_data.get('open_price_24h')),

                # LP信息
                lp_holders=pair_data.get('lp_holders'),
                lp_locked_percent=safe_decimal(pair_data.get('lp_locked_percent')),
                lp_lock_platform=pair_data.get('lp_lock_platform'),

                # 安全指标
                rusher_tx_count=pair_data.get('rusher_tx_count'),
                sniper_tx_count=pair_data.get('sniper_tx_count'),

                # Token创建信息
                token_created_at=pair_data.get('token_created_at'),
                first_trade_at=pair_data.get('first_trade_at'),
                creation_block_number=pair_data.get('creation_block_number'),
                creation_tx_hash=pair_data.get('creation_tx_hash'),
            )

            session.add(monitored_token)
            await session.commit()
            await session.refresh(monitored_token)

            logger.info(f"✅ 已添加到监控: {token_symbol} (pair: {pair_address[:10]}...)")

            return {
                "success": True,
                "message": f"已添加 {token_symbol} 到监控列表",
                "token_id": monitored_token.id,
                "token_symbol": token_symbol,
                "entry_price": current_price
            }

    async def permanently_delete_monitored_token(self, token_id: str) -> dict:
        """
        彻底删除监控代币（设置 permanently_deleted=1）
        """
        from src.storage.models import MonitoredToken
        from sqlalchemy import select
        from datetime import datetime

        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(MonitoredToken).where(MonitoredToken.id == token_id)
            )
            token = result.scalar_one_or_none()

            if not token:
                raise ValueError(f"未找到ID为 {token_id} 的监控代币")

            token.permanently_deleted = 1
            token.deleted_at = datetime.utcnow()
            await session.commit()

            logger.info(f"🗑️ 彻底删除监控代币: {token.token_symbol}")

            return {
                "success": True,
                "message": f"已彻底删除 {token.token_symbol}"
            }

    async def permanently_delete_potential_token(self, token_id: str) -> dict:
        """
        彻底删除潜力代币（设置 permanently_deleted=1）
        """
        from src.storage.models import PotentialToken
        from sqlalchemy import select
        from datetime import datetime

        await self._ensure_db()

        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(PotentialToken).where(PotentialToken.id == token_id)
            )
            token = result.scalar_one_or_none()

            if not token:
                raise ValueError(f"未找到ID为 {token_id} 的潜力代币")

            token.permanently_deleted = 1
            token.deleted_at = datetime.utcnow()
            await session.commit()

            logger.info(f"🗑️ 彻底删除潜力代币: {token.token_symbol}")

            return {
                "success": True,
                "message": f"已彻底删除 {token.token_symbol}"
            }
