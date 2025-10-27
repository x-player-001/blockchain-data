"""
K线数据更新服务
使用 GeckoTerminal API 拉取和增量更新K线数据
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..api_clients.geckoterminal_client import GeckoTerminalClient
from ..storage.db_manager import DatabaseManager
from ..storage.models import TokenKline, MonitoredToken, PotentialToken
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class KlineService:
    """K线数据更新服务"""

    def __init__(self):
        """初始化K线服务"""
        self.client = GeckoTerminalClient()
        self.db_manager = DatabaseManager()

    async def close(self):
        """关闭服务"""
        await self.db_manager.close()

    async def get_latest_kline_timestamp(
        self,
        session: AsyncSession,
        pair_address: str,
        timeframe: str = "minute",
        aggregate: int = 5
    ) -> Optional[int]:
        """
        获取指定交易对的最新K线时间戳

        Args:
            session: 数据库会话
            pair_address: 交易对地址
            timeframe: 时间周期
            aggregate: 聚合级别

        Returns:
            最新K线时间戳，如果没有数据则返回 None
        """
        result = await session.execute(
            select(TokenKline.timestamp)
            .where(
                and_(
                    TokenKline.pair_address == pair_address.lower(),
                    TokenKline.timeframe == timeframe,
                    TokenKline.aggregate == aggregate
                )
            )
            .order_by(desc(TokenKline.timestamp))
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        return latest

    async def save_klines(
        self,
        session: AsyncSession,
        token_address: str,
        pair_address: str,
        chain: str,
        klines: List[List[float]],
        timeframe: str = "minute",
        aggregate: int = 5
    ) -> Dict[str, int]:
        """
        保存K线数据到数据库（批量 UPSERT）

        Args:
            session: 数据库会话
            token_address: 代币地址
            pair_address: 交易对地址
            chain: 链名称
            klines: K线数据列表 [[timestamp, open, high, low, close, volume], ...]
            timeframe: 时间周期
            aggregate: 聚合级别

        Returns:
            统计信息 {saved: 新增数量, skipped: 跳过数量}
        """
        saved_count = 0
        skipped_count = 0

        for kline in klines:
            try:
                timestamp, open_price, high, low, close, volume = kline

                # 检查是否已存在（使用唯一索引）
                result = await session.execute(
                    select(TokenKline).where(
                        and_(
                            TokenKline.pair_address == pair_address.lower(),
                            TokenKline.timestamp == int(timestamp),
                            TokenKline.timeframe == timeframe,
                            TokenKline.aggregate == aggregate
                        )
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # 已存在，跳过（可以选择更新）
                    skipped_count += 1
                    continue

                # 创建新记录
                kline_record = TokenKline(
                    token_address=token_address.lower(),
                    pair_address=pair_address.lower(),
                    chain=chain,
                    timestamp=int(timestamp),
                    timeframe=timeframe,
                    aggregate=aggregate,
                    open=Decimal(str(open_price)),
                    high=Decimal(str(high)),
                    low=Decimal(str(low)),
                    close=Decimal(str(close)),
                    volume=Decimal(str(volume)),
                    data_source="geckoterminal"
                )

                session.add(kline_record)
                saved_count += 1

            except Exception as e:
                logger.error(f"Error saving kline for {pair_address} @ {timestamp}: {e}")
                continue

        # 批量提交
        await session.commit()

        return {"saved": saved_count, "skipped": skipped_count}

    async def update_token_klines(
        self,
        token_address: str,
        pair_address: str,
        chain: str = "bsc",
        timeframe: str = "minute",
        aggregate: int = 5,
        max_candles: int = 500
    ) -> Dict[str, Any]:
        """
        更新单个代币的K线数据（支持增量更新）

        Args:
            token_address: 代币地址
            pair_address: 交易对地址
            chain: 链名称
            timeframe: 时间周期 (minute/hour/day)
            aggregate: 聚合级别 (1/5/15 for minute, 1/4/12 for hour, 1 for day)
            max_candles: 最大拉取K线数量

        Returns:
            更新统计信息
        """
        stats = {
            "token_address": token_address,
            "pair_address": pair_address,
            "timeframe": f"{timeframe}/{aggregate}",
            "fetched": 0,
            "saved": 0,
            "skipped": 0,
            "success": False,
            "error": None,
            "is_incremental": False
        }

        try:
            async with self.db_manager.get_session() as session:
                # 查询最新K线时间戳
                latest_timestamp = await self.get_latest_kline_timestamp(
                    session, pair_address, timeframe, aggregate
                )

                if latest_timestamp:
                    # 增量更新：从最新时间戳开始拉取
                    stats["is_incremental"] = True
                    logger.info(
                        f"{token_address[:8]}... 增量更新K线，最新时间戳: {latest_timestamp} "
                        f"({datetime.fromtimestamp(latest_timestamp)})"
                    )

                    # 只拉取最新的数据（before_timestamp 不传，默认到现在）
                    klines = await self.client.get_ohlcv(
                        pool_address=pair_address,
                        timeframe=timeframe,
                        aggregate=aggregate,
                        network=chain
                    )

                    # 过滤：只保留比最新时间戳更新的K线
                    if klines:
                        klines = [k for k in klines if int(k[0]) > latest_timestamp]

                else:
                    # 首次拉取：获取历史数据
                    logger.info(
                        f"{token_address[:8]}... 首次拉取K线，最多 {max_candles} 根 (链: {chain})"
                    )
                    klines = await self.client.get_ohlcv_historical(
                        pool_address=pair_address,
                        timeframe=timeframe,
                        max_candles=max_candles,
                        aggregate=aggregate,
                        network=chain
                    )

                if not klines:
                    logger.warning(f"{token_address[:8]}... 未获取到K线数据")
                    stats["error"] = "No klines data"
                    return stats

                stats["fetched"] = len(klines)

                # 保存到数据库
                save_result = await self.save_klines(
                    session=session,
                    token_address=token_address,
                    pair_address=pair_address,
                    chain=chain,
                    klines=klines,
                    timeframe=timeframe,
                    aggregate=aggregate
                )

                stats["saved"] = save_result["saved"]
                stats["skipped"] = save_result["skipped"]
                stats["success"] = True

                logger.info(
                    f"✅ {token_address[:8]}... K线更新完成: "
                    f"拉取{stats['fetched']}根, 保存{stats['saved']}根, "
                    f"跳过{stats['skipped']}根"
                )

        except Exception as e:
            logger.error(f"❌ {token_address[:8]}... K线更新失败: {e}")
            stats["error"] = str(e)

        return stats

    async def update_monitored_tokens_klines(
        self,
        timeframe: str = "minute",
        aggregate: int = 5,
        max_candles: int = 500,
        delay: float = 0.5
    ) -> Dict[str, Any]:
        """
        批量更新监控代币的K线数据

        Args:
            timeframe: 时间周期
            aggregate: 聚合级别
            max_candles: 首次拉取的最大K线数
            delay: 每个代币之间的延迟（秒）

        Returns:
            更新统计
        """
        logger.info("=" * 80)
        logger.info(f"开始更新监控代币K线数据 ({timeframe}/{aggregate})")
        logger.info("=" * 80)

        total_stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "total_fetched": 0,
            "total_saved": 0
        }

        try:
            async with self.db_manager.get_session() as session:
                # 获取所有未删除的监控代币
                result = await session.execute(
                    select(MonitoredToken).where(
                        and_(
                            MonitoredToken.deleted_at.is_(None),
                            MonitoredToken.permanently_deleted == 0
                        )
                    )
                )
                tokens = result.scalars().all()

                if not tokens:
                    logger.info("没有监控代币需要更新K线")
                    return total_stats

                total_stats["total"] = len(tokens)
                logger.info(f"找到 {len(tokens)} 个监控代币")

            # 逐个更新
            for token in tokens:
                stats = await self.update_token_klines(
                    token_address=token.token_address,
                    pair_address=token.pair_address,
                    chain=token.chain,
                    timeframe=timeframe,
                    aggregate=aggregate,
                    max_candles=max_candles
                )

                if stats["success"]:
                    total_stats["success"] += 1
                    total_stats["total_fetched"] += stats["fetched"]
                    total_stats["total_saved"] += stats["saved"]
                else:
                    total_stats["failed"] += 1

                # 延迟避免API限流
                await asyncio.sleep(delay)

            logger.info("=" * 80)
            logger.info(
                f"✅ 监控代币K线更新完成: 总计{total_stats['total']}个, "
                f"成功{total_stats['success']}个, 失败{total_stats['failed']}个, "
                f"拉取{total_stats['total_fetched']}根, 保存{total_stats['total_saved']}根"
            )
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"批量更新监控代币K线失败: {e}", exc_info=True)

        return total_stats

    async def update_potential_tokens_klines(
        self,
        timeframe: str = "minute",
        aggregate: int = 5,
        max_candles: int = 500,
        delay: float = 0.5
    ) -> Dict[str, Any]:
        """
        批量更新潜力代币的K线数据

        Args:
            timeframe: 时间周期
            aggregate: 聚合级别
            max_candles: 首次拉取的最大K线数
            delay: 每个代币之间的延迟（秒）

        Returns:
            更新统计
        """
        logger.info("=" * 80)
        logger.info(f"开始更新潜力代币K线数据 ({timeframe}/{aggregate})")
        logger.info("=" * 80)

        total_stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "total_fetched": 0,
            "total_saved": 0
        }

        try:
            async with self.db_manager.get_session() as session:
                # 获取所有未删除且未添加到监控的潜力代币
                result = await session.execute(
                    select(PotentialToken).where(
                        and_(
                            PotentialToken.is_added_to_monitoring == 0,
                            PotentialToken.deleted_at.is_(None),
                            PotentialToken.permanently_deleted == 0
                        )
                    )
                )
                tokens = result.scalars().all()

                if not tokens:
                    logger.info("没有潜力代币需要更新K线")
                    return total_stats

                total_stats["total"] = len(tokens)
                logger.info(f"找到 {len(tokens)} 个潜力代币")

            # 逐个更新
            for token in tokens:
                stats = await self.update_token_klines(
                    token_address=token.token_address,
                    pair_address=token.pair_address,
                    chain=token.chain,
                    timeframe=timeframe,
                    aggregate=aggregate,
                    max_candles=max_candles
                )

                if stats["success"]:
                    total_stats["success"] += 1
                    total_stats["total_fetched"] += stats["fetched"]
                    total_stats["total_saved"] += stats["saved"]
                else:
                    total_stats["failed"] += 1

                # 延迟避免API限流
                await asyncio.sleep(delay)

            logger.info("=" * 80)
            logger.info(
                f"✅ 潜力代币K线更新完成: 总计{total_stats['total']}个, "
                f"成功{total_stats['success']}个, 失败{total_stats['failed']}个, "
                f"拉取{total_stats['total_fetched']}根, 保存{total_stats['total_saved']}根"
            )
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"批量更新潜力代币K线失败: {e}", exc_info=True)

        return total_stats

    async def update_all_tokens_klines(
        self,
        timeframe: str = "minute",
        aggregate: int = 5,
        max_candles: int = 500
    ) -> Dict[str, Any]:
        """
        统一更新所有代币的K线数据（监控代币 + 潜力代币）
        内部自动处理限流，确保不超过 GeckoTerminal API 限制（30 req/min）

        Args:
            timeframe: 时间周期 (minute/hour/day)
            aggregate: 聚合级别 (1/5/15 for minute, 1/4/12 for hour, 1 for day)
            max_candles: 首次拉取的最大K线数

        Returns:
            更新统计
        """
        logger.info("=" * 80)
        logger.info(f"开始统一更新所有代币K线数据 ({timeframe}/{aggregate})")
        logger.info("=" * 80)

        total_stats = {
            "monitored": 0,
            "potential": 0,
            "total": 0,
            "success": 0,
            "failed": 0,
            "total_fetched": 0,
            "total_saved": 0
        }

        try:
            # 1. 收集所有需要更新的代币
            all_tokens = []

            async with self.db_manager.get_session() as session:
                # 获取监控代币
                monitored_result = await session.execute(
                    select(MonitoredToken).where(
                        and_(
                            MonitoredToken.deleted_at.is_(None),
                            MonitoredToken.permanently_deleted == 0
                        )
                    )
                )
                monitored_tokens = monitored_result.scalars().all()
                for token in monitored_tokens:
                    all_tokens.append({
                        "type": "monitored",
                        "token_address": token.token_address,
                        "pair_address": token.pair_address,
                        "chain": token.chain,
                        "symbol": getattr(token, 'token_symbol', 'N/A')
                    })

                # 获取潜力代币
                potential_result = await session.execute(
                    select(PotentialToken).where(
                        and_(
                            PotentialToken.is_added_to_monitoring == 0,
                            PotentialToken.deleted_at.is_(None),
                            PotentialToken.permanently_deleted == 0
                        )
                    )
                )
                potential_tokens = potential_result.scalars().all()
                for token in potential_tokens:
                    all_tokens.append({
                        "type": "potential",
                        "token_address": token.token_address,
                        "pair_address": token.pair_address,
                        "chain": token.chain,
                        "symbol": getattr(token, 'token_symbol', 'N/A')
                    })

            if not all_tokens:
                logger.info("没有代币需要更新K线")
                return total_stats

            total_stats["monitored"] = len([t for t in all_tokens if t["type"] == "monitored"])
            total_stats["potential"] = len([t for t in all_tokens if t["type"] == "potential"])
            total_stats["total"] = len(all_tokens)

            logger.info(
                f"找到 {total_stats['total']} 个代币需要更新: "
                f"监控{total_stats['monitored']}个, 潜力{total_stats['potential']}个"
            )

            # 2. 自动计算安全的延迟时间
            # GeckoTerminal API 限制: 30 req/min = 0.5 req/sec
            # 为了安全，使用 25 req/min = 2.4 sec/req
            SAFE_DELAY = 2.5  # 秒
            estimated_time = len(all_tokens) * SAFE_DELAY
            logger.info(f"使用安全延迟: {SAFE_DELAY}秒/请求, 预计耗时: {estimated_time/60:.1f}分钟")

            # 3. 逐个更新，自动限流
            for idx, token_info in enumerate(all_tokens, 1):
                logger.info(
                    f"[{idx}/{len(all_tokens)}] 更新 {token_info['type']} 代币: "
                    f"{token_info['symbol']} ({token_info['token_address'][:8]}...)"
                )

                stats = await self.update_token_klines(
                    token_address=token_info["token_address"],
                    pair_address=token_info["pair_address"],
                    chain=token_info["chain"],
                    timeframe=timeframe,
                    aggregate=aggregate,
                    max_candles=max_candles
                )

                if stats["success"]:
                    total_stats["success"] += 1
                    total_stats["total_fetched"] += stats["fetched"]
                    total_stats["total_saved"] += stats["saved"]
                else:
                    total_stats["failed"] += 1

                # 自动限流：每次请求后延迟
                if idx < len(all_tokens):  # 最后一个不需要延迟
                    await asyncio.sleep(SAFE_DELAY)

            logger.info("=" * 80)
            logger.info(
                f"✅ K线更新完成: "
                f"总计{total_stats['total']}个 (监控{total_stats['monitored']}, 潜力{total_stats['potential']}), "
                f"成功{total_stats['success']}个, 失败{total_stats['failed']}个, "
                f"拉取{total_stats['total_fetched']}根, 保存{total_stats['total_saved']}根"
            )
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"统一更新K线失败: {e}", exc_info=True)

        return total_stats
