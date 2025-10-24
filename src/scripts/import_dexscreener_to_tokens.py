#!/usr/bin/env python3
"""
将DexScreener代币导入到tokens和token_pairs表
这样可以使用现有的K线收集器
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy import text
import uuid

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.db_manager import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def import_dexscreener_tokens():
    """将DexScreener代币导入到tokens和token_pairs表"""

    db = DatabaseManager()
    await db.init_async_db()

    try:
        async with db.get_session() as session:
            # 获取DexScreener代币
            result = await session.execute(text("""
                SELECT
                    pair_address,
                    base_token_address,
                    base_token_symbol,
                    base_token_name,
                    chain_id,
                    dex_id,
                    price_usd,
                    liquidity_usd,
                    volume_h24,
                    market_cap,
                    pair_created_at
                FROM dexscreener_tokens
                ORDER BY liquidity_usd DESC NULLS LAST
            """))

            dex_tokens = result.fetchall()

            if not dex_tokens:
                logger.warning("未找到DexScreener代币")
                return

            logger.info(f"找到 {len(dex_tokens)} 个DexScreener代币")

            inserted_tokens = 0
            updated_tokens = 0
            inserted_pairs = 0
            updated_pairs = 0

            for dex_token in dex_tokens:
                pair_address = dex_token[0]
                base_token_address = dex_token[1]
                symbol = dex_token[2] or 'UNKNOWN'
                name = dex_token[3] or 'Unknown Token'
                chain_id = dex_token[4]
                dex_id = dex_token[5]
                price_usd = float(dex_token[6]) if dex_token[6] else 0
                liquidity_usd = float(dex_token[7]) if dex_token[7] else 0
                volume_24h = float(dex_token[8]) if dex_token[8] else 0
                market_cap = float(dex_token[9]) if dex_token[9] else 0
                pair_created_at_ms = dex_token[10]

                # 转换时间戳
                pair_created_at = None
                if pair_created_at_ms:
                    pair_created_at = datetime.fromtimestamp(pair_created_at_ms / 1000)

                # 检查token是否已存在（基于base_token_address）
                result = await session.execute(text("""
                    SELECT id FROM tokens WHERE address = :address
                """), {"address": base_token_address.lower()})

                existing_token = result.scalar()

                if existing_token:
                    token_id = existing_token
                    # 更新token基本信息
                    await session.execute(text("""
                        UPDATE tokens
                        SET
                            symbol = :symbol,
                            name = :name,
                            updated_at = :updated_at
                        WHERE id = :token_id
                    """), {
                        "token_id": token_id,
                        "symbol": symbol,
                        "name": name,
                        "updated_at": datetime.utcnow()
                    })
                    updated_tokens += 1
                    logger.debug(f"更新token: {symbol} ({token_id})")
                else:
                    # 插入新token
                    token_id = str(uuid.uuid4())
                    await session.execute(text("""
                        INSERT INTO tokens (
                            id, address, symbol, name,
                            data_source, created_at, updated_at
                        ) VALUES (
                            :id, :address, :symbol, :name,
                            :data_source, :created_at, :updated_at
                        )
                    """), {
                        "id": token_id,
                        "address": base_token_address.lower(),
                        "symbol": symbol,
                        "name": name,
                        "data_source": "dexscreener",
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    })
                    inserted_tokens += 1
                    logger.info(f"插入token: {symbol} ({token_id})")

                # 检查token_pair是否已存在
                result = await session.execute(text("""
                    SELECT id FROM token_pairs
                    WHERE token_id = :token_id AND pair_address = :pair_address
                """), {"token_id": token_id, "pair_address": pair_address})

                existing_pair = result.scalar()

                if existing_pair:
                    # 更新pair信息
                    await session.execute(text("""
                        UPDATE token_pairs
                        SET
                            dex_name = :dex_name,
                            liquidity_usd = :liquidity_usd,
                            volume_24h = :volume_24h,
                            pair_created_at = COALESCE(pair_created_at, :pair_created_at),
                            updated_at = :updated_at
                        WHERE id = :pair_id
                    """), {
                        "pair_id": existing_pair,
                        "dex_name": dex_id,
                        "liquidity_usd": liquidity_usd,
                        "volume_24h": volume_24h,
                        "pair_created_at": pair_created_at,
                        "updated_at": datetime.utcnow()
                    })
                    updated_pairs += 1
                    logger.debug(f"更新pair: {symbol} - {pair_address[:10]}...")
                else:
                    # 插入新pair
                    pair_id = str(uuid.uuid4())
                    await session.execute(text("""
                        INSERT INTO token_pairs (
                            id, token_id, pair_address, dex_name, base_token,
                            liquidity_usd, volume_24h, pair_created_at,
                            created_at, updated_at
                        ) VALUES (
                            :id, :token_id, :pair_address, :dex_name, :base_token,
                            :liquidity_usd, :volume_24h, :pair_created_at,
                            :created_at, :updated_at
                        )
                    """), {
                        "id": pair_id,
                        "token_id": token_id,
                        "pair_address": pair_address,
                        "dex_name": dex_id,
                        "base_token": symbol,
                        "liquidity_usd": liquidity_usd,
                        "volume_24h": volume_24h,
                        "pair_created_at": pair_created_at,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    })
                    inserted_pairs += 1
                    logger.info(f"插入pair: {symbol} - {pair_address[:10]}...")

            # 提交所有更改
            await session.commit()

            logger.info("\n" + "=" * 80)
            logger.info("导入完成！")
            logger.info("=" * 80)
            logger.info(f"Tokens - 插入: {inserted_tokens}, 更新: {updated_tokens}")
            logger.info(f"Pairs  - 插入: {inserted_pairs}, 更新: {updated_pairs}")
            logger.info("=" * 80)

    finally:
        await db.close()


async def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("导入DexScreener代币到tokens和token_pairs表")
    logger.info("=" * 80)

    await import_dexscreener_tokens()

    logger.info("\n完成！现在可以使用K线收集器了")


if __name__ == "__main__":
    asyncio.run(main())
