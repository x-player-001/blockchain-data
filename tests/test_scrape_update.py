#!/usr/bin/env python3
"""
测试爬取更新逻辑
"""

import asyncio
from src.storage.db_manager import DatabaseManager
from sqlalchemy import select
from src.storage.models import PotentialToken
from datetime import datetime

async def test_update_logic():
    """
    测试更新逻辑：
    1. 手动降低一个代币的涨幅
    2. 模拟爬取到更高的涨幅
    3. 验证是否正确更新
    """
    db = DatabaseManager()

    print("="*80)
    print("测试爬取更新逻辑")
    print("="*80)

    # 步骤1: 选择一个代币，手动降低其涨幅
    async with db.get_session() as session:
        result = await session.execute(
            select(PotentialToken).limit(1)
        )
        test_token = result.scalar_one_or_none()

        if not test_token:
            print("❌ 没有找到测试代币")
            return

        print(f"\n【步骤1】选择测试代币: {test_token.token_symbol}")
        print(f"  原始涨幅: {test_token.price_change_24h_at_scrape}%")

        # 保存原始值
        original_change = test_token.price_change_24h_at_scrape
        original_price = test_token.scraped_price_usd
        pair_address = test_token.pair_address

        # 手动降低涨幅到 50%
        test_token.price_change_24h_at_scrape = 50.0
        test_token.scraped_price_usd = 0.001
        await session.commit()

        print(f"  修改后涨幅: {test_token.price_change_24h_at_scrape}%")

    # 步骤2: 模拟爬取到更高涨幅（100%）
    print(f"\n【步骤2】模拟爬取更高涨幅数据")

    async with db.get_session() as session:
        result = await session.execute(
            select(PotentialToken).where(
                PotentialToken.pair_address == pair_address
            )
        )
        existing = result.scalar_one_or_none()

        old_change = existing.price_change_24h_at_scrape
        new_change = 100.0  # 模拟更高的涨幅
        new_price = 0.002

        print(f"  数据库涨幅: {old_change}%")
        print(f"  爬取涨幅: {new_change}%")

        # 应用更新逻辑
        if new_change > old_change:
            existing.scraped_price_usd = new_price
            existing.scraped_timestamp = datetime.utcnow()
            existing.price_change_24h_at_scrape = new_change
            await session.commit()

            print(f"  ✅ 涨幅更高，已更新: {old_change}% → {new_change}%")
        else:
            print(f"  ⏭️  涨幅未提高，跳过更新")

    # 步骤3: 验证更新结果
    print(f"\n【步骤3】验证更新结果")

    async with db.get_session() as session:
        result = await session.execute(
            select(PotentialToken).where(
                PotentialToken.pair_address == pair_address
            )
        )
        updated_token = result.scalar_one_or_none()

        print(f"  代币: {updated_token.token_symbol}")
        print(f"  当前价格: ${updated_token.scraped_price_usd}")
        print(f"  当前涨幅: {updated_token.price_change_24h_at_scrape}%")

    # 步骤4: 模拟爬取到更低涨幅（80%）
    print(f"\n【步骤4】模拟爬取更低涨幅数据")

    async with db.get_session() as session:
        result = await session.execute(
            select(PotentialToken).where(
                PotentialToken.pair_address == pair_address
            )
        )
        existing = result.scalar_one_or_none()

        old_change = existing.price_change_24h_at_scrape
        new_change = 80.0  # 模拟更低的涨幅

        print(f"  数据库涨幅: {old_change}%")
        print(f"  爬取涨幅: {new_change}%")

        # 应用更新逻辑
        if new_change > old_change:
            existing.price_change_24h_at_scrape = new_change
            await session.commit()
            print(f"  ✅ 涨幅更高，已更新")
        else:
            print(f"  ⏭️  涨幅未提高（{new_change}% <= {old_change}%），跳过更新")

    # 步骤5: 恢复原始数据
    print(f"\n【步骤5】恢复原始数据")

    async with db.get_session() as session:
        result = await session.execute(
            select(PotentialToken).where(
                PotentialToken.pair_address == pair_address
            )
        )
        token = result.scalar_one_or_none()

        token.price_change_24h_at_scrape = original_change
        token.scraped_price_usd = original_price
        await session.commit()

        print(f"  ✅ 已恢复原始数据")
        print(f"  涨幅: {token.price_change_24h_at_scrape}%")

    print("\n" + "="*80)
    print("测试完成")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_update_logic())
