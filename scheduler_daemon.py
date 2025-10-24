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
import random
import argparse
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from src.services.token_monitor_service import TokenMonitorService
from src.services.multi_chain_scraper import MultiChainScraper

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


async def scrape_dexscreener_task():
    """
    爬取 DexScreener 首页任务（随机间隔9-15分钟）
    使用 cloudscraper 爬取 BSC 和 Solana 链
    支持重试机制提高成功率
    """
    scraper = None
    monitor_service = None

    try:
        logger.info("="*80)
        logger.info("开始爬取 DexScreener 首页（多链）...")
        logger.info("="*80)

        # 使用新的多链爬虫
        scraper = MultiChainScraper()

        # 爬取并保存到 potential_tokens 表
        result = await scraper.scrape_and_save_multi_chain(
            chains=['bsc', 'solana'],  # 爬取 BSC 和 Solana 链
            count_per_chain=100,       # 每条链爬取100个代币
            top_n_per_chain=10         # 每条链取前10名涨幅榜
        )

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

        # 调度下一次爬取任务（随机间隔9-15分钟）
        schedule_next_scrape()

    except Exception as e:
        logger.error(f"爬取任务失败: {e}", exc_info=True)
        # 即使失败也要调度下一次
        schedule_next_scrape()

    finally:
        # 关闭连接
        if scraper:
            await scraper.close()
        if monitor_service:
            await monitor_service.close()


def schedule_next_scrape():
    """
    调度下一次爬取任务（随机间隔9-15分钟）
    """
    global scheduler, enable_scraper

    # 如果爬虫被禁用，不调度
    if not enable_scraper:
        return

    if scheduler:
        # 计算随机间隔时间（9-15分钟）
        next_run_minutes = random.uniform(9, 15)
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
    监控价格任务（每5分钟）
    更新监控代币价格 + 潜力代币数据
    """
    global monitor_service

    try:
        logger.info("="*80)
        logger.info("开始更新监控代币价格...")
        logger.info("="*80)

        if not monitor_service:
            monitor_service = TokenMonitorService()

        # 更新所有监控代币的价格
        result = await monitor_service.update_monitored_prices()

        logger.info(
            f"价格更新完成：更新 {result['updated']} 个代币，"
            f"触发 {result['alerts_triggered']} 个报警"
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
        logger.info("="*80)

    except Exception as e:
        logger.error(f"监控任务失败: {e}", exc_info=True)


def shutdown_handler(signum, frame):
    """
    优雅关闭处理
    """
    logger.info("收到关闭信号，正在关闭调度器...")

    if scheduler:
        scheduler.shutdown(wait=True)

    if monitor_service:
        asyncio.create_task(monitor_service.close())

    logger.info("调度器已关闭")
    sys.exit(0)


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

    args = parser.parse_args()

    # 检查参数冲突
    if args.monitor_only and args.scraper_only:
        logger.error("错误: --monitor-only 和 --scraper-only 不能同时使用")
        sys.exit(1)

    # 确定启用哪些任务
    enable_scraper = not args.monitor_only
    enable_monitor = not args.scraper_only

    logger.info("="*80)
    logger.info("定时任务守护进程启动")
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
        scheduler.add_job(
            monitor_prices_task,
            trigger=IntervalTrigger(minutes=5),
            id='monitor_prices',
            name='监控代币价格',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30
        )
        logger.info("✅ 已启用任务：每5分钟监控代币价格")

    # 启动调度器
    scheduler.start()

    logger.info("调度器已启动，任务计划：")
    if enable_scraper:
        logger.info("  - 随机间隔9-15分钟爬取 DexScreener 首页（BSC + Solana，支持重试机制）")
    if enable_monitor:
        logger.info("  - 每5分钟监控代币价格（更新 monitored_tokens 表并触发报警 + 更新 potential_tokens AVE 数据）")
    logger.info("="*80)

    # 启动时立即执行一次任务
    if enable_scraper:
        logger.info("立即执行一次爬取任务...")
        await scrape_dexscreener_task()

    if enable_monitor:
        logger.info("立即执行一次监控任务...")
        await monitor_prices_task()

    # 保持运行
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("接收到退出信号")
    finally:
        if scheduler:
            scheduler.shutdown(wait=True)
        if monitor_service:
            await monitor_service.close()
        logger.info("定时任务守护进程已关闭")


if __name__ == "__main__":
    asyncio.run(main())
