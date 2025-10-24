#!/usr/bin/env python3
"""
测试监控服务的价格更新功能（使用AVE API）
"""

import asyncio
from src.services.token_monitor_service import TokenMonitorService
from src.storage.db_manager import DatabaseManager
from src.storage.models import MonitoredToken
from sqlalchemy import select


async def display_token_info(db_manager: DatabaseManager):
    """显示更新前后的代币信息"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(MonitoredToken)
            .where(MonitoredToken.status == "active")
            .limit(3)  # 显示前3个
        )
        tokens = result.scalars().all()

        print("\n更新后的代币信息（前3个）:")
        print("="*100)

        for token in tokens:
            print(f"\n代币: {token.token_symbol}")
            print(f"  当前价格: ${token.current_price_usd}")
            print(f"  历史最高价(ATH): ${token.price_ath_usd}" if token.price_ath_usd else "  历史最高价(ATH): N/A")
            print(f"  入场价格: ${token.entry_price_usd}")
            print(f"  峰值价格: ${token.peak_price_usd}")
            print(f"  TVL: ${token.current_tvl:,.2f}" if token.current_tvl else "  TVL: N/A")
            print(f"  市值: ${token.current_market_cap:,.2f}" if token.current_market_cap else "  市值: N/A")
            print(f"  24h交易量: ${token.volume_24h:,.2f}" if token.volume_24h else "  24h交易量: N/A")
            print(f"  24h价格变化: {token.price_change_24h}%" if token.price_change_24h else "  24h价格变化: N/A")
            print(f"  24h买入次数: {token.buys_24h}" if token.buys_24h else "  24h买入次数: N/A")
            print(f"  24h卖出次数: {token.sells_24h}" if token.sells_24h else "  24h卖出次数: N/A")
            print(f"  LP锁仓: {token.lp_locked_percent}%" if token.lp_locked_percent else "  LP锁仓: N/A")
            print(f"  最后更新: {token.last_update_timestamp}")

        print("\n" + "="*100)


async def test_monitor_update():
    """测试监控服务更新功能"""

    print("\n" + "="*80)
    print("测试监控服务 - 使用AVE API更新代币价格和详细信息")
    print("="*80 + "\n")

    # 初始化服务
    db_manager = DatabaseManager()
    await db_manager.init_async_db()

    monitor_service = TokenMonitorService(db_manager=db_manager)

    # 执行更新
    print("正在调用 update_monitored_prices() ...\n")

    result = await monitor_service.update_monitored_prices(delay=0.3)

    print("\n" + "="*80)
    print("更新结果统计")
    print("="*80)
    print(f"  总监控数: {result['total_monitored']}")
    print(f"  成功更新: {result['updated']}")
    print(f"  触发报警: {result['alerts_triggered']}")
    print("="*80)

    # 显示更新后的信息
    await display_token_info(db_manager)

    await monitor_service.close()

    print("\n测试完成!\n")


if __name__ == '__main__':
    asyncio.run(test_monitor_update())
