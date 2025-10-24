#!/usr/bin/env python3
"""
更新监控表中的真实token地址
目前存的是pair地址，需要从DexScreener API获取真正的token地址
"""

import asyncio
import requests
import time
from src.storage.db_manager import DatabaseManager
from src.storage.models import MonitoredToken
from sqlalchemy import select


async def update_token_addresses():
    """从DexScreener获取真实token地址并更新数据库"""

    print("\n" + "="*80)
    print("更新监控表中的真实Token地址")
    print("="*80 + "\n")

    db_manager = DatabaseManager()
    await db_manager.init_async_db()

    async with db_manager.get_session() as session:
        # 获取所有监控的代币
        result = await session.execute(
            select(MonitoredToken).where(MonitoredToken.status == "active")
        )
        tokens = result.scalars().all()

        print(f"找到 {len(tokens)} 个监控代币\n")

        updated_count = 0
        failed_count = 0

        for i, token in enumerate(tokens, 1):
            print(f"{i}. {token.token_symbol:12s} pair={token.pair_address[:10]}...")

            # 调用DexScreener API获取pair详情
            url = f"https://api.dexscreener.com/latest/dex/pairs/bsc/{token.pair_address}"

            try:
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    pair = data.get('pair') or data.get('pairs', [{}])[0]

                    if pair:
                        real_token_address = pair.get('baseToken', {}).get('address', '')

                        if real_token_address and real_token_address != token.token_address:
                            print(f"   旧token地址: {token.token_address}")
                            print(f"   新token地址: {real_token_address}")

                            # 更新数据库
                            token.token_address = real_token_address.lower()
                            session.add(token)
                            updated_count += 1
                            print(f"   ✓ 已更新")
                        else:
                            print(f"   token地址: {real_token_address}")
                            print(f"   ⚠ 相同，无需更新")
                    else:
                        print(f"   ❌ API返回空数据")
                        failed_count += 1
                else:
                    print(f"   ❌ API调用失败: {response.status_code}")
                    failed_count += 1

            except Exception as e:
                print(f"   ❌ 错误: {e}")
                failed_count += 1

            time.sleep(0.3)  # 避免限流
            print()

        # 提交更新
        if updated_count > 0:
            await session.commit()
            print(f"✓ 已提交 {updated_count} 个更新到数据库")

    await db_manager.close()

    print("\n" + "="*80)
    print("更新完成")
    print("="*80)
    print(f"  总数: {len(tokens)}")
    print(f"  已更新: {updated_count}")
    print(f"  失败: {failed_count}")
    print(f"  无需更新: {len(tokens) - updated_count - failed_count}")
    print("="*80 + "\n")


if __name__ == '__main__':
    asyncio.run(update_token_addresses())
