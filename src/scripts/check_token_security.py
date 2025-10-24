"""Check token security using GoPlus API and filter out non-open-source tokens."""
import asyncio
from sqlalchemy import text

from ..api_clients.goplus_client import GoPlusClient
from ..storage.db_manager import db_manager
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


async def check_and_filter_tokens(
    chain_id: str = "56",
    require_open_source: bool = True,
    batch_size: int = 10,
    dry_run: bool = False
):
    """
    Check all tokens in database for security and filter out unsafe ones.

    Args:
        chain_id: Blockchain ID (56 for BSC)
        require_open_source: Require contracts to be open source
        batch_size: Number of tokens to check per batch
        dry_run: If True, only report what would be deleted without actually deleting
    """
    logger.info("=" * 80)
    logger.info("Token Security Check and Filter")
    logger.info("=" * 80)
    logger.info(f"Chain ID: {chain_id}")
    logger.info(f"Require open source: {require_open_source}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("")

    # Initialize database
    await db_manager.init_async_db()

    # Get all token addresses from database
    async with db_manager.get_session() as session:
        result = await session.execute(text("""
            SELECT id, address, symbol, name, data_source
            FROM tokens
            ORDER BY created_at DESC
        """))
        tokens = result.fetchall()

    if not tokens:
        logger.info("No tokens found in database")
        return

    logger.info(f"Found {len(tokens)} tokens in database")

    # Extract addresses
    token_map = {}  # address -> token data
    addresses = []

    for token in tokens:
        token_id, address, symbol, name, data_source = token
        token_map[address.lower()] = {
            "id": token_id,
            "address": address,
            "symbol": symbol,
            "name": name,
            "data_source": data_source
        }
        addresses.append(address)

    # Check security in batches
    client = GoPlusClient()
    async with client:
        security_results = await client.batch_check_security(
            chain_id=chain_id,
            contract_addresses=addresses,
            batch_size=batch_size
        )

    # Analyze results
    safe_tokens = []
    unsafe_tokens = []
    no_data_tokens = []

    for address in addresses:
        addr_lower = address.lower()
        token_info = token_map[addr_lower]
        security_data = security_results.get(addr_lower)

        if not security_data:
            no_data_tokens.append(token_info)
            logger.warning(f"No security data for {token_info['symbol']} ({address})")
            continue

        is_safe = client.is_safe_token(security_data, require_open_source=require_open_source)

        if is_safe:
            safe_tokens.append(token_info)
        else:
            reason = []
            if not client.is_open_source(security_data):
                reason.append("NOT_OPEN_SOURCE")
            if security_data.get("is_honeypot") == "1":
                reason.append("HONEYPOT")
            if security_data.get("cannot_buy") == "1":
                reason.append("CANNOT_BUY")
            if security_data.get("cannot_sell_all") == "1":
                reason.append("CANNOT_SELL_ALL")
            if security_data.get("honeypot_with_same_creator") == "1":
                reason.append("CREATOR_HONEYPOT_HISTORY")

            unsafe_tokens.append({
                **token_info,
                "reason": ", ".join(reason)
            })

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("SECURITY CHECK SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total tokens checked:     {len(tokens):>6}")
    logger.info(f"Safe tokens:              {len(safe_tokens):>6}")
    logger.info(f"Unsafe tokens:            {len(unsafe_tokens):>6}")
    logger.info(f"No security data:         {len(no_data_tokens):>6}")
    logger.info("=" * 80)

    # Show unsafe tokens
    if unsafe_tokens:
        logger.info("\nUNSAFE TOKENS (to be removed):")
        logger.info("-" * 80)
        for token in unsafe_tokens:
            logger.info(f"  {token['symbol']:10} | {token['address']} | {token['reason']}")

    # Delete unsafe tokens if not dry run
    if unsafe_tokens and not dry_run:
        logger.info(f"\nDeleting {len(unsafe_tokens)} unsafe tokens...")

        token_ids_to_delete = [t["id"] for t in unsafe_tokens]

        async with db_manager.get_session() as session:
            # Delete in order to avoid foreign key violations
            await session.execute(text("""
                DELETE FROM token_metrics WHERE token_id = ANY(:ids)
            """), {"ids": token_ids_to_delete})

            await session.execute(text("""
                DELETE FROM token_ohlcv WHERE token_id = ANY(:ids)
            """), {"ids": token_ids_to_delete})

            await session.execute(text("""
                DELETE FROM token_pairs WHERE token_id = ANY(:ids)
            """), {"ids": token_ids_to_delete})

            await session.execute(text("""
                DELETE FROM token_deployments WHERE token_id = ANY(:ids)
            """), {"ids": token_ids_to_delete})

            await session.execute(text("""
                DELETE FROM early_trades WHERE token_id = ANY(:ids)
            """), {"ids": token_ids_to_delete})

            await session.execute(text("""
                DELETE FROM tokens WHERE id = ANY(:ids)
            """), {"ids": token_ids_to_delete})

            await session.commit()

        logger.info(f"✓ Deleted {len(unsafe_tokens)} unsafe tokens")

        # Show final stats
        async with db_manager.get_session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM tokens"))
            remaining_count = result.scalar()

        logger.info(f"\n✓ Remaining tokens in database: {remaining_count}")

    elif unsafe_tokens and dry_run:
        logger.info(f"\n[DRY RUN] Would delete {len(unsafe_tokens)} unsafe tokens")

    await db_manager.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check token security and filter unsafe tokens")
    parser.add_argument("--chain-id", type=str, default="56", help="Chain ID (default: 56 for BSC)")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for API calls")
    parser.add_argument("--allow-closed-source", action="store_true", help="Allow non-open-source contracts")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be deleted")

    args = parser.parse_args()

    asyncio.run(check_and_filter_tokens(
        chain_id=args.chain_id,
        require_open_source=not args.allow_closed_source,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    ))
