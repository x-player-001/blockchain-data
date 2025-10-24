#!/usr/bin/env python3
"""
查询和分析K线数据示例
演示如何使用收集的K线数据进行分析
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import text
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.db_manager import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def get_token_ohlcv(
    db: DatabaseManager,
    symbol: str = None,
    token_id: str = None,
    limit: int = 100
) -> pd.DataFrame:
    """
    获取代币的K线数据

    Args:
        db: 数据库管理器
        symbol: 代币符号
        token_id: 代币ID
        limit: 返回的K线数量

    Returns:
        DataFrame with OHLCV data
    """
    async with db.get_session() as session:
        query = """
            SELECT
                o.timestamp,
                o.open,
                o.high,
                o.low,
                o.close,
                o.volume,
                o.timeframe,
                t.symbol,
                t.name
            FROM token_ohlcv o
            JOIN tokens t ON o.token_id = t.id
            WHERE 1=1
        """

        params = {}

        if token_id:
            query += " AND t.id = :token_id"
            params["token_id"] = token_id
        elif symbol:
            query += " AND t.symbol = :symbol"
            params["symbol"] = symbol
        else:
            raise ValueError("Must provide either symbol or token_id")

        query += " ORDER BY o.timestamp DESC LIMIT :limit"
        params["limit"] = limit

        result = await session.execute(text(query), params)
        rows = result.fetchall()

        if not rows:
            logger.warning(f"No OHLCV data found for {symbol or token_id}")
            return pd.DataFrame()

        # 转换为DataFrame
        df = pd.DataFrame(rows, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'timeframe', 'symbol', 'name'
        ])

        # 转换数据类型
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        # 按时间排序
        df = df.sort_values('timestamp').reset_index(drop=True)

        return df


async def get_all_dexscreener_tokens(db: DatabaseManager) -> List[Dict[str, Any]]:
    """获取所有DexScreener代币列表"""
    async with db.get_session() as session:
        result = await session.execute(text("""
            SELECT
                t.id,
                t.symbol,
                t.name,
                COUNT(o.id) as candle_count,
                MIN(o.timestamp) as earliest,
                MAX(o.timestamp) as latest,
                array_agg(DISTINCT o.timeframe ORDER BY o.timeframe) as timeframes
            FROM tokens t
            LEFT JOIN token_ohlcv o ON t.id = o.token_id
            WHERE t.data_source = 'dexscreener'
            GROUP BY t.id, t.symbol, t.name
            HAVING COUNT(o.id) > 0
            ORDER BY COUNT(o.id) DESC
        """))

        tokens = []
        for row in result:
            tokens.append({
                'id': row[0],
                'symbol': row[1],
                'name': row[2],
                'candle_count': row[3],
                'earliest': row[4],
                'latest': row[5],
                'timeframes': row[6]
            })

        return tokens


async def calculate_price_change(df: pd.DataFrame) -> Dict[str, float]:
    """计算价格变化统计"""
    if len(df) == 0:
        return {}

    first_price = df.iloc[0]['close']
    last_price = df.iloc[-1]['close']
    max_price = df['high'].max()
    min_price = df['low'].min()

    price_change = last_price - first_price
    price_change_pct = (price_change / first_price * 100) if first_price > 0 else 0

    return {
        'first_price': float(first_price),
        'last_price': float(last_price),
        'max_price': float(max_price),
        'min_price': float(min_price),
        'price_change': float(price_change),
        'price_change_pct': float(price_change_pct),
        'volatility': float((max_price - min_price) / first_price * 100) if first_price > 0 else 0
    }


async def example1_list_tokens():
    """示例1: 列出所有有K线数据的DexScreener代币"""
    print("\n" + "=" * 80)
    print("示例 1: 列出所有DexScreener代币及其K线数据")
    print("=" * 80)

    db = DatabaseManager()
    await db.init_async_db()

    try:
        tokens = await get_all_dexscreener_tokens(db)

        print(f"\n找到 {len(tokens)} 个有K线数据的代币:\n")

        for i, token in enumerate(tokens[:10], 1):  # 只显示前10个
            print(f"{i}. {token['symbol']:>10} - {token['name']}")
            print(f"   K线数量: {token['candle_count']}")
            print(f"   时间周期: {', '.join(token['timeframes'])}")
            print(f"   时间范围: {token['earliest']} 至 {token['latest']}")
            print()

        if len(tokens) > 10:
            print(f"... 还有 {len(tokens) - 10} 个代币\n")

    finally:
        await db.close()


async def example2_query_ohlcv():
    """示例2: 查询特定代币的K线数据"""
    print("\n" + "=" * 80)
    print("示例 2: 查询代币K线数据")
    print("=" * 80)

    db = DatabaseManager()
    await db.init_async_db()

    try:
        # 查询COAI代币的K线
        symbol = "COAI"
        print(f"\n查询 {symbol} 的K线数据...\n")

        df = await get_token_ohlcv(db, symbol=symbol, limit=100)

        if len(df) > 0:
            print(f"获取到 {len(df)} 根K线")
            print(f"时间周期: {df['timeframe'].iloc[0]}")
            print(f"时间范围: {df['timestamp'].min()} 至 {df['timestamp'].max()}")
            print(f"\n最近5根K线:")
            print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(5).to_string(index=False))
        else:
            print(f"未找到 {symbol} 的K线数据")

    finally:
        await db.close()


async def example3_price_analysis():
    """示例3: 价格分析"""
    print("\n" + "=" * 80)
    print("示例 3: 价格变化分析")
    print("=" * 80)

    db = DatabaseManager()
    await db.init_async_db()

    try:
        # 分析多个代币
        symbols = ["COAI", "修仙", "GIGGLE"]

        for symbol in symbols:
            print(f"\n分析 {symbol}:")

            df = await get_token_ohlcv(db, symbol=symbol, limit=200)

            if len(df) > 0:
                stats = await calculate_price_change(df)

                print(f"  K线数量: {len(df)}")
                print(f"  时间周期: {df['timeframe'].iloc[0]}")
                print(f"  起始价格: ${stats['first_price']:.8f}")
                print(f"  最新价格: ${stats['last_price']:.8f}")
                print(f"  价格变化: {stats['price_change_pct']:+.2f}%")
                print(f"  最高价格: ${stats['max_price']:.8f}")
                print(f"  最低价格: ${stats['min_price']:.8f}")
                print(f"  波动率: {stats['volatility']:.2f}%")
            else:
                print(f"  未找到数据")

    finally:
        await db.close()


async def example4_volume_analysis():
    """示例4: 交易量分析"""
    print("\n" + "=" * 80)
    print("示例 4: 交易量分析")
    print("=" * 80)

    db = DatabaseManager()
    await db.init_async_db()

    try:
        symbol = "COAI"
        print(f"\n分析 {symbol} 的交易量:\n")

        df = await get_token_ohlcv(db, symbol=symbol, limit=100)

        if len(df) > 0:
            total_volume = df['volume'].sum()
            avg_volume = df['volume'].mean()
            max_volume = df['volume'].max()
            max_volume_time = df.loc[df['volume'].idxmax(), 'timestamp']

            print(f"总交易量: {total_volume:,.2f}")
            print(f"平均交易量: {avg_volume:,.2f}")
            print(f"最大交易量: {max_volume:,.2f}")
            print(f"最大交易量时间: {max_volume_time}")

            # 按小时统计（如果数据足够）
            if len(df) > 24:
                df['hour'] = df['timestamp'].dt.hour
                hourly_volume = df.groupby('hour')['volume'].sum().sort_values(ascending=False)

                print(f"\n交易量最大的3个小时:")
                for hour, vol in hourly_volume.head(3).items():
                    print(f"  {hour:02d}:00 - {vol:,.2f}")

    finally:
        await db.close()


async def example5_recent_tokens():
    """示例5: 查看最近的代币"""
    print("\n" + "=" * 80)
    print("示例 5: 最近活跃的代币")
    print("=" * 80)

    db = DatabaseManager()
    await db.init_async_db()

    try:
        async with db.get_session() as session:
            # 查询最近有交易的代币
            result = await session.execute(text("""
                SELECT
                    t.symbol,
                    t.name,
                    MAX(o.timestamp) as last_candle,
                    COUNT(*) as candle_count,
                    o.timeframe
                FROM token_ohlcv o
                JOIN tokens t ON o.token_id = t.id
                WHERE t.data_source = 'dexscreener'
                GROUP BY t.symbol, t.name, o.timeframe
                ORDER BY MAX(o.timestamp) DESC
                LIMIT 10
            """))

            print("\n最近更新的10个代币:\n")
            for i, row in enumerate(result, 1):
                symbol, name, last_candle, count, timeframe = row
                print(f"{i}. {symbol:>10} ({name})")
                print(f"   最新K线: {last_candle}")
                print(f"   时间周期: {timeframe}")
                print(f"   K线数量: {count}")
                print()

    finally:
        await db.close()


async def main():
    """主函数"""
    examples = {
        "1": ("列出所有代币", example1_list_tokens),
        "2": ("查询K线数据", example2_query_ohlcv),
        "3": ("价格变化分析", example3_price_analysis),
        "4": ("交易量分析", example4_volume_analysis),
        "5": ("最近活跃代币", example5_recent_tokens),
    }

    print("\n" + "=" * 80)
    print("K线数据查询示例")
    print("=" * 80)

    print("\n可用示例:")
    for key, (desc, _) in examples.items():
        print(f"  {key}. {desc}")
    print("  0. 运行所有示例")
    print("  q. 退出")

    choice = input("\n请选择示例 (1-5, 0, q): ").strip()

    if choice == 'q':
        print("\n再见!")
        return

    if choice == '0':
        # 运行所有示例
        for key, (desc, func) in examples.items():
            try:
                await func()
                print("\n" + "-" * 80)
            except Exception as e:
                print(f"\n✗ 示例 {key} 失败: {e}")
                import traceback
                traceback.print_exc()
    elif choice in examples:
        # 运行单个示例
        desc, func = examples[choice]
        try:
            await func()
        except Exception as e:
            print(f"\n✗ 示例失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"\n✗ 无效选择: {choice}")


if __name__ == "__main__":
    asyncio.run(main())
