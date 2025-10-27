#!/usr/bin/env python3
"""
测试手动添加监控代币并验证 market_cap 字段
"""

import requests
import json

url = "http://localhost:8888/api/monitor/add-by-pair"
data = {
    "pair_address": "0x172fcd41e0913e95784454622d1c3724f546f849",
    "chain": "bsc",
    "drop_threshold": 20
}

print("=" * 60)
print("测试添加监控代币...")
print("=" * 60)

response = requests.post(url, json=data)

if response.status_code == 200:
    result = response.json()
    print("\n✅ 添加成功:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 获取代币详情
    print("\n" + "=" * 60)
    print("检查代币 market_cap 字段...")
    print("=" * 60)

    tokens_response = requests.get("http://localhost:8888/api/monitored-tokens?limit=1")
    if tokens_response.status_code == 200:
        tokens_data = tokens_response.json()
        tokens = tokens_data.get('tokens', [])
        if tokens:
            token = tokens[0]
            print(f"\nToken: {token['token_symbol']}")
            print(f"Current Price: ${token.get('current_price_usd')}")
            print(f"Current TVL: ${token.get('current_tvl')}")
            print(f"Current Market Cap: ${token.get('current_market_cap')}")

            if token.get('current_market_cap'):
                print("\n✅ Market Cap 字段已正确填充!")
            else:
                print("\n❌ Market Cap 字段仍然为 null")
else:
    print(f"\n❌ 添加失败: {response.status_code}")
    print(response.text)

print("=" * 60)
