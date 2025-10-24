#!/usr/bin/env python3
"""
API速度对比测试 V2
对比：AVE搜索接口 vs DexScreener API
"""

import time
import asyncio
import requests
from typing import List, Dict
from src.storage.db_manager import DatabaseManager
from src.storage.models import MonitoredToken
from sqlalchemy import select


async def get_test_tokens(limit: int = 10) -> List[Dict]:
    """从监控表获取测试用的代币"""
    db_manager = DatabaseManager()
    await db_manager.init_async_db()

    async with db_manager.get_session() as session:
        result = await session.execute(
            select(MonitoredToken).where(MonitoredToken.status == "active").limit(limit)
        )
        tokens = result.scalars().all()

        test_data = []
        for token in tokens:
            test_data.append({
                'token_address': token.token_address,
                'pair_address': token.pair_address,
                'symbol': token.token_symbol
            })

    await db_manager.close()
    return test_data


def test_ave_search_api(tokens: List[Dict]) -> Dict:
    """测试 AVE API - 搜索接口（逐个查询）"""
    print("\n" + "="*60)
    print("1. 测试 AVE API（搜索接口，逐个查询）")
    print("="*60)

    base_url = "https://prod.ave-api.com/v2/tokens"
    headers = {
        'X-API-KEY': 'hQbtbUuNvlSfuR4pV2raF63YFL3OBsw6hLGXkVX91kuEALEsiVnOxWcMiyrbYFl2'
    }

    print(f"  基础URL: {base_url}")
    print(f"  代币数量: {len(tokens)}")
    print(f"  请求方式: GET（搜索，逐个）")

    start_time = time.time()
    success_count = 0

    try:
        for i, token in enumerate(tokens, 1):
            url = f"{base_url}?keyword={token['symbol']}&chain=bsc&limit=1"

            try:
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()

                    if data.get('data') and len(data['data']) > 0:
                        success_count += 1
                        token_data = data['data'][0]
                        price = token_data.get('current_price_usd', 'N/A')

                        if i <= 3:
                            print(f"  {i}. {token['symbol']}: ${price}")
                    else:
                        if i <= 3:
                            print(f"  {i}. {token['symbol']}: 未找到")
                else:
                    if i <= 3:
                        print(f"  {i}. {token['symbol']}: 失败({response.status_code})")

                time.sleep(0.05)  # 短延迟

            except Exception as e:
                if i <= 3:
                    print(f"  {i}. {token['symbol']}: 错误({e})")
                continue

        elapsed = time.time() - start_time

        print(f"\n  总耗时: {elapsed:.3f}秒")
        print(f"  成功: {success_count}/{len(tokens)}")

        return {
            'name': 'AVE Search',
            'success': success_count > 0,
            'time': elapsed,
            'count': len(tokens),
            'success_count': success_count,
            'time_per_token': elapsed / len(tokens) if tokens else 0
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ❌ 错误: {e}")
        return {
            'name': 'AVE Search',
            'success': False,
            'time': float('inf'),
            'count': len(tokens),
            'success_count': 0,
            'time_per_token': float('inf')
        }


def test_dexscreener_api(tokens: List[Dict]) -> Dict:
    """测试 DexScreener API - 逐个查询（当前使用）"""
    print("\n" + "="*60)
    print("2. 测试 DexScreener API（当前使用，逐个查询）")
    print("="*60)

    base_url = "https://api.dexscreener.com/latest/dex/pairs/bsc"

    print(f"  基础URL: {base_url}")
    print(f"  代币数量: {len(tokens)}")
    print(f"  请求方式: GET（逐个）")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    start_time = time.time()
    success_count = 0

    try:
        for i, token in enumerate(tokens, 1):
            url = f"{base_url}/{token['pair_address']}"

            try:
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    success_count += 1
                    data = response.json()

                    if i <= 3:
                        pair = data.get('pair') or data.get('pairs', [{}])[0]
                        price = pair.get('priceUsd', 'N/A')
                        print(f"  {i}. {token['symbol']}: ${price}")
                else:
                    if i <= 3:
                        print(f"  {i}. {token['symbol']}: 失败({response.status_code})")

                time.sleep(0.3)  # DexScreener建议延迟

            except Exception as e:
                if i <= 3:
                    print(f"  {i}. {token['symbol']}: 错误({e})")
                continue

        elapsed = time.time() - start_time

        print(f"\n  总耗时: {elapsed:.3f}秒")
        print(f"  成功: {success_count}/{len(tokens)}")

        return {
            'name': 'DexScreener',
            'success': success_count > 0,
            'time': elapsed,
            'count': len(tokens),
            'success_count': success_count,
            'time_per_token': elapsed / len(tokens) if tokens else 0
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ❌ 错误: {e}")
        return {
            'name': 'DexScreener',
            'success': False,
            'time': float('inf'),
            'count': len(tokens),
            'success_count': 0,
            'time_per_token': float('inf')
        }


async def main():
    """主函数"""
    print("\n" + "="*80)
    print("API速度对比测试 V2")
    print("AVE搜索接口 vs DexScreener API")
    print("="*80)

    # 获取测试代币
    print("\n获取测试代币...")
    tokens = await get_test_tokens(limit=10)

    if not tokens:
        print("❌ 监控表中没有代币，请先添加监控")
        return

    print(f"✓ 已获取 {len(tokens)} 个测试代币")
    print("\n代币列表:")
    for i, token in enumerate(tokens, 1):
        print(f"  {i}. {token['symbol']}")

    # 测试两个API
    results = []

    results.append(test_ave_search_api(tokens))
    results.append(test_dexscreener_api(tokens))

    # 汇总结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)

    print(f"\n{'API名称':<20} {'总耗时':<12} {'平均/个':<12} {'成功率':<12}")
    print("-"*60)

    for result in results:
        time_str = f"{result['time']:.3f}秒" if result['time'] != float('inf') else "失败"
        avg_str = f"{result['time_per_token']:.3f}秒" if result['time_per_token'] != float('inf') else "N/A"
        success_rate = f"{result['success_count']}/{result['count']}"

        print(f"{result['name']:<20} {time_str:<12} {avg_str:<12} {success_rate:<12}")

    # 显示对比
    if results[0]['success'] and results[1]['success']:
        ave_time = results[0]['time']
        dex_time = results[1]['time']

        if ave_time < dex_time:
            speedup = dex_time / ave_time
            print(f"\n🏆 AVE Search 更快: {ave_time:.3f}秒 vs {dex_time:.3f}秒")
            print(f"   快了 {speedup:.2f}x")
        else:
            speedup = ave_time / dex_time
            print(f"\n🏆 DexScreener 更快: {dex_time:.3f}秒 vs {ave_time:.3f}秒")
            print(f"   快了 {speedup:.2f}x")

    print("\n" + "="*80)


if __name__ == '__main__':
    asyncio.run(main())
