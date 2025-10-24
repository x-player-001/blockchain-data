#!/usr/bin/env python3
"""
Import DexScreener token data into database.
Parses JSON data and inserts into dexscreener_tokens table.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.db_manager import DatabaseManager
from src.storage.models import DexScreenerToken
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def parse_token_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse raw DexScreener token data into database fields.

    Args:
        raw_data: Raw token data from DexScreener JSON

    Returns:
        Parsed data dictionary for database insertion
    """
    # Extract base token info
    base_token = raw_data.get("baseToken", {})
    quote_token = raw_data.get("quoteToken", {})

    # Extract transaction data
    txns = raw_data.get("txns", {})
    txns_m5 = txns.get("m5", {})
    txns_h1 = txns.get("h1", {})
    txns_h6 = txns.get("h6", {})
    txns_h24 = txns.get("h24", {})

    # Extract volume data
    volume = raw_data.get("volume", {})

    # Extract price changes
    price_change = raw_data.get("priceChange", {})

    # Extract liquidity
    liquidity = raw_data.get("liquidity", {})

    # Extract info (social links, images)
    info = raw_data.get("info", {})
    websites = info.get("websites", [])
    socials = info.get("socials", [])

    # Parse social links
    website_url = websites[0].get("url") if websites else None
    twitter_url = None
    telegram_url = None

    for social in socials:
        if social.get("type") == "twitter":
            twitter_url = social.get("url")
        elif social.get("type") == "telegram":
            telegram_url = social.get("url")

    # Parse labels
    labels_list = raw_data.get("labels", [])
    labels_str = ",".join(labels_list) if labels_list else None

    return {
        "chain_id": raw_data.get("chainId"),
        "dex_id": raw_data.get("dexId"),
        "pair_address": raw_data.get("pairAddress"),

        # Base token
        "base_token_address": base_token.get("address"),
        "base_token_name": base_token.get("name"),
        "base_token_symbol": base_token.get("symbol"),

        # Quote token
        "quote_token_address": quote_token.get("address"),
        "quote_token_name": quote_token.get("name"),
        "quote_token_symbol": quote_token.get("symbol"),

        # Prices
        "price_native": raw_data.get("priceNative"),
        "price_usd": raw_data.get("priceUsd"),

        # Volumes
        "volume_m5": volume.get("m5"),
        "volume_h1": volume.get("h1"),
        "volume_h6": volume.get("h6"),
        "volume_h24": volume.get("h24"),

        # Transactions
        "txns_m5_buys": txns_m5.get("buys"),
        "txns_m5_sells": txns_m5.get("sells"),
        "txns_h1_buys": txns_h1.get("buys"),
        "txns_h1_sells": txns_h1.get("sells"),
        "txns_h6_buys": txns_h6.get("buys"),
        "txns_h6_sells": txns_h6.get("sells"),
        "txns_h24_buys": txns_h24.get("buys"),
        "txns_h24_sells": txns_h24.get("sells"),

        # Price changes
        "price_change_h1": price_change.get("h1"),
        "price_change_h6": price_change.get("h6"),
        "price_change_h24": price_change.get("h24"),

        # Liquidity
        "liquidity_usd": liquidity.get("usd"),
        "liquidity_base": liquidity.get("base"),
        "liquidity_quote": liquidity.get("quote"),

        # Market data
        "fdv": raw_data.get("fdv"),
        "market_cap": raw_data.get("marketCap"),

        # Pair creation time
        "pair_created_at": raw_data.get("pairCreatedAt"),

        # Additional info
        "image_url": info.get("imageUrl"),
        "website_url": website_url,
        "twitter_url": twitter_url,
        "telegram_url": telegram_url,
        "dexscreener_url": raw_data.get("url"),
        "labels": labels_str,
    }


async def import_tokens_from_json(json_file_path: str, db_manager: DatabaseManager):
    """
    Import tokens from JSON file into database.

    Args:
        json_file_path: Path to JSON file
        db_manager: Database manager instance
    """
    logger.info(f"Reading JSON file: {json_file_path}")

    # Read JSON file
    with open(json_file_path, 'r', encoding='utf-8') as f:
        tokens_data = json.load(f)

    logger.info(f"Found {len(tokens_data)} tokens in JSON file")

    # Parse and insert tokens
    inserted_count = 0
    updated_count = 0
    error_count = 0

    async with db_manager.get_session() as session:
        for idx, raw_token in enumerate(tokens_data, 1):
            try:
                # Parse token data
                parsed_data = parse_token_data(raw_token)
                pair_address = parsed_data.get("pair_address")

                if not pair_address:
                    logger.warning(f"Token {idx}: Missing pair address, skipping")
                    error_count += 1
                    continue

                # Check if token already exists
                from sqlalchemy import select
                result = await session.execute(
                    select(DexScreenerToken).where(
                        DexScreenerToken.pair_address == pair_address
                    )
                )
                existing_token = result.scalar_one_or_none()

                if existing_token:
                    # Update existing token
                    for key, value in parsed_data.items():
                        if key != 'pair_address':  # Don't update the unique key
                            setattr(existing_token, key, value)
                    existing_token.updated_at = datetime.utcnow()
                    updated_count += 1
                    logger.debug(f"[{idx}/{len(tokens_data)}] Updated: {parsed_data.get('base_token_symbol')} ({pair_address[:10]}...)")
                else:
                    # Insert new token
                    token = DexScreenerToken(**parsed_data)
                    session.add(token)
                    inserted_count += 1
                    logger.info(f"[{idx}/{len(tokens_data)}] Inserted: {parsed_data.get('base_token_symbol')} ({pair_address[:10]}...)")

                # Commit every 10 records
                if idx % 10 == 0:
                    await session.commit()
                    logger.info(f"Progress: {idx}/{len(tokens_data)} processed")

            except Exception as e:
                logger.error(f"Error processing token {idx}: {e}")
                error_count += 1
                continue

        # Final commit
        await session.commit()

    logger.info("=" * 60)
    logger.info(f"Import completed!")
    logger.info(f"  Inserted: {inserted_count}")
    logger.info(f"  Updated:  {updated_count}")
    logger.info(f"  Errors:   {error_count}")
    logger.info(f"  Total:    {len(tokens_data)}")
    logger.info("=" * 60)


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Import DexScreener tokens from JSON")
    parser.add_argument(
        "json_file",
        nargs="?",
        default="dexscreener_tokens.json",
        help="Path to JSON file (default: dexscreener_tokens.json)"
    )

    args = parser.parse_args()

    # Get absolute path
    if not Path(args.json_file).is_absolute():
        json_file = Path.cwd() / args.json_file
    else:
        json_file = Path(args.json_file)

    if not json_file.exists():
        logger.error(f"JSON file not found: {json_file}")
        sys.exit(1)

    logger.info("Starting DexScreener token import")
    logger.info(f"JSON file: {json_file}")

    # Initialize database
    db_manager = DatabaseManager()
    await db_manager.init_async_db()

    try:
        # Import tokens
        await import_tokens_from_json(str(json_file), db_manager)
    finally:
        # Close database connection
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
