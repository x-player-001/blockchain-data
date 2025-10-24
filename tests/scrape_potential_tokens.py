#!/usr/bin/env python3
"""
爬取潜力币种脚本

使用新的工作流程：
1. 爬取 Top 涨幅代币
2. 保存到 potential_tokens 表
3. 更新 AVE API 数据

前端可以从 potential_tokens 表中选择代币手动添加到监控
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.services.token_monitor_service import TokenMonitorService
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def main():
    """主函数"""
    monitor_service = TokenMonitorService()

    try:
        logger.info("\n" + "="*80)
        logger.info("🚀 开始爬取潜力币种（新工作流程）")
        logger.info("="*80 + "\n")

        # 步骤1: 爬取并保存到 potential_tokens 表
        logger.info("📊 步骤1: 爬取 DexScreener Top 涨幅代币...")
        scrape_result = await monitor_service.scrape_and_save_to_potential(
            count=100,        # 爬取100个代币
            top_n=10,         # 筛选前10名
            headless=True     # 使用无头浏览器
        )

        logger.info(f"\n✅ 爬取完成:")
        logger.info(f"   - 爬取总数: {scrape_result['scraped']}")
        logger.info(f"   - Top涨幅: {scrape_result['top_gainers']}")
        logger.info(f"   - 保存数量: {scrape_result['saved']}")
        logger.info(f"   - 跳过: {scrape_result['skipped']}")

        logger.info("\n💡 提示: 潜力代币的 AVE API 数据会在添加到监控时自动获取")

        # 显示当前潜力币种列表
        logger.info("\n📋 当前潜力币种列表:")
        potential_tokens = await monitor_service.get_potential_tokens(
            limit=20,
            only_not_added=True  # 只显示未添加到监控的
        )

        if potential_tokens:
            logger.info(f"\n共有 {len(potential_tokens)} 个未添加到监控的潜力币种:\n")
            for i, token in enumerate(potential_tokens, 1):
                symbol = token['token_symbol']
                scraped_price = token['scraped_price_usd']
                scraped_change = token['price_change_24h_at_scrape'] or 0
                current_price = token['current_price_usd'] or scraped_price
                lp_locked = token['lp_locked_percent'] or 0

                # 计算从爬取时到现在的涨跌幅
                price_change_since_scrape = 0
                if scraped_price and current_price:
                    price_change_since_scrape = ((current_price - scraped_price) / scraped_price) * 100

                logger.info(
                    f"  {i}. {symbol:12s} | "
                    f"爬取时: ${scraped_price:12.8f} (+{scraped_change:6.1f}%) | "
                    f"当前: ${current_price:12.8f} ({price_change_since_scrape:+6.1f}%) | "
                    f"LP锁仓: {lp_locked:5.1f}%"
                )
        else:
            logger.info("  （暂无未添加的潜力币种）")

        logger.info("\n" + "="*80)
        logger.info("✅ 完成！")
        logger.info("="*80)
        logger.info("\n💡 下一步操作:")
        logger.info("   1. 查看潜力币种: GET /api/potential-tokens")
        logger.info("   2. 手动添加到监控: POST /api/monitor/add-from-potential")
        logger.info("   3. 删除不感兴趣的: DELETE /api/potential-tokens/{id}")
        logger.info("\n")

    except Exception as e:
        logger.error(f"\n❌ 错误: {e}", exc_info=True)
        return 1
    finally:
        await monitor_service.close()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
