"""Main application entry point with CLI."""
import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from .collectors.dex_collector import DexCollector
from .analyzers.market_analyzer import MarketAnalyzer
from .filters.market_cap_filter import MarketCapFilter, VolumeFilter, CompositeFilter
from .storage.db_manager import db_manager
from .utils.config import config
from .utils.logger import setup_logger
from .utils.helpers import format_market_cap, format_percentage

logger = setup_logger(__name__)
console = Console()


class BlockchainDataApp:
    """Main application class."""

    def __init__(self):
        """Initialize application."""
        self.collector = DexCollector()
        self.analyzer = MarketAnalyzer()

    async def initialize(self):
        """Initialize database and resources."""
        logger.info("Initializing application...")

        # Initialize database
        await db_manager.init_async_db()

        logger.info("Application initialized successfully")

    async def collect_data(
        self,
        min_market_cap: float = None,
        save_to_db: bool = True,
        separate_sources: bool = False
    ):
        """
        Collect token data.

        Args:
            min_market_cap: Minimum market cap filter
            save_to_db: Whether to save to database
            separate_sources: Whether to save sources separately (for comparison)
        """
        min_cap = min_market_cap or config.MIN_MARKET_CAP

        console.print(f"\n[bold blue]Collecting token data (min market cap: ${min_cap:,.0f})...[/bold blue]\n")

        if separate_sources:
            # Collect from each source separately
            console.print("[yellow]Collecting from sources separately (no merging)...[/yellow]\n")

            # Collect from DexScreener
            dex_tokens = await self.collector.collect_from_dexscreener()
            console.print(f"[cyan]DexScreener: {len(dex_tokens)} tokens[/cyan]")

            # Collect from GeckoTerminal
            gecko_tokens = await self.collector.collect_from_geckoterminal()
            console.print(f"[cyan]GeckoTerminal: {len(gecko_tokens)} tokens[/cyan]\n")

            # Filter by market cap
            dex_filtered = [t for t in dex_tokens if t.get("market_cap", 0) >= min_cap]
            gecko_filtered = [t for t in gecko_tokens if t.get("market_cap", 0) >= min_cap]

            console.print(f"[green]After filtering (market cap >= ${min_cap:,.0f}):[/green]")
            console.print(f"  DexScreener: {len(dex_filtered)} tokens")
            console.print(f"  GeckoTerminal: {len(gecko_filtered)} tokens\n")

            # Save to database
            if save_to_db:
                result = await self.collector.save_separate_sources(dex_filtered, gecko_filtered)
                console.print(f"[green]Saved to database:[/green]")
                console.print(f"  DexScreener: {result['dexscreener']} tokens")
                console.print(f"  GeckoTerminal: {result['geckoterminal']} tokens")
                console.print(f"  Total: {result['total']} records\n")

            return {"dexscreener": dex_filtered, "geckoterminal": gecko_filtered}

        else:
            # Original merged collection
            tokens = await self.collector.collect(min_market_cap=min_cap)
            console.print(f"[green]Collected {len(tokens)} tokens (merged)[/green]\n")

            # Save to database
            if save_to_db and tokens:
                saved_count = await self.collector.save_to_database(tokens, source="merged")
                console.print(f"[green]Saved {saved_count} tokens to database[/green]\n")

            return tokens

    async def query_tokens(
        self,
        min_market_cap: float = None,
        limit: int = None
    ):
        """
        Query tokens from database.

        Args:
            min_market_cap: Minimum market cap filter
            limit: Maximum number of results
        """
        min_cap = min_market_cap or config.MIN_MARKET_CAP

        console.print(f"\n[bold blue]Querying tokens (min market cap: ${min_cap:,.0f})...[/bold blue]\n")

        tokens = await db_manager.get_tokens_by_market_cap(min_cap, limit)

        if not tokens:
            console.print("[yellow]No tokens found[/yellow]")
            return []

        # Display results in table
        table = Table(title=f"Tokens (Market Cap >= ${min_cap:,.0f})")
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Price", justify="right", style="green")
        table.add_column("Market Cap", justify="right", style="yellow")
        table.add_column("24h Change", justify="right")
        table.add_column("Volume 24h", justify="right", style="blue")

        for token in tokens[:limit] if limit else tokens:
            price_change = token.get("price_change_24h", 0)
            change_color = "green" if price_change >= 0 else "red"
            change_str = f"[{change_color}]{format_percentage(price_change)}[/{change_color}]"

            table.add_row(
                token["symbol"],
                token["name"][:30],
                f"${token.get('price_usd', 0):,.4f}",
                format_market_cap(token.get("market_cap", 0)),
                change_str,
                format_market_cap(token.get("volume_24h", 0))
            )

        console.print(table)
        console.print(f"\n[green]Total: {len(tokens)} tokens[/green]\n")

        return tokens

    async def analyze_market(
        self,
        min_market_cap: float = None
    ):
        """
        Analyze market data.

        Args:
            min_market_cap: Minimum market cap filter
        """
        min_cap = min_market_cap or config.MIN_MARKET_CAP

        console.print(f"\n[bold blue]Analyzing market data...[/bold blue]\n")

        # Get tokens from database
        tokens = await db_manager.get_tokens_by_market_cap(min_cap)

        if not tokens:
            console.print("[yellow]No tokens found for analysis[/yellow]")
            return

        # Analyze
        analysis = self.analyzer.analyze_tokens(tokens)

        # Format and display report
        report = self.analyzer.format_analysis_report(analysis)
        console.print(report)

    async def close(self):
        """Clean up resources."""
        await self.collector.close()
        await db_manager.close()


@click.group()
def cli():
    """BSC Token Data Collection and Analysis Tool."""
    pass


@cli.command()
@click.option("--min-market-cap", type=float, default=None, help="Minimum market cap in USD")
@click.option("--no-save", is_flag=True, help="Don't save to database")
@click.option("--separate", is_flag=True, help="Save sources separately (for comparison)")
def collect(min_market_cap, no_save, separate):
    """Collect token data from DEX aggregators."""
    async def run():
        app = BlockchainDataApp()
        try:
            await app.initialize()
            await app.collect_data(
                min_market_cap=min_market_cap,
                save_to_db=not no_save,
                separate_sources=separate
            )
        finally:
            await app.close()

    asyncio.run(run())


@cli.command()
@click.option("--min-market-cap", type=float, default=None, help="Minimum market cap in USD")
@click.option("--limit", type=int, default=None, help="Maximum number of results")
def query(min_market_cap, limit):
    """Query tokens from database."""
    async def run():
        app = BlockchainDataApp()
        try:
            await app.initialize()
            await app.query_tokens(
                min_market_cap=min_market_cap,
                limit=limit
            )
        finally:
            await app.close()

    asyncio.run(run())


@cli.command()
@click.option("--min-market-cap", type=float, default=None, help="Minimum market cap in USD")
def analyze(min_market_cap):
    """Analyze market data."""
    async def run():
        app = BlockchainDataApp()
        try:
            await app.initialize()
            await app.analyze_market(min_market_cap=min_market_cap)
        finally:
            await app.close()

    asyncio.run(run())


@cli.command()
def health():
    """Check health of data sources."""
    async def run():
        app = BlockchainDataApp()
        try:
            console.print("\n[bold blue]Checking data source health...[/bold blue]\n")

            is_healthy = await app.collector.health_check()

            if is_healthy:
                console.print("[green]All data sources are healthy![/green]\n")
            else:
                console.print("[red]Some data sources are unavailable[/red]\n")

        finally:
            await app.close()

    asyncio.run(run())


@cli.command()
def init_db():
    """Initialize database."""
    async def run():
        console.print("\n[bold blue]Initializing database...[/bold blue]\n")
        await db_manager.init_async_db()
        console.print("[green]Database initialized successfully![/green]\n")

    asyncio.run(run())


@cli.command()
@click.option("--timeframe", type=click.Choice(['minute', 'hour', 'day']), default='day', help="OHLCV timeframe")
@click.option("--limit", type=int, default=None, help="Limit number of tokens to collect")
@click.option("--max-candles", type=int, default=100, help="Maximum candles per token (100-1000)")
def collect_ohlcv(timeframe, limit, max_candles):
    """Collect OHLCV (candlestick) data for tokens."""
    async def run():
        from .api_clients.geckoterminal_client import GeckoTerminalClient

        app = BlockchainDataApp()
        try:
            await app.initialize()

            console.print(f"\n[bold blue]Collecting {timeframe} OHLCV data (up to {max_candles} candles per token)...[/bold blue]\n")

            # Get tokens with pool addresses
            query = """
            SELECT t.id, t.symbol, t.name, tp.pair_address as pool_address
            FROM tokens t
            JOIN token_pairs tp ON t.id = tp.token_id
            """
            if limit:
                query += f" LIMIT {limit}"

            async with db_manager.get_session() as session:
                result = await session.execute(text(query))
                tokens_with_pools = result.fetchall()

            if not tokens_with_pools:
                console.print("[yellow]No tokens with pool addresses found[/yellow]")
                return

            console.print(f"Found {len(tokens_with_pools)} tokens with pool addresses\n")

            # Collect OHLCV data
            client = GeckoTerminalClient()
            total_inserted = 0

            async with client:
                for token in tokens_with_pools:
                    token_id, symbol, name, pool_address = token

                    try:
                        console.print(f"Fetching {timeframe} data for [cyan]{symbol}[/cyan] ({pool_address[:10]}...)...")

                        # Use historical method if max_candles > 100
                        if max_candles > 100:
                            ohlcv_data = await client.get_ohlcv_historical(
                                pool_address=pool_address,
                                timeframe=timeframe,
                                max_candles=max_candles
                            )
                        else:
                            ohlcv_data = await client.get_ohlcv(pool_address, timeframe)

                        if ohlcv_data:
                            inserted = await db_manager.batch_insert_ohlcv(
                                token_id=token_id,
                                pool_address=pool_address,
                                timeframe=timeframe,
                                ohlcv_data=ohlcv_data
                            )
                            total_inserted += inserted
                            console.print(f"  ✓ Inserted {inserted} candles for {symbol}")
                        else:
                            console.print(f"  ✗ No data for {symbol}")

                    except Exception as e:
                        console.print(f"  ✗ Error for {symbol}: {e}")
                        continue

            console.print(f"\n[green]Total: Inserted {total_inserted} OHLCV records[/green]\n")

        finally:
            await app.close()

    asyncio.run(run())


@cli.command()
@click.option("--limit", type=int, default=None, help="Limit number of tokens to analyze")
def analyze_deployment(limit):
    """Analyze token deployment info and deployer fund flow."""
    async def run():
        from .collectors.onchain_collector import OnChainCollector

        app = BlockchainDataApp()
        try:
            await app.initialize()

            console.print(f"\n[bold blue]Analyzing Token Deployments...[/bold blue]\n")

            # Get tokens from database
            query = """
            SELECT t.id, t.address, t.symbol, t.name
            FROM tokens t
            LEFT JOIN token_deployments td ON t.id = td.token_id
            WHERE td.id IS NULL
            """
            if limit:
                query += f" LIMIT {limit}"

            async with db_manager.get_session() as session:
                result = await session.execute(text(query))
                tokens_without_deployment = result.fetchall()

            if not tokens_without_deployment:
                console.print("[yellow]No tokens without deployment info found[/yellow]")
                return

            console.print(f"Found {len(tokens_without_deployment)} tokens without deployment info\n")

            collector = OnChainCollector()

            for token in tokens_without_deployment:
                token_id, token_address, symbol, name = token

                try:
                    console.print(f"Analyzing [cyan]{symbol}[/cyan] ({token_address[:10]}...)...")

                    # Collect deployment info
                    deployment_info = await collector.collect_deployment_info(token_address, token_id)

                    if deployment_info:
                        deployer = deployment_info["deployer_address"]
                        console.print(f"  Deployer: {deployer}")
                        console.print(f"  Block: {deployment_info['deploy_block']}")
                        console.print(f"  Time: {deployment_info['deploy_timestamp']}")

                        # Analyze fund flow
                        flow_analysis = await collector.analyze_fund_flow(deployer)
                        console.print(f"  Total Inflow: {flow_analysis['total_inflow']:.2f} BNB")
                        console.print(f"  Total Outflow: {flow_analysis['total_outflow']:.2f} BNB")

                        if flow_analysis['top_inflows']:
                            console.print(f"  Top Funder: {flow_analysis['top_inflows'][0]['address'][:10]}... ({flow_analysis['top_inflows'][0]['total_bnb']:.2f} BNB)")

                    console.print("")

                except Exception as e:
                    console.print(f"  ✗ Error: {e}\n")
                    continue

            await collector.close()
            console.print("[green]Analysis complete![/green]\n")

        finally:
            await app.close()

    asyncio.run(run())


@cli.command()
@click.option("--minutes", type=int, default=5, help="Minutes after deployment to analyze")
@click.option("--limit", type=int, default=None, help="Limit number of tokens")
def analyze_early_trades(minutes, limit):
    """Analyze early trades after token deployment."""
    async def run():
        from .collectors.onchain_collector import OnChainCollector

        app = BlockchainDataApp()
        try:
            await app.initialize()

            console.print(f"\n[bold blue]Analyzing Early Trades (first {minutes} minutes)...[/bold blue]\n")

            # Get tokens with deployment info
            query = """
            SELECT t.id, t.address, t.symbol, td.deploy_timestamp
            FROM tokens t
            JOIN token_deployments td ON t.id = td.token_id
            """
            if limit:
                query += f" LIMIT {limit}"

            async with db_manager.get_session() as session:
                result = await session.execute(text(query))
                tokens = result.fetchall()

            if not tokens:
                console.print("[yellow]No tokens with deployment info found. Run 'analyze-deployment' first.[/yellow]")
                return

            console.print(f"Analyzing {len(tokens)} tokens\n")

            collector = OnChainCollector()

            for token in tokens:
                token_id, token_address, symbol, deploy_timestamp = token

                try:
                    console.print(f"Analyzing [cyan]{symbol}[/cyan] early trades...")

                    # Collect early trades
                    early_trades = await collector.collect_early_trades(
                        token_address=token_address,
                        token_id=token_id,
                        deploy_timestamp=deploy_timestamp,
                        minutes=minutes
                    )

                    if early_trades:
                        console.print(f"  Found {len(early_trades)} trades")

                        # Count unique traders
                        unique_traders = len(set(trade['trader_address'] for trade in early_trades))
                        console.print(f"  Unique traders: {unique_traders}")

                        # Show first few trades
                        for trade in early_trades[:3]:
                            console.print(f"    +{trade['seconds_after_deploy']}s: {trade['trade_type']} by {trade['trader_address'][:10]}...")

                    console.print("")

                except Exception as e:
                    console.print(f"  ✗ Error: {e}\n")
                    continue

            await collector.close()
            console.print("[green]Early trade analysis complete![/green]\n")

        finally:
            await app.close()

    asyncio.run(run())


@cli.command()
@click.option("--min-market-cap", type=float, default=1000000, help="Minimum market cap in USD")
@click.option("--limit", type=int, default=300, help="Maximum number of tokens")
@click.option("--chain", type=str, default="bsc", help="Blockchain name")
def collect_ave_tokens(min_market_cap, limit, chain):
    """Collect tokens from AVE API with market cap filter."""
    async def run():
        from .collectors.ave_collector import AveCollector

        app = BlockchainDataApp()
        try:
            await app.initialize()

            console.print(f"\n[bold blue]Collecting tokens from AVE API...[/bold blue]")
            console.print(f"Chain: {chain}")
            console.print(f"Min Market Cap: ${min_market_cap:,.0f}")
            console.print(f"Limit: {limit}\n")

            collector = AveCollector()
            tokens = await collector.collect_tokens(
                chain=chain,
                min_market_cap=min_market_cap,
                limit=limit
            )

            if tokens:
                console.print(f"\n[green]✓ Collected {len(tokens)} tokens from AVE API[/green]\n")

                # Show sample
                table = Table(title="Sample Tokens (First 10)")
                table.add_column("Symbol", style="cyan")
                table.add_column("Name", style="white")
                table.add_column("Market Cap", style="green")
                table.add_column("Price", style="yellow")
                table.add_column("24h Volume", style="magenta")

                for token in tokens[:10]:
                    mc = token.get("market_cap") or token.get("marketCap") or 0
                    price = token.get("current_price_usd") or token.get("price_usd") or token.get("price") or 0
                    vol = token.get("tx_volume_u_24h") or token.get("volume_24h") or 0

                    # Convert to float if string
                    try:
                        mc = float(mc) if mc else 0
                        price = float(price) if price else 0
                        vol = float(vol) if vol else 0
                    except (ValueError, TypeError):
                        mc, price, vol = 0, 0, 0

                    table.add_row(
                        token.get("symbol", "N/A"),
                        (token.get("name") or "N/A")[:30],
                        f"${mc:,.0f}" if mc else "N/A",
                        f"${price:.6f}" if price else "N/A",
                        f"${vol:,.0f}" if vol else "N/A"
                    )

                console.print(table)
            else:
                console.print("[yellow]No tokens found[/yellow]")

        finally:
            await app.close()

    asyncio.run(run())


@cli.command()
@click.option("--interval", type=int, default=1440, help="Interval in minutes (1440=1day)")
@click.option("--limit", type=int, default=1000, help="Max candles per token")
@click.option("--max-tokens", type=int, default=None, help="Max tokens to process")
@click.option("--skip-existing/--no-skip-existing", default=True, help="Enable incremental update (default: True)")
def collect_ave_ohlcv(interval, limit, max_tokens, skip_existing):
    """Collect OHLCV data from AVE API with true incremental updates."""
    async def run():
        from .collectors.ave_ohlcv_collector import AveOHLCVCollector

        app = BlockchainDataApp()
        try:
            await app.initialize()

            console.print(f"\n[bold blue]Collecting OHLCV from AVE API...[/bold blue]")
            console.print(f"Interval: {interval} minutes")
            console.print(f"Candles per token: {limit}")
            console.print(f"Max tokens: {max_tokens or 'All'}")
            console.print(f"Incremental update: {skip_existing}\n")

            collector = AveOHLCVCollector()
            stats = await collector.collect_all(
                interval=interval,
                limit=limit,
                skip_existing=skip_existing,
                max_tokens=max_tokens
            )

            console.print(f"\n[green]✓ OHLCV Collection Complete[/green]")
            console.print(f"Total tokens: {stats['total_tokens']}")
            console.print(f"Successful: {stats['successful']}")
            console.print(f"Skipped: {stats['skipped']}")
            console.print(f"Failed: {stats['failed']}")
            console.print(f"Total candles: {stats['total_candles']}\n")

        finally:
            await app.close()

    asyncio.run(run())


@cli.command()
@click.option("--ave-min-mc", type=float, default=1000000, help="AVE minimum market cap (default: $1M)")
@click.option("--gecko-min-mc", type=float, default=100000, help="GeckoTerminal minimum market cap (default: $100K)")
@click.option("--gecko-pages", type=int, default=10, help="GeckoTerminal pages to fetch (default: 10)")
@click.option("--paprika-min-mc", type=float, default=1000000, help="DexPaprika minimum market cap (default: $1M)")
@click.option("--paprika-limit", type=int, default=100, help="DexPaprika pools per sort strategy (default: 100)")
@click.option("--max-age-days", type=int, default=30, help="Only collect tokens created within last X days (default: 30)")
# @click.option("--dex-min-liq", type=float, default=50000, help="DexScreener minimum liquidity (default: $50K)")  # DISABLED
# @click.option("--dex-limit", type=int, default=100, help="DexScreener token limit (default: 100)")  # DISABLED
def collect_multi_source(ave_min_mc, gecko_min_mc, gecko_pages, paprika_min_mc, paprika_limit, max_age_days):  # Removed: dex_min_liq, dex_limit
    """Collect tokens from AVE, GeckoTerminal and DexPaprika with automatic deduplication."""
    async def run():
        from .collectors.multi_source_collector import MultiSourceCollector

        try:
            await db_manager.init_async_db()

            collector = MultiSourceCollector()
            stats = await collector.collect_all(
                ave_min_market_cap=ave_min_mc,
                gecko_min_market_cap=gecko_min_mc,
                gecko_pages=gecko_pages,
                paprika_min_market_cap=paprika_min_mc,
                paprika_limit_per_sort=paprika_limit,
                max_token_age_days=max_age_days,
                # dex_min_liquidity=dex_min_liq,  # DISABLED
                # dex_limit=dex_limit  # DISABLED
            )

            console.print(f"\n[bold green]✓ Collection complete![/bold green]")
            console.print(f"Total unique tokens: {stats['total_unique']}\n")

        finally:
            await db_manager.close()

    asyncio.run(run())


@cli.command()
@click.option("--limit", type=int, default=None, help="Limit number of tokens to process")
@click.option("--source", type=click.Choice(['tokens', 'dexscreener_tokens']), default='tokens', help="Source table to read tokens from (default: tokens)")
def collect_smart_ohlcv(limit, source):
    """Collect OHLCV data with intelligent timeframe selection based on token age."""
    async def run():
        from .collectors.smart_ohlcv_collector import SmartOHLCVCollector

        try:
            await db_manager.init_async_db()

            console.print("\n[bold blue]Starting Smart OHLCV Collection[/bold blue]")
            console.print(f"Source table: {source}")
            console.print("Strategy: Auto-select optimal timeframe (≤200 candles per token)\n")

            collector = SmartOHLCVCollector()
            stats = await collector.collect_all(limit=limit, source_table=source)

            console.print(f"\n[bold green]✓ Collection complete![/bold green]")
            console.print(f"Total candles collected: {stats['total_candles']}\n")

        finally:
            await db_manager.close()

    asyncio.run(run())


@cli.command()
@click.option("--target-count", type=int, default=100, help="Target number of tokens to scrape")
@click.option("--headless/--no-headless", default=False, help="Use headless browser mode (default: False)")
@click.option("--max-age-days", type=int, default=30, help="Maximum token age in days (default: 30)")
def collect_dexscreener_homepage_fast(target_count, headless, max_age_days):
    """Collect tokens from DexScreener homepage by parsing page data (fast, no API calls)."""
    async def run():
        from .services.dexscreener_service import DexScreenerService

        try:
            await db_manager.init_async_db()

            console.print("\n[bold blue]Fast Collection from DexScreener Homepage[/bold blue]")
            console.print(f"Target: {target_count} tokens")
            console.print(f"Headless mode: {headless}")
            console.print(f"Max age: {max_age_days} days")
            console.print("[yellow]Method: Parse page data directly (no API calls)[/yellow]\n")

            service = DexScreenerService(db_manager)

            # 爬取页面并解析数据
            console.print("[cyan]Step 1: Scraping and parsing page data...[/cyan]")
            tokens_data = service.scrape_bsc_page_with_details(
                target_count=target_count,
                headless=headless
            )

            if not tokens_data:
                console.print("[red]No tokens scraped[/red]")
                return

            console.print(f"[green]✓ Scraped {len(tokens_data)} tokens with details[/green]\n")

            # 年龄过滤
            console.print(f"[cyan]Step 2: Filtering by age (max {max_age_days} days)...[/cyan]")
            filtered_tokens = service.filter_tokens_by_age(tokens_data, max_age_days)
            console.print(f"[green]✓ After filtering: {len(filtered_tokens)} tokens[/green]\n")

            # 导入数据库
            console.print("[cyan]Step 3: Importing to database...[/cyan]")
            import_stats = await service.import_tokens(filtered_tokens, update_existing=True)
            console.print(f"[green]✓ Imported: {import_stats['inserted']} new, {import_stats['updated']} updated[/green]\n")

            # 去重
            console.print("[cyan]Step 4: Deduplicating...[/cyan]")
            dedup_stats = await service.deduplicate_tokens(dry_run=False)
            console.print(f"[green]✓ Removed {dedup_stats.get('pairs_to_delete', 0)} duplicates[/green]\n")

            # 最终统计
            final_count = await service.get_token_count()
            console.print(f"[bold green]✓ Collection complete![/bold green]")
            console.print(f"Final token count: {final_count}\n")

        finally:
            await db_manager.close()

    asyncio.run(run())


@cli.command()
@click.option("--target-count", type=int, default=100, help="Target number of tokens to scrape")
@click.option("--headless/--no-headless", default=True, help="Use headless browser mode")
@click.option("--deduplicate/--no-deduplicate", default=True, help="Remove duplicate pairs")
@click.option("--filter-old/--no-filter-old", default=True, help="Filter tokens older than max-age-days")
@click.option("--max-age-days", type=int, default=30, help="Maximum token age in days (default: 30)")
def collect_dexscreener_homepage(target_count, headless, deduplicate, filter_old, max_age_days):
    """Collect tokens from DexScreener homepage using Selenium + API (slow but complete)."""
    async def run():
        from .services.dexscreener_service import DexScreenerService

        try:
            await db_manager.init_async_db()

            console.print("\n[bold blue]Collecting from DexScreener Homepage[/bold blue]")
            console.print(f"Target: {target_count} tokens")
            console.print(f"Headless mode: {headless}")
            console.print(f"Deduplicate: {deduplicate}")
            console.print(f"Filter old tokens: {filter_old}")
            if filter_old:
                console.print(f"Max age: {max_age_days} days\n")
            else:
                console.print()

            service = DexScreenerService(db_manager)
            result = await service.scrape_and_import(
                target_count=target_count,
                headless=headless,
                deduplicate=deduplicate,
                filter_old_tokens=filter_old,
                max_age_days=max_age_days
            )

            if result.get("success"):
                console.print(f"\n[bold green]✓ Collection complete![/bold green]")
                console.print(f"Final token count: {result.get('final_count', 0)}\n")
            else:
                console.print(f"\n[bold red]✗ Collection failed[/bold red]")
                if "error" in result:
                    console.print(f"Error: {result['error']}\n")

        finally:
            await db_manager.close()

    asyncio.run(run())


@cli.command()
def compare_sources():
    """Compare data completeness between AVE and GeckoTerminal."""
    async def run():
        app = BlockchainDataApp()
        try:
            await app.initialize()

            console.print("\n[bold blue]Comparing Data Sources...[/bold blue]\n")

            # Query statistics
            async with db_manager.get_session() as session:
                # Count tokens by source
                result = await session.execute(text("""
                    SELECT COALESCE(data_source, 'unknown') as data_source, COUNT(*) as count
                    FROM tokens
                    GROUP BY data_source
                """))
                source_counts = dict(result.fetchall())

                # Count OHLCV records by source
                result = await session.execute(text("""
                    SELECT COALESCE(t.data_source, 'unknown') as data_source, COUNT(o.id) as ohlcv_count
                    FROM tokens t
                    LEFT JOIN token_ohlcv o ON t.id = o.token_id
                    GROUP BY t.data_source
                """))
                ohlcv_counts = dict(result.fetchall())

                # Total counts
                result = await session.execute(text("SELECT COUNT(*) FROM tokens"))
                total_tokens = result.scalar()

                result = await session.execute(text("SELECT COUNT(*) FROM token_ohlcv"))
                total_ohlcv = result.scalar()

            # Display comparison table
            table = Table(title="Data Source Comparison")
            table.add_column("Source", style="cyan")
            table.add_column("Total Tokens", style="green")
            table.add_column("OHLCV Records", style="magenta")

            for source in ["ave", "geckoterminal", "dexscreener", "unknown"]:
                if source_counts.get(source, 0) > 0:
                    table.add_row(
                        source.upper() if source != "unknown" else "LEGACY",
                        str(source_counts.get(source, 0)),
                        str(ohlcv_counts.get(source, 0))
                    )

            # Add total row
            table.add_row(
                "[bold]TOTAL[/bold]",
                f"[bold]{total_tokens}[/bold]",
                f"[bold]{total_ohlcv}[/bold]"
            )

            console.print(table)
            console.print()

        finally:
            await app.close()

    asyncio.run(run())


if __name__ == "__main__":
    cli()
