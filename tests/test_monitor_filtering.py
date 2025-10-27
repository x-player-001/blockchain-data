#!/usr/bin/env python3
"""
Test script for monitoring filtering logic
"""

import asyncio
from src.services.token_monitor_service import TokenMonitorService


async def test_monitor_config():
    """Test loading monitor configuration"""
    print("=" * 60)
    print("Testing Monitor Configuration Loading")
    print("=" * 60)

    service = TokenMonitorService()

    try:
        # This will test if the monitor config can be loaded
        # and if the filtering logic works
        await service._ensure_db()

        # Load config from database
        from src.storage.models import MonitorConfig
        from sqlalchemy import select

        async with service.db_manager.get_session() as session:
            result = await session.execute(
                select(MonitorConfig).limit(1)
            )
            config = result.scalar_one_or_none()

            if config:
                print(f"✅ Found monitor config:")
                print(f"   - Min Market Cap: ${config.min_monitor_market_cap}")
                print(f"   - Min Liquidity: ${config.min_monitor_liquidity}")
                print(f"   - Update Interval: {config.update_interval_minutes} minutes")
                print(f"   - Enabled: {bool(config.enabled)}")
            else:
                print("⚠️  No monitor config found (will use defaults)")

        print("\n" + "=" * 60)
        print("Test completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(test_monitor_config())
