#!/usr/bin/env python3
"""
Token Monitor CLI
命令行工具用于管理代币监控
"""

import asyncio
import click
from rich.console import Console
from rich.table import Table
from datetime import datetime

from src.services.token_monitor_service import TokenMonitorService
from src.utils.logger import setup_logger

logger = setup_logger(__name__)
console = Console()


@click.group()
def cli():
    """代币监控管理工具"""
    pass


@cli.command()
@click.option('--count', '-c', default=100, help='抓取代币数量 (10-500)')
@click.option('--top-n', '-n', default=10, help='取前N名涨幅榜 (1-50)')
@click.option('--headless/--no-headless', default=False, help='是否使用无头浏览器')
@click.option('--output', '-o', default=None, help='保存结果到JSON文件')
def filter(count, top_n, headless, output):
    """
    【独立功能1】只爬取和筛选Top涨幅代币，不添加监控

    示例：
        python -m src.scripts.monitor_tokens filter
        python -m src.scripts.monitor_tokens filter --count 50 --top-n 5
        python -m src.scripts.monitor_tokens filter --output /tmp/top_gainers.json
    """
    console.print(f"\n[bold blue]🔍 爬取并筛选涨幅榜（不添加监控）[/bold blue]")
    console.print(f"  抓取数量: {count}")
    console.print(f"  取前: {top_n} 名")
    console.print(f"  无头模式: {headless}\n")

    def run():
        monitor_service = TokenMonitorService()
        try:
            top_gainers = monitor_service.scrape_and_filter_top_gainers(
                count=count,
                top_n=top_n,
                headless=headless
            )

            console.print(f"\n[bold green]✅ 筛选完成[/bold green]")
            console.print(f"  已筛选: {len(top_gainers)} 个Top涨幅代币")
            console.print(f"  [bold yellow]注意：还未添加到监控表[/bold yellow]\n")

            # 保存到文件
            if output:
                import json
                with open(output, 'w', encoding='utf-8') as f:
                    json.dump(top_gainers, f, indent=2, ensure_ascii=False)
                console.print(f"  [green]✓ 已保存到: {output}[/green]\n")

        except Exception as e:
            console.print(f"\n[bold red]❌ 错误: {e}[/bold red]\n")
            logger.error(f"Filter error: {e}", exc_info=True)

    run()


@cli.command()
@click.option('--input', '-i', required=True, help='从JSON文件加载代币')
@click.option('--threshold', '-t', default=20.0, help='跌幅报警阈值 (%)')
def add(input, threshold):
    """
    【独立功能2】从JSON文件加载代币并添加到监控

    示例：
        python -m src.scripts.monitor_tokens add --input /tmp/top_gainers.json
        python -m src.scripts.monitor_tokens add -i tokens.json --threshold 15
    """
    console.print(f"\n[bold blue]📥 从文件加载代币并添加监控[/bold blue]")
    console.print(f"  文件: {input}")
    console.print(f"  跌幅阈值: {threshold}%\n")

    async def run():
        import json

        # 加载文件
        try:
            with open(input, 'r', encoding='utf-8') as f:
                tokens = json.load(f)
        except FileNotFoundError:
            console.print(f"[bold red]❌ 文件不存在: {input}[/bold red]\n")
            return
        except json.JSONDecodeError as e:
            console.print(f"[bold red]❌ JSON解析错误: {e}[/bold red]\n")
            return

        console.print(f"✓ 已加载 {len(tokens)} 个代币\n")

        # 添加到监控
        monitor_service = TokenMonitorService()
        try:
            result = await monitor_service.add_tokens_to_monitor(
                tokens=tokens,
                drop_threshold=threshold
            )

            console.print(f"\n[bold green]✅ 添加完成[/bold green]")
            console.print(f"  总数: {result['total']}")
            console.print(f"  成功: {result['added']}")
            console.print(f"  跳过: {result['skipped']}\n")

        except Exception as e:
            console.print(f"\n[bold red]❌ 错误: {e}[/bold red]\n")
            logger.error(f"Add error: {e}", exc_info=True)
        finally:
            await monitor_service.close()

    asyncio.run(run())


@cli.command()
@click.option('--count', '-c', default=100, help='抓取代币数量 (10-500)')
@click.option('--top-n', '-n', default=10, help='取前N名涨幅榜 (1-50)')
@click.option('--threshold', '-t', default=20.0, help='跌幅报警阈值 (%)')
@click.option('--headless/--no-headless', default=False, help='是否使用无头浏览器')
def scrape(count, top_n, threshold, headless):
    """
    【一键操作】抓取 + 筛选 + 添加监控

    如果想分开执行，请使用：
        filter 命令 - 只爬取筛选
        add 命令 - 只添加监控

    示例：
        python -m src.scripts.monitor_tokens scrape
        python -m src.scripts.monitor_tokens scrape --count 200 --top-n 15
    """
    console.print(f"\n[bold blue]🔍 【一键操作】爬取 + 筛选 + 添加监控[/bold blue]")
    console.print(f"  抓取数量: {count}")
    console.print(f"  取前: {top_n} 名")
    console.print(f"  跌幅阈值: {threshold}%")
    console.print(f"  无头模式: {headless}\n")

    async def run():
        monitor_service = TokenMonitorService()
        try:
            result = await monitor_service.scrape_and_add_top_gainers(
                count=count,
                top_n=top_n,
                drop_threshold=threshold,
                headless=headless
            )

            console.print("\n[bold green]✅ 完成[/bold green]")
            console.print(f"  已抓取: {result['scraped']} 个代币")
            console.print(f"  涨幅榜: {result['top_gainers']} 个")
            console.print(f"  [bold yellow]已添加监控: {result['added']} 个[/bold yellow]")
            console.print(f"  跳过: {result['skipped']} 个\n")

        except Exception as e:
            console.print(f"\n[bold red]❌ 错误: {e}[/bold red]\n")
            logger.error(f"Scrape error: {e}", exc_info=True)
        finally:
            await monitor_service.close()

    asyncio.run(run())


@cli.command()
@click.option('--batch-size', '-b', default=10, help='批处理大小 (1-50)')
@click.option('--delay', '-d', default=0.5, help='批次间延迟(秒)')
def update(batch_size, delay):
    """
    更新监控代币价格并检查报警

    示例：
        python -m src.scripts.monitor_tokens update
        python -m src.scripts.monitor_tokens update --batch-size 20 --delay 1.0
    """
    console.print(f"\n[bold blue]📊 更新监控代币价格[/bold blue]\n")

    async def run():
        monitor_service = TokenMonitorService()
        try:
            result = await monitor_service.update_monitored_prices(
                batch_size=batch_size,
                delay=delay
            )

            console.print("\n[bold green]✅ 更新完成[/bold green]")
            console.print(f"  已更新: {result['updated']} 个代币")
            console.print(f"  总监控数: {result['total_monitored']} 个")

            if result['alerts_triggered'] > 0:
                console.print(f"  [bold red]🚨 触发报警: {result['alerts_triggered']} 个[/bold red]")
            else:
                console.print(f"  触发报警: 0 个")

            console.print()

        except Exception as e:
            console.print(f"\n[bold red]❌ 错误: {e}[/bold red]\n")
            logger.error(f"Update error: {e}", exc_info=True)
        finally:
            await monitor_service.close()

    asyncio.run(run())


@cli.command()
@click.option('--limit', '-l', default=50, help='显示数量')
def list_tokens(limit):
    """
    查看监控代币列表

    示例：
        python -m src.scripts.monitor_tokens list-tokens
        python -m src.scripts.monitor_tokens list-tokens --limit 20
    """
    console.print(f"\n[bold blue]📋 监控代币列表[/bold blue]\n")

    async def run():
        monitor_service = TokenMonitorService()
        try:
            tokens = await monitor_service.get_active_monitored_tokens(limit=limit)

            if not tokens:
                console.print("[yellow]暂无监控代币[/yellow]\n")
                return

            # 创建表格
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("符号", style="cyan", width=12)
            table.add_column("入场价", justify="right", style="green")
            table.add_column("当前价", justify="right")
            table.add_column("峰值价", justify="right", style="yellow")
            table.add_column("距峰值", justify="right")
            table.add_column("入场涨幅", justify="right")
            table.add_column("状态", style="bold")
            table.add_column("入场时间", width=16)

            for token in tokens:
                entry_price = token['entry_price_usd']
                current_price = token.get('current_price_usd')
                peak_price = token['peak_price_usd']

                # 计算距峰值跌幅
                if current_price and peak_price > 0:
                    drop_pct = ((peak_price - current_price) / peak_price) * 100
                    drop_str = f"-{drop_pct:.1f}%" if drop_pct > 0 else f"+{abs(drop_pct):.1f}%"
                    drop_style = "red" if drop_pct > 10 else "yellow" if drop_pct > 0 else "green"
                else:
                    drop_str = "N/A"
                    drop_style = ""

                # 入场时涨幅
                entry_gain = token.get('price_change_24h_at_entry', 0)
                entry_gain_str = f"+{entry_gain:.1f}%" if entry_gain else "N/A"

                # 状态颜色
                status = token['status']
                if status == "active":
                    status_str = "[green]active[/green]"
                elif status == "alerted":
                    status_str = "[red]alerted[/red]"
                else:
                    status_str = "[gray]stopped[/gray]"

                # 入场时间
                entry_time = datetime.fromisoformat(token['entry_timestamp'])
                entry_time_str = entry_time.strftime("%m-%d %H:%M")

                table.add_row(
                    token['token_symbol'],
                    f"${entry_price:.8f}",
                    f"${current_price:.8f}" if current_price else "N/A",
                    f"${peak_price:.8f}",
                    f"[{drop_style}]{drop_str}[/{drop_style}]",
                    entry_gain_str,
                    status_str,
                    entry_time_str
                )

            console.print(table)
            console.print(f"\n共 {len(tokens)} 个监控代币\n")

        except Exception as e:
            console.print(f"\n[bold red]❌ 错误: {e}[/bold red]\n")
            logger.error(f"List tokens error: {e}", exc_info=True)
        finally:
            await monitor_service.close()

    asyncio.run(run())


@cli.command()
@click.option('--limit', '-l', default=20, help='显示数量')
@click.option('--severity', '-s', help='严重程度筛选: low/medium/high/critical')
@click.option('--acknowledged/--unacknowledged', default=None, help='是否已确认')
def list_alerts(limit, severity, acknowledged):
    """
    查看价格报警列表

    示例：
        python -m src.scripts.monitor_tokens list-alerts
        python -m src.scripts.monitor_tokens list-alerts --severity high
        python -m src.scripts.monitor_tokens list-alerts --unacknowledged
    """
    console.print(f"\n[bold blue]🚨 价格报警列表[/bold blue]\n")

    async def run():
        monitor_service = TokenMonitorService()
        try:
            alerts = await monitor_service.get_alerts(
                limit=limit,
                acknowledged=acknowledged,
                severity=severity
            )

            if not alerts:
                console.print("[yellow]暂无报警记录[/yellow]\n")
                return

            # 创建表格
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("代币", style="cyan", width=12)
            table.add_column("触发价", justify="right", style="red")
            table.add_column("峰值价", justify="right", style="yellow")
            table.add_column("距峰值跌幅", justify="right", style="bold red")
            table.add_column("距入场跌幅", justify="right")
            table.add_column("严重程度", width=10)
            table.add_column("触发时间", width=16)

            for alert in alerts:
                # 严重程度颜色
                severity_map = {
                    "critical": "[bold red]CRITICAL[/bold red]",
                    "high": "[red]HIGH[/red]",
                    "medium": "[yellow]MEDIUM[/yellow]",
                    "low": "[blue]LOW[/blue]"
                }
                severity_str = severity_map.get(alert['severity'], alert['severity'])

                # 触发时间
                triggered_at = datetime.fromisoformat(alert['triggered_at'])
                triggered_str = triggered_at.strftime("%m-%d %H:%M")

                table.add_row(
                    alert['token_symbol'],
                    f"${alert['trigger_price_usd']:.8f}",
                    f"${alert['peak_price_usd']:.8f}",
                    f"-{alert['drop_from_peak_percent']:.1f}%",
                    f"-{alert['drop_from_entry_percent']:.1f}%",
                    severity_str,
                    triggered_str
                )

            console.print(table)
            console.print(f"\n共 {len(alerts)} 条报警记录\n")

        except Exception as e:
            console.print(f"\n[bold red]❌ 错误: {e}[/bold red]\n")
            logger.error(f"List alerts error: {e}", exc_info=True)
        finally:
            await monitor_service.close()

    asyncio.run(run())


@cli.command()
def auto_monitor():
    """
    自动监控模式（持续运行）

    每隔5分钟更新一次价格，检查报警

    示例：
        python -m src.scripts.monitor_tokens auto-monitor
    """
    console.print("\n[bold blue]🤖 启动自动监控模式[/bold blue]")
    console.print("每5分钟更新一次价格...\n")
    console.print("[dim]按 Ctrl+C 停止[/dim]\n")

    async def run():
        monitor_service = TokenMonitorService()
        try:
            while True:
                try:
                    console.print(f"[cyan]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/cyan] 开始更新价格...")

                    result = await monitor_service.update_monitored_prices(
                        batch_size=10,
                        delay=0.5
                    )

                    console.print(
                        f"  ✓ 已更新 {result['updated']}/{result['total_monitored']} 个代币"
                    )

                    if result['alerts_triggered'] > 0:
                        console.print(
                            f"  [bold red]🚨 触发 {result['alerts_triggered']} 个报警！[/bold red]"
                        )

                    console.print("  等待5分钟...\n")

                    # 等待5分钟
                    await asyncio.sleep(300)

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    console.print(f"  [red]错误: {e}[/red]")
                    console.print("  等待1分钟后重试...\n")
                    await asyncio.sleep(60)

        except KeyboardInterrupt:
            console.print("\n\n[yellow]已停止监控[/yellow]\n")
        finally:
            await monitor_service.close()

    asyncio.run(run())


if __name__ == '__main__':
    cli()
