#!/usr/bin/env python3
"""
使用AVE API更新监控代币的详细信息
获取历史ATH、交易数据、LP信息等
"""

import asyncio
import time
from src.storage.db_manager import DatabaseManager
from src.storage.models import MonitoredToken
from src.services.ave_api_service import ave_api_service
from sqlalchemy import select


async def update_monitored_tokens_with_ave_data():
    """使用AVE API更新所有监控代币的详细数据"""

    print("\n" + "="*80)
    print("使用AVE API更新监控代币详细信息")
    print("="*80 + "\n")

    db_manager = DatabaseManager()
    await db_manager.init_async_db()

    async with db_manager.get_session() as session:
        # 获取所有活跃的监控代币
        result = await session.execute(
            select(MonitoredToken).where(MonitoredToken.status == "active")
        )
        tokens = result.scalars().all()

        print(f"找到 {len(tokens)} 个活跃监控代币\n")

        if not tokens:
            print("没有找到需要更新的代币")
            await db_manager.close()
            return

        updated_count = 0
        failed_count = 0

        for i, token in enumerate(tokens, 1):
            print(f"{i}. {token.token_symbol:12s} pair={token.pair_address[:10]}...")

            # 调用AVE API获取交易对详情
            try:
                pair_data = ave_api_service.get_pair_detail_parsed(
                    pair_address=token.pair_address,
                    chain="bsc"
                )

                if pair_data:
                    # 更新数据库字段
                    updates_made = []

                    # Token地址（如果AVE返回的不同）
                    if pair_data.get('token_address') and pair_data['token_address'].lower() != token.token_address:
                        token.token_address = pair_data['token_address'].lower()
                        updates_made.append("token_address")

                    # AMM类型
                    if pair_data.get('amm'):
                        token.amm = pair_data['amm']
                        updates_made.append("amm")

                    # 当前价格
                    if pair_data.get('current_price_usd'):
                        token.current_price_usd = pair_data['current_price_usd']
                        updates_made.append("current_price")

                    # 历史最高价 (重要!)
                    if pair_data.get('price_ath_usd'):
                        token.price_ath_usd = pair_data['price_ath_usd']
                        updates_made.append("price_ath_usd")
                        print(f"   ATH价格: ${pair_data['price_ath_usd']}")

                    # 市场数据
                    if pair_data.get('current_tvl'):
                        token.current_tvl = pair_data['current_tvl']
                        updates_made.append("tvl")

                    if pair_data.get('current_market_cap'):
                        token.current_market_cap = pair_data['current_market_cap']
                        updates_made.append("market_cap")

                    # 价格变化
                    for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '24h']:
                        field = f'price_change_{timeframe}'
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # 交易量
                    for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '24h']:
                        field = f'volume_{timeframe}'
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # 交易次数
                    for timeframe in ['1m', '5m', '15m', '30m', '1h', '4h', '24h']:
                        field = f'tx_count_{timeframe}'
                        if pair_data.get(field) is not None:
                            setattr(token, field, pair_data[field])

                    # 买卖数据
                    if pair_data.get('buys_24h') is not None:
                        token.buys_24h = pair_data['buys_24h']
                    if pair_data.get('sells_24h') is not None:
                        token.sells_24h = pair_data['sells_24h']

                    # 交易者数据
                    if pair_data.get('makers_24h') is not None:
                        token.makers_24h = pair_data['makers_24h']
                    if pair_data.get('buyers_24h') is not None:
                        token.buyers_24h = pair_data['buyers_24h']
                    if pair_data.get('sellers_24h') is not None:
                        token.sellers_24h = pair_data['sellers_24h']

                    # 24小时价格范围
                    if pair_data.get('price_24h_high') is not None:
                        token.price_24h_high = pair_data['price_24h_high']
                    if pair_data.get('price_24h_low') is not None:
                        token.price_24h_low = pair_data['price_24h_low']
                    if pair_data.get('open_price_24h') is not None:
                        token.open_price_24h = pair_data['open_price_24h']

                    # Token创建信息
                    if pair_data.get('token_created_at'):
                        token.token_created_at = pair_data['token_created_at']
                        updates_made.append("created_at")
                    if pair_data.get('first_trade_at'):
                        token.first_trade_at = pair_data['first_trade_at']
                    if pair_data.get('creation_block_number'):
                        token.creation_block_number = pair_data['creation_block_number']
                    if pair_data.get('creation_tx_hash'):
                        token.creation_tx_hash = pair_data['creation_tx_hash']

                    # LP信息
                    if pair_data.get('lp_holders') is not None:
                        token.lp_holders = pair_data['lp_holders']
                    if pair_data.get('lp_locked_percent') is not None:
                        token.lp_locked_percent = pair_data['lp_locked_percent']
                        print(f"   LP锁仓: {pair_data['lp_locked_percent']}%")
                    if pair_data.get('lp_lock_platform'):
                        token.lp_lock_platform = pair_data['lp_lock_platform']

                    # 早期交易指标
                    if pair_data.get('rusher_tx_count') is not None:
                        token.rusher_tx_count = pair_data['rusher_tx_count']
                    if pair_data.get('sniper_tx_count') is not None:
                        token.sniper_tx_count = pair_data['sniper_tx_count']

                    session.add(token)
                    updated_count += 1

                    print(f"   ✓ 更新成功 ({len(updates_made)} 个关键字段)")
                    if updates_made[:3]:  # 显示前3个主要更新
                        print(f"   主要更新: {', '.join(updates_made[:3])}")
                else:
                    print(f"   ❌ AVE API返回空数据")
                    failed_count += 1

            except Exception as e:
                print(f"   ❌ 错误: {e}")
                failed_count += 1

            # 避免限流
            time.sleep(0.3)
            print()

        # 提交所有更新
        if updated_count > 0:
            await session.commit()
            print(f"✓ 已提交 {updated_count} 个代币的更新到数据库")

    await db_manager.close()

    print("\n" + "="*80)
    print("更新完成")
    print("="*80)
    print(f"  总数: {len(tokens)}")
    print(f"  成功: {updated_count}")
    print(f"  失败: {failed_count}")
    print("="*80 + "\n")


if __name__ == '__main__':
    asyncio.run(update_monitored_tokens_with_ave_data())
