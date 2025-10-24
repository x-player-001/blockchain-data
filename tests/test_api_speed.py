#!/usr/bin/env python3
"""
测试三个API的速度对比：
1. AVE API - 批量获取代币价格
2. Dexpaprika - 获取代币信息
3. DexScreener API - 当前使用的API
"""

import time
import asyncio
import requests
from typing import List, Dict
from src.storage.db_manager import DatabaseManager
from src.storage.models import MonitoredToken
from sqlalchemy import select


# 测试用的代币地址（从监控表中获取）
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


def test_ave_api(tokens: List[Dict]) -> Dict:
    """测试 AVE API - 批量查询"""
    print("\n" + "="*60)
    print("1. 测试 AVE API（批量查询）")
    print("="*60)

    url = "https://prod.ave-api.com/v2/tokens/price"
    headers = {
        'X-API-KEY': 'hQbtbUuNvlSfuR4pV2raF63YFL3OBsw6hLGXkVX91kuEALEsiVnOxWcMiyrbYFl2',
        'Content-Type': 'application/json'
    }

    # 准备token_ids（格式：bsc_0x...）
    token_ids = [f"bsc_{token['token_address']}" for token in tokens]

    payload = {
        "token_ids": token_ids,
        "tvl_min": 0
    }

    print(f"  请求URL: {url}")
    print(f"  代币数量: {len(token_ids)}")
    print(f"  请求方式: POST（批量）")

    start_time = time.time()

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        elapsed = time.time() - start_time

        print(f"\n  状态码: {response.status_code}")
        print(f"  耗时: {elapsed:.3f}秒")

        if response.status_code == 200:
            data = response.json()
            print(f"  返回数据量: {len(data.get('data', []))} 个代币")

            # 显示前3个代币的价格
            if data.get('data'):
                print("\n  前3个代币价格:")
                for i, item in enumerate(data['data'][:3], 1):
                    symbol = item.get('symbol', 'N/A')
                    price = item.get('price', 'N/A')
                    print(f"    {i}. {symbol}: ${price}")
        else:
            print(f"  错误: {response.text[:200]}")
            elapsed = float('inf')

        return {
            'name': 'AVE API',
            'success': response.status_code == 200,
            'time': elapsed,
            'count': len(tokens),
            'time_per_token': elapsed / len(tokens) if tokens else 0
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ❌ 错误: {e}")
        return {
            'name': 'AVE API',
            'success': False,
            'time': float('inf'),
            'count': len(tokens),
            'time_per_token': float('inf')
        }


def test_dexpaprika_api(tokens: List[Dict]) -> Dict:
    """测试 Dexpaprika API - 逐个查询"""
    print("\n" + "="*60)
    print("2. 测试 Dexpaprika API（逐个查询）")
    print("="*60)

    base_url = "https://api.dexpaprika.com/networks/bsc/tokens"

    print(f"  基础URL: {base_url}")
    print(f"  代币数量: {len(tokens)}")
    print(f"  请求方式: GET（逐个）")

    start_time = time.time()
    success_count = 0

    try:
        for i, token in enumerate(tokens, 1):
            url = f"{base_url}/{token['token_address']}"

            try:
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    success_count += 1
                    data = response.json()

                    if i <= 3:  # 显示前3个
                        price = data.get('price', 'N/A')
                        print(f"  {i}. {token['symbol']}: ${price}")
                else:
                    if i <= 3:
                        print(f"  {i}. {token['symbol']}: 失败({response.status_code})")

                time.sleep(0.1)  # 避免限流

            except Exception as e:
                if i <= 3:
                    print(f"  {i}. {token['symbol']}: 错误({e})")
                continue

        elapsed = time.time() - start_time

        print(f"\n  总耗时: {elapsed:.3f}秒")
        print(f"  成功: {success_count}/{len(tokens)}")

        return {
            'name': 'Dexpaprika',
            'success': success_count > 0,
            'time': elapsed,
            'count': len(tokens),
            'time_per_token': elapsed / len(tokens) if tokens else 0
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ❌ 错误: {e}")
        return {
            'name': 'Dexpaprika',
            'success': False,
            'time': float('inf'),
            'count': len(tokens),
            'time_per_token': float('inf')
        }


def test_dexscreener_api(tokens: List[Dict]) -> Dict:
    """测试 DexScreener API - 逐个查询（当前使用）"""
    print("\n" + "="*60)
    print("3. 测试 DexScreener API（当前使用，逐个查询）")
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

                    if i <= 3:  # 显示前3个
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
            'time_per_token': float('inf')
        }


async def main():
    """主函数"""
    print("\n" + "="*80)
    print("API速度对比测试")
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
        print(f"  {i}. {token['symbol']} - {token['token_address'][:10]}...")

    # 测试三个API
    results = []

    results.append(test_ave_api(tokens))
    results.append(test_dexpaprika_api(tokens))
    results.append(test_dexscreener_api(tokens))

    # 汇总结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)

    # 按速度排序
    results_sorted = sorted([r for r in results if r['success']], key=lambda x: x['time'])

    print(f"\n{'API名称':<20} {'总耗时':<12} {'平均/个':<12} {'成功':<8}")
    print("-"*60)

    for result in results:
        success = "✓" if result['success'] else "✗"
        time_str = f"{result['time']:.3f}秒" if result['time'] != float('inf') else "失败"
        avg_str = f"{result['time_per_token']:.3f}秒" if result['time_per_token'] != float('inf') else "N/A"

        print(f"{result['name']:<20} {time_str:<12} {avg_str:<12} {success:<8}")

    # 显示最快的
    if results_sorted:
        fastest = results_sorted[0]
        print(f"\n🏆 最快: {fastest['name']} ({fastest['time']:.3f}秒)")

        if len(results_sorted) > 1:
            second = results_sorted[1]
            speedup = second['time'] / fastest['time']
            print(f"   比第二名快 {speedup:.2f}x")

    print("\n" + "="*80)


if __name__ == '__main__':
    asyncio.run(main())
