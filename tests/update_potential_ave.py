#!/usr/bin/env python3
"""
更新潜力币种的 AVE API 数据
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.services.token_monitor_service import TokenMonitorService
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def main():
    """主函数"""
    monitor_service = TokenMonitorService()

    try:
        logger.info("🔄 开始更新潜力币种的 AVE API 数据...")

        update_result = await monitor_service.update_potential_tokens_data(delay=0.3)

        logger.info(f"\n✅ 更新完成:")
        logger.info(f"   - 更新成功: {update_result['updated']}")
        logger.info(f"   - 更新失败: {update_result['failed']}\n")

    except Exception as e:
        logger.error(f"\n❌ 错误: {e}", exc_info=True)
        return 1
    finally:
        await monitor_service.close()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
