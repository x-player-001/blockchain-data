#!/usr/bin/env python3
"""
手动更新潜力代币的 AVE API 数据
用于立即应用 market_cap 字段的修复
"""

import asyncio
from src.services.token_monitor_service import TokenMonitorService


async def update_potential_tokens():
    """更新所有潜力代币的数据"""
    service = TokenMonitorService()

    try:
        print("=" * 60)
        print("开始更新潜力代币 AVE API 数据...")
        print("=" * 60)

        # 强制更新（跳过时间间隔检查）
        result = await service.update_potential_tokens_data(
            delay=0.3,
            min_update_interval_minutes=0  # 跳过间隔检查
        )

        print(f"\n✅ 更新完成:")
        print(f"   - 成功更新: {result['updated']} 个")
        print(f"   - 失败: {result['failed']} 个")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(update_potential_tokens())
