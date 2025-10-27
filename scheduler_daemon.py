#!/usr/bin/env python3
"""
定时任务守护进程
负责运行两个定时任务：
1. 每10分钟爬取 DexScreener 首页数据（可选）
2. 每5分钟运行监控更新价格

使用方法：
- 启动所有任务（爬虫+监控）：python scheduler_daemon.py
- 只启动监控任务：python scheduler_daemon.py --monitor-only
- 查看帮助：python scheduler_daemon.py --help
"""

import asyncio
import logging
import signal
import sys
import os
import random
import argparse
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from src.services.token_monitor_service import TokenMonitorService
from src.services.multi_chain_scraper import MultiChainScraper
from src.services.kline_service import KlineService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 全局变量
scheduler = None
monitor_service = None
enable_scraper = True  # 是否启用爬虫任务
use_undetected_chrome = os.getenv('USE_UNDETECTED_CHROME', 'false').lower() == 'true'


async def scrape_dexscreener_task():
    """
    爬取 DexScreener 首页任务（从数据库读取配置）
    使用 cloudscraper 或 undetected-chromedriver 爬取多链数据
    支持重试机制提高成功率
    """
    from src.storage.models import ScrapeLog
    from src.storage.db_manager import DatabaseManager
    import uuid

    scraper = None
    monitor_service = None
    scrape_log_id = None
    db_manager = None

    try:
        logger.info("="*80)
        logger.info("开始爬取 DexScreener 首页（多链）...")
        logger.info("="*80)

        # 1. 从数据库读取配置
        monitor_service = TokenMonitorService()
        config = await monitor_service.get_scraper_config()

        if not config:
            logger.error("未找到爬虫配置，使用默认配置")
            config = {
                'enabled_chains': ['bsc', 'solana'],
                'count_per_chain': 100,
                'top_n_per_chain': 10,
                'use_undetected_chrome': use_undetected_chrome,
                'enabled': True,
                'scrape_interval_min': 9,
                'scrape_interval_max': 15
            }

        # 2. 检查配置是否启用
        if not config.get('enabled', True):
            logger.info("爬虫配置已禁用，跳过本次爬取")
            schedule_next_scrape(config)
            return

        logger.info(f"配置信息: chains={config['enabled_chains']}, "
                   f"count_per_chain={config['count_per_chain']}, "
                   f"top_n_per_chain={config['top_n_per_chain']}, "
                   f"use_undetected_chrome={config['use_undetected_chrome']}")

        # 2.5 创建 ScrapeLog 记录（状态：running）
        start_time = datetime.utcnow()
        db_manager = DatabaseManager()
        scrape_log_id = str(uuid.uuid4())

        async with db_manager.get_session() as session:
            scrape_log = ScrapeLog(
                id=scrape_log_id,
                started_at=start_time,
                status='running',
                chain=','.join(config.get('enabled_chains', [])),  # 多链用逗号分隔
                config_snapshot=config  # 保存配置快照
            )
            session.add(scrape_log)
            await session.commit()

        logger.info(f"📝 已创建抓取日志记录: {scrape_log_id}")

        # 3. 使用配置参数爬取
        scraper = MultiChainScraper()

        # 爬取并保存到 potential_tokens 表
        result = await scraper.scrape_and_save_multi_chain(
            chains=config['enabled_chains'],              # 从配置读取链列表
            count_per_chain=config['count_per_chain'],    # 从配置读取每条链爬取总数
            top_n_per_chain=config['top_n_per_chain'],    # 从配置读取每条链取前N名
            use_undetected_chrome=config['use_undetected_chrome'],  # 从配置读取爬取方法
            min_market_cap=config.get('min_market_cap'),  # 从配置读取最小市值
            min_liquidity=config.get('min_liquidity'),    # 从配置读取最小流动性
            max_token_age_days=config.get('max_token_age_days')  # 从配置读取最大代币年龄
        )

        # 3.5 更新 ScrapeLog 记录（状态：success）
        end_time = datetime.utcnow()
        duration = int((end_time - start_time).total_seconds())

        async with db_manager.get_session() as session:
            scrape_log = await session.get(ScrapeLog, scrape_log_id)
            if scrape_log:
                scrape_log.completed_at = end_time
                scrape_log.duration_seconds = duration
                scrape_log.status = 'success'
                scrape_log.tokens_saved = result.get('total_saved', 0)
                scrape_log.tokens_skipped = result.get('total_skipped', 0)
                # 从 chains 结果中计算 scraped 总数
                total_scraped = sum(
                    chain_result.get('scraped', 0)
                    for chain_result in result.get('chains', {}).values()
                )
                scrape_log.tokens_scraped = total_scraped
                await session.commit()

        logger.info(f"✅ 已更新抓取日志: 耗时 {duration}秒")

        logger.info(
            f"爬取完成：总共保存 {result['total_saved']} 个代币到数据库，"
            f"跳过 {result['total_skipped']} 个"
        )
        logger.info("="*80)

        # 爬取完成后，立即更新潜力代币的 AVE API 数据
        if result['total_saved'] > 0:
            logger.info("\n" + "="*80)
            logger.info("更新潜力代币的 AVE API 数据...")
            logger.info("="*80)

            if not monitor_service:
                monitor_service = TokenMonitorService()

            update_result = await monitor_service.update_potential_tokens_data(
                delay=0.3,
                min_update_interval_minutes=0  # 爬取后立即更新，不检查间隔
            )

            logger.info(
                f"更新完成：成功 {update_result.get('updated', 0)} 个，"
                f"失败 {update_result.get('failed', 0)} 个"
            )
            logger.info("="*80)

        # 调度下一次爬取任务（使用配置的间隔时间）
        schedule_next_scrape(config)

    except Exception as e:
        logger.error(f"爬取任务失败: {e}", exc_info=True)

        # 更新 ScrapeLog 记录（状态：failed）
        if scrape_log_id and db_manager:
            try:
                end_time = datetime.utcnow()
                duration = int((end_time - start_time).total_seconds())

                async with db_manager.get_session() as session:
                    scrape_log = await session.get(ScrapeLog, scrape_log_id)
                    if scrape_log:
                        scrape_log.completed_at = end_time
                        scrape_log.duration_seconds = duration
                        scrape_log.status = 'failed'
                        scrape_log.error_message = str(e)[:1000]  # 限制长度
                        await session.commit()

                logger.info(f"❌ 已更新抓取日志: 失败，耗时 {duration}秒")
            except Exception as log_error:
                logger.error(f"更新失败日志时出错: {log_error}")

        # 即使失败也要调度下一次（使用默认配置）
        schedule_next_scrape()

    finally:
        # 关闭连接
        if scraper:
            await scraper.close()
        if monitor_service:
            await monitor_service.close()


def schedule_next_scrape(config=None):
    """
    调度下一次爬取任务（使用配置的间隔时间或默认9-15分钟）

    Args:
        config: 爬虫配置字典，包含 scrape_interval_min 和 scrape_interval_max
    """
    global scheduler, enable_scraper

    # 如果爬虫被禁用，不调度
    if not enable_scraper:
        return

    if scheduler:
        # 从配置读取间隔时间，如果没有配置则使用默认值（9-15分钟）
        if config:
            interval_min = config.get('scrape_interval_min', 9)
            interval_max = config.get('scrape_interval_max', 15)
        else:
            interval_min = 9
            interval_max = 15

        # 计算随机间隔时间
        next_run_minutes = random.uniform(interval_min, interval_max)
        next_run_time = datetime.now() + timedelta(minutes=next_run_minutes)

        # 移除旧的爬取任务
        try:
            scheduler.remove_job('scrape_dexscreener')
        except:
            pass

        # 添加新的一次性任务
        scheduler.add_job(
            scrape_dexscreener_task,
            trigger=DateTrigger(run_date=next_run_time),
            id='scrape_dexscreener',
            name='爬取DexScreener首页',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60
        )

        logger.info(f"📅 下次爬取时间: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')} "
                   f"(间隔 {next_run_minutes:.1f} 分钟)")



async def monitor_prices_task():
    """
    监控价格任务（从数据库读取配置）
    更新监控代币价格 + 潜力代币数据
    """
    from src.storage.models import MonitorLog
    from src.storage.db_manager import DatabaseManager
    import uuid

    global monitor_service

    monitor_log_id = None
    db_manager = None
    start_time = None

    try:
        # 任务开始计时（包含所有步骤）
        start_time = datetime.utcnow()

        logger.info("="*80)
        logger.info("开始更新监控代币价格...")
        logger.info("="*80)

        # 1. 从数据库读取监控配置
        if not monitor_service:
            monitor_service = TokenMonitorService()

        config = await monitor_service.get_monitor_config()

        if not config:
            logger.error("未找到监控配置，跳过本次更新")
            return

        # 2. 检查配置是否启用
        if not config.get('enabled', True):
            logger.info("监控配置已禁用，跳过本次更新")
            return

        logger.info(f"配置信息: 间隔={config['update_interval_minutes']}分钟, "
                   f"市值阈值={config.get('min_monitor_market_cap')}, "
                   f"流动性阈值={config.get('min_monitor_liquidity')}")

        # 创建 MonitorLog 记录（状态：running）
        db_manager = DatabaseManager()
        monitor_log_id = str(uuid.uuid4())

        async with db_manager.get_session() as session:
            monitor_log = MonitorLog(
                id=monitor_log_id,
                started_at=start_time,
                status='running',
                config_snapshot=config  # 保存配置快照
            )
            session.add(monitor_log)
            await session.commit()

        logger.info(f"📝 已创建监控日志记录: {monitor_log_id}")

        # 更新所有监控代币的价格
        result = await monitor_service.update_monitored_prices()

        # 更新 MonitorLog 记录（中间状态）
        async with db_manager.get_session() as session:
            monitor_log = await session.get(MonitorLog, monitor_log_id)
            if monitor_log:
                monitor_log.status = 'success'
                monitor_log.tokens_monitored = result.get('total_monitored', 0)
                monitor_log.tokens_updated = result.get('updated', 0)
                monitor_log.tokens_failed = result.get('failed', 0)
                monitor_log.tokens_auto_removed = result.get('removed', 0)
                monitor_log.alerts_triggered = result.get('alerts_triggered', 0)
                monitor_log.removed_by_market_cap = result.get('removed_by_market_cap', 0)
                monitor_log.removed_by_liquidity = result.get('removed_by_liquidity', 0)
                await session.commit()

        logger.info(
            f"价格更新完成：更新 {result['updated']} 个代币，"
            f"触发 {result['alerts_triggered']} 个报警"
        )
        if result.get('removed', 0) > 0:
            logger.info(
                f"自动删除 {result['removed']} 个代币 "
                f"(市值: {result.get('removed_by_market_cap', 0)}, "
                f"流动性: {result.get('removed_by_liquidity', 0)})"
            )
        logger.info("="*80)

        # 同时更新潜力代币的 AVE API 数据（带去重检查）
        logger.info("\n" + "="*80)
        logger.info("检查是否需要更新潜力代币数据...")
        logger.info("="*80)

        potential_result = await monitor_service.update_potential_tokens_data(
            delay=0.3,
            min_update_interval_minutes=3  # 最少间隔3分钟，避免重复调用
        )

        if potential_result.get('skipped'):
            logger.info("潜力代币数据更新已跳过（距上次更新时间太短）")
        else:
            logger.info(
                f"潜力代币更新完成：成功 {potential_result.get('updated', 0)} 个，"
                f"失败 {potential_result.get('failed', 0)} 个"
            )

            # 如果潜力代币有删除，累加到监控日志统计中
            potential_removed = potential_result.get('removed', 0)
            if potential_removed > 0:
                logger.info(
                    f"自动删除潜力代币 {potential_removed} 个 "
                    f"(市值: {potential_result.get('removed_by_market_cap', 0)}, "
                    f"流动性: {potential_result.get('removed_by_liquidity', 0)})"
                )

                # 更新 monitor_log，累加潜力代币的删除统计
                async with db_manager.get_session() as session:
                    monitor_log = await session.get(MonitorLog, monitor_log_id)
                    if monitor_log:
                        monitor_log.tokens_auto_removed += potential_removed
                        monitor_log.removed_by_market_cap += potential_result.get('removed_by_market_cap', 0)
                        monitor_log.removed_by_liquidity += potential_result.get('removed_by_liquidity', 0)
                        await session.commit()

                logger.info(f"✅ 已累加潜力代币删除统计到监控日志")

        # 所有任务完成，计算总耗时并更新监控日志
        end_time = datetime.utcnow()
        duration = int((end_time - start_time).total_seconds())

        async with db_manager.get_session() as session:
            monitor_log = await session.get(MonitorLog, monitor_log_id)
            if monitor_log:
                monitor_log.completed_at = end_time
                monitor_log.duration_seconds = duration
                await session.commit()

        logger.info(f"✅ 监控任务完成，总耗时: {duration} 秒")
        logger.info("="*80)

    except Exception as e:
        logger.error(f"监控任务失败: {e}", exc_info=True)

        # 更新 MonitorLog 记录（状态：failed）
        if monitor_log_id and db_manager and start_time:
            try:
                end_time = datetime.utcnow()
                duration = int((end_time - start_time).total_seconds())

                async with db_manager.get_session() as session:
                    monitor_log = await session.get(MonitorLog, monitor_log_id)
                    if monitor_log:
                        monitor_log.completed_at = end_time
                        monitor_log.duration_seconds = duration
                        monitor_log.status = 'failed'
                        monitor_log.error_message = str(e)[:1000]  # 限制长度
                        await session.commit()

                logger.info(f"❌ 已更新监控日志: 失败，耗时 {duration}秒")
            except Exception as log_error:
                logger.error(f"更新失败日志时出错: {log_error}")
    finally:
        # 关闭数据库连接
        if db_manager:
            try:
                await db_manager.close()
            except:
                pass


async def update_klines_task():
    """
    更新K线数据任务（每1小时）
    拉取所有监控代币和潜力代币的K线数据
    """
    kline_service = None

    try:
        logger.info("="*80)
        logger.info("开始更新K线数据...")
        logger.info("="*80)

        kline_service = KlineService()

        # 调用统一更新方法（内部自动限流）
        result = await kline_service.update_all_tokens_klines(
            timeframe="minute",
            aggregate=5,
            max_candles=500
        )

        logger.info("="*80)
        logger.info("✅ K线数据更新完成")
        logger.info(f"  监控代币: {result['monitored']} 个")
        logger.info(f"  潜力代币: {result['potential']} 个")
        logger.info(f"  总代币数: {result['total']} 个")
        logger.info(f"  成功: {result['success']} 个，失败: {result['failed']} 个")
        logger.info(f"  拉取: {result['total_fetched']} 根，保存: {result['total_saved']} 根")
        logger.info("="*80)

    except Exception as e:
        logger.error(f"❌ 更新K线数据时出错: {e}", exc_info=True)


def shutdown_handler(signum, frame):
    """
    优雅关闭处理
    """
    global scheduler
    logger.info("收到关闭信号，正在关闭调度器...")

    if scheduler:
        try:
            scheduler.shutdown(wait=False)
            logger.info("调度器已关闭")
        except Exception:
            pass  # 忽略重复关闭的错误

    # 直接退出（避免程序卡死）
    import os
    os._exit(0)


async def main():
    """
    主函数：启动调度器
    """
    global scheduler, monitor_service, enable_scraper

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='定时任务守护进程：监控代币价格和爬取 DexScreener 数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  python scheduler_daemon.py                   # 启动所有任务（爬虫+监控）
  python scheduler_daemon.py --monitor-only    # 只启动监控任务（不爬取）
  python scheduler_daemon.py --scraper-only    # 只启动爬虫任务（不监控）
        """
    )
    parser.add_argument(
        '--monitor-only',
        action='store_true',
        help='只启动监控价格任务，不启动爬虫'
    )
    parser.add_argument(
        '--scraper-only',
        action='store_true',
        help='只启动爬虫任务，不启动监控'
    )
    parser.add_argument(
        '--use-undetected-chrome',
        action='store_true',
        help='使用 undetected-chromedriver 爬取（成功率更高，需要安装 Chrome）'
    )

    args = parser.parse_args()

    # 检查参数冲突
    if args.monitor_only and args.scraper_only:
        logger.error("错误: --monitor-only 和 --scraper-only 不能同时使用")
        sys.exit(1)

    # 确定启用哪些任务
    enable_scraper = not args.monitor_only
    enable_monitor = not args.scraper_only

    # 设置爬取方法
    global use_undetected_chrome
    if args.use_undetected_chrome:
        use_undetected_chrome = True

    logger.info("="*80)
    logger.info("定时任务守护进程启动")
    if use_undetected_chrome:
        logger.info("爬取方法: undetected-chromedriver（高成功率模式）")
    else:
        logger.info("爬取方法: cloudscraper（快速模式）")
    logger.info("="*80)

    # 注册信号处理
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # 初始化服务
    monitor_service = TokenMonitorService()

    # 创建调度器
    scheduler = AsyncIOScheduler(timezone='UTC')

    # 根据参数添加任务
    if enable_monitor:
        # 从数据库读取监控配置
        monitor_config = await monitor_service.get_monitor_config()

        if not monitor_config:
            logger.error("未找到监控配置，使用默认间隔 5 分钟")
            update_interval = 5
        else:
            update_interval = monitor_config.get('update_interval_minutes', 5)
            logger.info(f"从配置读取更新间隔: {update_interval} 分钟")

        scheduler.add_job(
            monitor_prices_task,
            trigger=IntervalTrigger(minutes=update_interval),
            id='monitor_prices',
            name='监控代币价格',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30
        )
        logger.info(f"✅ 已启用任务：每 {update_interval} 分钟监控代币价格")

        # K线更新任务：每1小时执行一次
        scheduler.add_job(
            update_klines_task,
            trigger=IntervalTrigger(hours=1),
            id='update_klines',
            name='更新K线数据',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300  # 允许5分钟的延迟
        )
        logger.info("✅ 已启用任务：每1小时更新K线数据")

    # 启动调度器
    scheduler.start()

    logger.info("调度器已启动，任务计划：")
    if enable_scraper:
        logger.info("  - 随机间隔9-15分钟爬取 DexScreener 首页（BSC + Solana，支持重试机制）")
    if enable_monitor:
        logger.info(f"  - 每 {update_interval} 分钟监控代币价格（更新 monitored_tokens 表并触发报警 + 更新 potential_tokens AVE 数据）")
        logger.info("  - 每1小时更新K线数据（监控代币 + 潜力代币，5分钟K线）")
    logger.info("="*80)

    # 启动时立即执行一次任务
    if enable_scraper:
        logger.info("立即执行一次爬取任务...")
        await scrape_dexscreener_task()

    if enable_monitor:
        logger.info("立即执行一次监控任务...")
        await monitor_prices_task()

        # 启动时也立即执行一次K线更新
        logger.info("立即执行一次K线更新任务...")
        await update_klines_task()

    # 保持运行
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("接收到退出信号")
    except Exception as e:
        logger.error(f"运行时错误: {e}", exc_info=True)
    finally:
        logger.info("正在关闭服务...")
        if scheduler:
            try:
                scheduler.shutdown(wait=False)
            except:
                pass
        if monitor_service:
            try:
                await monitor_service.close()
            except:
                pass
        logger.info("✅ 定时任务守护进程已安全关闭")


if __name__ == "__main__":
    asyncio.run(main())
