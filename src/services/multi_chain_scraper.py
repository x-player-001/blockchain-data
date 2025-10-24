#!/usr/bin/env python3
"""
多链爬虫服务 - 使用 cloudscraper
支持 BSC 和 Solana 链
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select
import requests
import time

from src.storage.models import PotentialToken
from src.storage.db_manager import DatabaseManager
from src.services.dexscreener_service import DexScreenerService
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class MultiChainScraper:
    """多链爬虫服务"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager
        self._db_created = False
        self.dex_service = DexScreenerService()

    async def _ensure_db(self):
        """确保数据库已初始化"""
        if self.db_manager is None:
            self.db_manager = DatabaseManager()
            await self.db_manager.init_async_db()
            self._db_created = True

    async def close(self):
        """关闭连接"""
        if self._db_created and self.db_manager:
            await self.db_manager.close()

    def _get_correct_case_address(self, pair_address: str, chain: str) -> str:
        """
        获取正确大小写的地址（仅对 Solana）

        Args:
            pair_address: 小写的 pair 地址
            chain: 链名称

        Returns:
            正确大小写的地址，失败则返回原地址
        """
        if chain != 'solana':
            return pair_address

        try:
            url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                pairs = data.get('pairs', [])

                if pairs and len(pairs) > 0:
                    correct_address = pairs[0].get('pairAddress')
                    if correct_address:
                        logger.debug(f"    地址大小写修正: {pair_address} -> {correct_address}")
                        return correct_address

        except Exception as e:
            logger.debug(f"    获取正确地址失败: {e}")

        return pair_address

    async def scrape_and_save_multi_chain(
        self,
        chains: List[str] = ['bsc', 'solana'],
        count_per_chain: int = 100,
        top_n_per_chain: int = 10
    ) -> Dict[str, Any]:
        """
        爬取多条链并保存到 potential_tokens 表

        Args:
            chains: 链列表，如 ['bsc', 'solana']
            count_per_chain: 每条链爬取多少个代币
            top_n_per_chain: 每条链取前N个

        Returns:
            统计信息 {chain: {scraped, saved, skipped}}
        """
        logger.info("\n" + "="*80)
        logger.info("【多链爬取】开始爬取并保存潜力代币")
        logger.info("="*80)

        await self._ensure_db()

        results = {}
        total_saved = 0
        total_skipped = 0

        for chain in chains:
            logger.info(f"\n{'─'*80}")
            logger.info(f"爬取 {chain.upper()} 链...")
            logger.info(f"{'─'*80}")

            chain_result = await self._scrape_and_save_chain(
                chain=chain,
                count=count_per_chain,
                top_n=top_n_per_chain
            )

            results[chain] = chain_result
            total_saved += chain_result['saved']
            total_skipped += chain_result['skipped']

        logger.info("\n" + "="*80)
        logger.info(f"【总计】保存: {total_saved}, 跳过: {total_skipped}")
        logger.info("="*80 + "\n")

        return {
            'total_saved': total_saved,
            'total_skipped': total_skipped,
            'chains': results
        }

    async def _scrape_and_save_chain(
        self,
        chain: str,
        count: int,
        top_n: int
    ) -> Dict[str, Any]:
        """
        爬取单条链并保存

        Args:
            chain: 链名称
            count: 爬取数量
            top_n: 取前N个

        Returns:
            {scraped, saved, skipped}
        """
        # 1. 爬取数据
        tokens = self.dex_service.scrape_with_cloudscraper(
            chain=chain,
            limit=count
        )

        if not tokens:
            logger.warning(f"  {chain}: 未获取到数据")
            return {"scraped": 0, "saved": 0, "skipped": 0}

        logger.info(f"  ✓ 爬取到 {len(tokens)} 个代币")

        # 2. 过滤有24h涨幅的代币
        tokens_with_change = [
            t for t in tokens
            if t.get('price_change_24h') is not None
        ]

        logger.info(f"  ✓ 其中 {len(tokens_with_change)} 个有24h涨幅数据")

        # 3. 按24h涨幅排序取前N
        sorted_tokens = sorted(
            tokens_with_change,
            key=lambda x: x.get('price_change_24h', 0),
            reverse=True
        )
        top_gainers = sorted_tokens[:top_n]

        logger.info(f"\n  Top {len(top_gainers)} 涨幅榜:")
        logger.info(f"  {'-'*76}")
        for idx, token in enumerate(top_gainers, 1):
            symbol = token.get('token_symbol', 'N/A')
            change = token.get('price_change_24h', 0)
            price = token.get('price_usd', 0)
            logger.info(f"  {idx:2d}. {symbol:12s} +{change:>7.1f}%  ${price:.8f}")
        logger.info(f"  {'-'*76}\n")

        # 4. 对于 Solana 链，修正地址大小写
        if chain == 'solana':
            logger.info(f"  🔧 修正 Solana 地址大小写...")
            for token_data in top_gainers:
                old_address = token_data.get('pair_address', '')
                correct_address = self._get_correct_case_address(old_address, chain)
                if correct_address != old_address:
                    token_data['pair_address'] = correct_address
                    # 如果 token_address 也是 pair_address，同样修正
                    if token_data.get('token_address') == old_address:
                        token_data['token_address'] = correct_address
                # 避免API限流
                time.sleep(0.1)

        # 5. 保存到数据库
        saved_count = 0
        skipped_count = 0

        async with self.db_manager.get_session() as session:
            for token_data in top_gainers:
                try:
                    saved = await self._save_or_update_token(
                        session, token_data, chain
                    )
                    if saved:
                        saved_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    logger.error(f"  错误: {e}")
                    skipped_count += 1

            await session.commit()

        logger.info(f"  ✅ {chain}: 保存 {saved_count}, 跳过 {skipped_count}")

        return {
            "scraped": len(tokens),
            "saved": saved_count,
            "skipped": skipped_count
        }

    async def _save_or_update_token(
        self,
        session,
        token_data: Dict[str, Any],
        chain: str
    ) -> bool:
        """
        保存或更新代币到 potential_tokens 表

        更新策略：
        - 如果代币不存在：创建新记录
        - 如果代币已存在：
          - 新涨幅 > 原涨幅：更新所有字段
          - 新涨幅 <= 原涨幅：跳过

        Returns:
            True=保存/更新, False=跳过
        """
        pair_address = token_data.get('pair_address', '')
        token_symbol = token_data.get('token_symbol', 'N/A')
        token_name = token_data.get('token_name', 'Unknown')

        price_usd = token_data.get('price_usd', 0)
        price_change_24h = token_data.get('price_change_24h', 0)
        market_cap = token_data.get('market_cap', 0)
        liquidity_usd = token_data.get('liquidity_usd', 0)
        volume_24h = token_data.get('volume_24h', 0)
        dex_type = token_data.get('dex_type')  # Solana DEX type

        # 检查是否已存在（按 pair_address + chain）
        result = await session.execute(
            select(PotentialToken).where(
                PotentialToken.pair_address == pair_address,
                PotentialToken.chain == chain
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # 已存在，检查是否需要更新
            old_change = float(existing.price_change_24h_at_scrape or 0)

            if price_change_24h > old_change:
                # 新涨幅更高，更新
                existing.scraped_price_usd = price_usd
                existing.scraped_timestamp = datetime.utcnow()
                existing.market_cap_at_scrape = market_cap if market_cap > 0 else None
                existing.liquidity_at_scrape = liquidity_usd if liquidity_usd > 0 else None
                existing.volume_24h_at_scrape = volume_24h if volume_24h > 0 else None
                existing.price_change_24h_at_scrape = price_change_24h
                existing.dex_type = dex_type

                await session.flush()

                # 不再打印每个代币的更新信息，由调用方汇总
                return True
            else:
                # 涨幅未提高，跳过
                return False

        # 不存在，创建新记录
        # 注意：对于没有 token_address 的情况，使用 pair_address
        token_address = token_data.get('token_address', pair_address)

        potential_token = PotentialToken(
            chain=chain,
            token_address=token_address,
            token_symbol=token_symbol,
            token_name=token_name,
            dex_id='dexscreener',
            pair_address=pair_address,
            amm=None,
            dex_type=dex_type,
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

        # 不再打印每个代币的保存信息，由调用方汇总
        return True
