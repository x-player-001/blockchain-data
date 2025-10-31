#!/usr/bin/env python3
"""
测试 AVE API 返回的 token 地址是否正确
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.ave_api_service import ave_api_service
import json


def test_ave_token_address(pair_address: str, chain: str = "bsc"):
    """
    测试 AVE API 返回的 token 地址

    Args:
        pair_address: 交易对地址
        chain: 链名称
    """
    print("="*80)
    print(f"测试交易对: {pair_address} ({chain})")
    print("="*80)

    # 1. 获取原始数据
    print("\n1. 获取 AVE API 原始返回数据...")
    raw_data = ave_api_service.get_pair_detail(pair_address, chain)

    if not raw_data:
        print("❌ 无法获取数据")
        return

    print("✅ 成功获取数据\n")

    # 2. 显示关键字段
    data = raw_data.get('data', {})

    print("2. 关键字段:")
    print(f"  pair_address (API): {data.get('pair')}")
    print(f"  target_token:       {data.get('target_token')}")
    print(f"  token0_address:     {data.get('token0_address')}")
    print(f"  token0_symbol:      {data.get('token0_symbol')}")
    print(f"  token0_name:        {data.get('token0_name')}")
    print(f"  token1_address:     {data.get('token1_address')}")
    print(f"  token1_symbol:      {data.get('token1_symbol')}")
    print(f"  token1_name:        {data.get('token1_name')}")

    # 3. 解析后的数据
    print("\n3. 解析后的结果:")
    parsed = ave_api_service.parse_pair_data(raw_data)

    if parsed:
        print(f"  token_address:       {parsed.get('token_address')}")
        print(f"  token_symbol:        {parsed.get('token_symbol')}")
        print(f"  token_name:          {parsed.get('token_name')}")
        print(f"  quote_token_address: {parsed.get('quote_token_address')}")
        print(f"  quote_token_symbol:  {parsed.get('quote_token_symbol')}")
        print(f"  current_price_usd:   {parsed.get('current_price_usd')}")
    else:
        print("❌ 解析失败")
        return

    # 4. 验证逻辑
    print("\n4. 验证:")
    target = data.get('target_token', '').lower()
    token0 = data.get('token0_address', '').lower()
    token1 = data.get('token1_address', '').lower()

    if target == token0:
        print(f"  ✅ target_token == token0_address")
        print(f"     目标代币是 token0: {data.get('token0_symbol')}")
        print(f"     报价代币是 token1: {data.get('token1_symbol')}")
    elif target == token1:
        print(f"  ✅ target_token == token1_address")
        print(f"     目标代币是 token1: {data.get('token1_symbol')}")
        print(f"     报价代币是 token0: {data.get('token0_symbol')}")
    else:
        print(f"  ⚠️ target_token 不匹配 token0 或 token1")

    # 5. 与 pair_address 对比
    print("\n5. 地址对比:")
    print(f"  输入的 pair_address:  {pair_address.lower()}")
    print(f"  解析的 token_address: {parsed.get('token_address')}")

    if pair_address.lower() == parsed.get('token_address'):
        print(f"  ⚠️ token_address == pair_address （这是不对的！）")
    else:
        print(f"  ✅ token_address != pair_address （正确）")

    print("\n" + "="*80)


if __name__ == "__main__":
    # 测试几个交易对
    test_pairs = [
        # BSC 测试案例
        ("0x16b9a82891338f9ba80e2d6970fdda79d1eb0dae", "bsc"),  # 随机 BSC pair
    ]

    # 如果命令行提供了参数，使用命令行参数
    if len(sys.argv) >= 2:
        pair = sys.argv[1]
        chain = sys.argv[2] if len(sys.argv) >= 3 else "bsc"
        test_pairs = [(pair, chain)]

    for pair_addr, chain in test_pairs:
        test_ave_token_address(pair_addr, chain)
        print("\n")
