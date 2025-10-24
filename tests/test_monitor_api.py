#!/usr/bin/env python3
"""
测试监控代币API - 验证完整的AVE API字段返回
"""

import requests
import json


def test_monitor_tokens_api():
    """测试 GET /api/monitor/tokens 接口"""

    print("\n" + "="*80)
    print("测试监控代币API - 完整AVE API数据")
    print("="*80 + "\n")

    # API URL
    url = "http://localhost:8888/api/monitor/tokens"
    params = {"limit": 5}

    print(f"请求: GET {url}")
    print(f"参数: {params}\n")

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            print(f"✓ 请求成功 (状态码: {response.status_code})")
            print(f"✓ 返回代币数量: {data['total']}\n")

            if data['total'] > 0:
                # 显示第一个代币的完整信息
                token = data['data'][0]

                print("="*80)
                print(f"代币详情: {token['token_symbol']}")
                print("="*80)

                # 基础信息
                print("\n【基础信息】")
                print(f"  代币地址: {token['token_address']}")
                print(f"  代币名称: {token['token_name']}")
                print(f"  交易对: {token['pair_address']}")
                print(f"  DEX: {token['dex_id']}")
                print(f"  AMM: {token['amm']}")

                # 价格信息
                print("\n【价格信息】")
                print(f"  入场价格: ${token['entry_price_usd']}")
                print(f"  当前价格: ${token['current_price_usd']}")
                print(f"  监控峰值: ${token['peak_price_usd']}")
                print(f"  历史ATH: ${token['price_ath_usd']}")

                # 时间信息
                print("\n【时间信息】")
                print(f"  入场时间: {token['entry_timestamp']}")
                print(f"  最后更新: {token['last_update_timestamp']}")
                print(f"  代币创建: {token['token_created_at']}")
                print(f"  首次交易: {token['first_trade_at']}")

                # 市场数据
                print("\n【市场数据】")
                print(f"  当前TVL: ${token['current_tvl']:,.2f}" if token['current_tvl'] else "  当前TVL: N/A")
                print(f"  当前市值: ${token['current_market_cap']:,.2f}" if token['current_market_cap'] else "  当前市值: N/A")
                print(f"  入场时市值: ${token['market_cap_at_entry']:,.2f}" if token['market_cap_at_entry'] else "  入场时市值: N/A")

                # 价格变化（多时间段）
                print("\n【价格变化】")
                print(f"  1分钟: {token['price_change_1m']}%" if token['price_change_1m'] else "  1分钟: N/A")
                print(f"  5分钟: {token['price_change_5m']}%" if token['price_change_5m'] else "  5分钟: N/A")
                print(f"  1小时: {token['price_change_1h']}%" if token['price_change_1h'] else "  1小时: N/A")
                print(f"  24小时: {token['price_change_24h']}%" if token['price_change_24h'] else "  24小时: N/A")

                # 交易量
                print("\n【交易量】")
                print(f"  1小时: ${token['volume_1h']:,.2f}" if token['volume_1h'] else "  1小时: N/A")
                print(f"  24小时: ${token['volume_24h']:,.2f}" if token['volume_24h'] else "  24小时: N/A")

                # 交易数据
                print("\n【交易数据】")
                print(f"  24h交易次数: {token['tx_count_24h']}" if token['tx_count_24h'] else "  24h交易次数: N/A")
                print(f"  24h买入: {token['buys_24h']}" if token['buys_24h'] else "  24h买入: N/A")
                print(f"  24h卖出: {token['sells_24h']}" if token['sells_24h'] else "  24h卖出: N/A")

                # 交易者
                print("\n【交易者】")
                print(f"  做市商: {token['makers_24h']}" if token['makers_24h'] else "  做市商: N/A")
                print(f"  买家: {token['buyers_24h']}" if token['buyers_24h'] else "  买家: N/A")
                print(f"  卖家: {token['sellers_24h']}" if token['sellers_24h'] else "  卖家: N/A")

                # LP信息
                print("\n【LP信息】")
                print(f"  LP持有人: {token['lp_holders']}" if token['lp_holders'] else "  LP持有人: N/A")
                print(f"  LP锁仓: {token['lp_locked_percent']}%" if token['lp_locked_percent'] else "  LP锁仓: N/A")
                print(f"  锁仓平台: {token['lp_lock_platform']}" if token['lp_lock_platform'] else "  锁仓平台: N/A")

                # 安全指标
                print("\n【安全指标】")
                print(f"  Rusher交易: {token['rusher_tx_count']}" if token['rusher_tx_count'] else "  Rusher交易: N/A")
                print(f"  Sniper交易: {token['sniper_tx_count']}" if token['sniper_tx_count'] else "  Sniper交易: N/A")

                # 监控状态
                print("\n【监控状态】")
                print(f"  状态: {token['status']}")
                print(f"  跌幅阈值: {token['drop_threshold_percent']}%")

                print("\n" + "="*80)

                # 统计字段数量
                total_fields = len(token.keys())
                non_null_fields = sum(1 for v in token.values() if v is not None)

                print(f"\n字段统计:")
                print(f"  总字段数: {total_fields}")
                print(f"  非空字段: {non_null_fields}")
                print(f"  空字段: {total_fields - non_null_fields}")

                # 保存完整JSON到文件
                with open('/tmp/monitor_token_response.json', 'w', encoding='utf-8') as f:
                    json.dump(token, f, indent=2, ensure_ascii=False)
                print(f"\n✓ 完整响应已保存到: /tmp/monitor_token_response.json")

            else:
                print("⚠ 当前没有监控代币")

        else:
            print(f"✗ 请求失败 (状态码: {response.status_code})")
            print(f"错误信息: {response.text}")

    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到API服务器")
        print("请确保API服务正在运行: python run_api.py")
    except Exception as e:
        print(f"✗ 发生错误: {e}")

    print("\n" + "="*80)
    print("测试完成")
    print("="*80 + "\n")


if __name__ == '__main__':
    test_monitor_tokens_api()
