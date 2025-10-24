#!/usr/bin/env python3
"""
爬取潜力币种脚本 - 非 headless 模式（用于绕过 Cloudflare）
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
        logger.info("🚀 开始爬取潜力币种（非 headless 模式 - 绕过 Cloudflare）")
        logger.info("="*80 + "\n")

        # 爬取并保存（非 headless 模式）
        scrape_result = await monitor_service.scrape_and_save_to_potential(
            count=100,
            top_n=10,
            headless=False  # 使用可见浏览器窗口
        )

        logger.info(f"\n✅ 爬取完成:")
        logger.info(f"   - 爬取总数: {scrape_result['scraped']}")
        logger.info(f"   - Top涨幅: {scrape_result['top_gainers']}")
        logger.info(f"   - 新增: {scrape_result['added']}")
        logger.info(f"   - 跳过: {scrape_result['skipped']}")

        # 如果有新增的代币，更新 AVE API 数据
        if scrape_result['added'] > 0:
            logger.info("\n📈 更新 AVE API 数据...")
            update_result = await monitor_service.update_potential_tokens_data(delay=0.3)

            logger.info(f"\n✅ 更新完成:")
            logger.info(f"   - 更新成功: {update_result['updated']}")
            logger.info(f"   - 更新失败: {update_result['failed']}")

        logger.info("\n✅ 完成！")

    except Exception as e:
        logger.error(f"\n❌ 错误: {e}", exc_info=True)
        return 1
    finally:
        await monitor_service.close()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
