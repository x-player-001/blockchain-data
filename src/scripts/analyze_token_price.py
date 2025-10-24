#!/usr/bin/env python3
"""
代币价格分析脚本
分析K线数据，找出高低点、大幅波动等
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional
from sqlalchemy import text
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.db_manager import DatabaseManager
from src.analysis.ohlcv_analyzer import OHLCVAnalyzer
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def get_token_ohlcv(
    db: DatabaseManager,
    symbol: str = None,
    token_id: str = None,
    limit: Optional[int] = None
) -> pd.DataFrame:
    """
    获取代币的K线数据

    Args:
        db: 数据库管理器
        symbol: 代币符号
        token_id: 代币ID
        limit: 限制K线数量

    Returns:
        K线数据DataFrame
    """
    async with db.get_session() as session:
        # 构建查询
        if token_id:
            query = """
                SELECT
                    o.timestamp,
                    o.open,
                    o.high,
                    o.low,
                    o.close,
                    o.volume,
                    o.timeframe,
                    d.base_token_symbol as symbol,
                    d.base_token_name as name
                FROM token_ohlcv o
                JOIN dexscreener_tokens d ON o.token_id = d.id
                WHERE d.id = :token_id
                ORDER BY o.timestamp ASC
            """
            params = {"token_id": token_id}
        elif symbol:
            query = """
                SELECT
                    o.timestamp,
                    o.open,
                    o.high,
                    o.low,
                    o.close,
                    o.volume,
                    o.timeframe,
                    d.base_token_symbol as symbol,
                    d.base_token_name as name
                FROM token_ohlcv o
                JOIN dexscreener_tokens d ON o.token_id = d.id
                WHERE d.base_token_symbol = :symbol
                ORDER BY o.timestamp ASC
            """
            params = {"symbol": symbol}
        else:
            raise ValueError("Must provide either symbol or token_id")

        if limit:
            query += f" LIMIT :limit"
            params["limit"] = limit

        result = await session.execute(text(query), params)
        rows = result.fetchall()

        if not rows:
            logger.warning(f"未找到K线数据: {symbol or token_id}")
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

        return df


async def analyze_token(
    symbol: str = None,
    token_id: str = None,
    min_swing_pct: float = 50.0,
    limit: Optional[int] = None,
    save_to_db: bool = True
):
    """
    分析代币价格

    Args:
        symbol: 代币符号
        token_id: 代币ID
        min_swing_pct: 最小波动幅度（百分比）
        limit: 限制K线数量
        save_to_db: 是否保存分析结果到数据库
    """
    db = DatabaseManager()
    await db.init_async_db()

    try:
        # 获取K线数据
        logger.info(f"正在获取 {symbol or token_id} 的K线数据...")
        df = await get_token_ohlcv(db, symbol=symbol, token_id=token_id, limit=limit)

        if df.empty:
            logger.error("未找到K线数据")
            return

        token_symbol = df.iloc[0]['symbol']
        token_name = df.iloc[0]['name']
        timeframe = df.iloc[0]['timeframe']

        # 获取token_id（如果通过symbol查询）
        if symbol and not token_id:
            async with db.get_session() as session:
                result = await session.execute(
                    text("SELECT id FROM dexscreener_tokens WHERE base_token_symbol = :symbol"),
                    {"symbol": symbol}
                )
                token_id = result.scalar()

        logger.info(f"找到 {len(df)} 根K线 ({token_symbol} - {token_name}, 时间周期: {timeframe})")

        # 创建分析器
        analyzer = OHLCVAnalyzer(min_swing_pct=min_swing_pct)

        # 分析数据
        logger.info("正在分析价格数据...")
        analysis = analyzer.analyze(df)

        # 保存到数据库
        if save_to_db and analysis.large_swings:
            async with db.get_session() as session:
                saved_count = await analyzer.save_swings_to_db(
                    session=session,
                    token_id=token_id,
                    swings=analysis.large_swings,
                    timeframe=timeframe
                )
                logger.info(f"保存了 {saved_count} 条波动记录到数据库")

        # 输出分析结果
        print("\n" + "=" * 80)
        print(f"代币: {token_symbol} ({token_name})")
        print(f"时间周期: {timeframe}")
        print(str(analysis))

        # 输出详细波动信息
        if analysis.large_swings:
            print(analyzer.get_swing_summary(analysis))

        # 输出统计摘要
        print("\n" + "=" * 80)
        print("关键指标:")
        print(f"  • 共有 {analysis.large_swings_count} 次大幅波动 (>{min_swing_pct}%)")

        if analysis.max_rise:
            print(f"  • 最大涨幅: {analysis.max_rise.swing_pct:.2f}%")

        if analysis.max_fall:
            print(f"  • 最大跌幅: {analysis.max_fall.swing_pct:.2f}%")

        print(f"  • 当前距离最高点: {abs(analysis.current_from_high_pct):.2f}%")
        print(f"  • 需要涨 {analysis.to_ath_multiplier:.2f} 倍才能回到最高点")
        print("=" * 80)

    finally:
        await db.close()


async def analyze_all_tokens(min_swing_pct: float = 50.0, min_liquidity: float = 0, save_to_db: bool = True):
    """
    分析所有代币

    Args:
        min_swing_pct: 最小波动幅度
        min_liquidity: 最小流动性过滤
        save_to_db: 是否保存分析结果到数据库
    """
    db = DatabaseManager()
    await db.init_async_db()

    try:
        # 获取所有有K线数据的代币
        async with db.get_session() as session:
            query = """
                SELECT DISTINCT
                    d.id,
                    d.base_token_symbol,
                    d.base_token_name,
                    d.liquidity_usd,
                    COUNT(o.id) as candle_count
                FROM dexscreener_tokens d
                JOIN token_ohlcv o ON d.id = o.token_id
                WHERE d.liquidity_usd >= :min_liquidity
                GROUP BY d.id, d.base_token_symbol, d.base_token_name, d.liquidity_usd
                HAVING COUNT(o.id) > 0
                ORDER BY d.liquidity_usd DESC
            """
            result = await session.execute(text(query), {"min_liquidity": min_liquidity})
            tokens = result.fetchall()

        logger.info(f"找到 {len(tokens)} 个有K线数据的代币")

        # 分析每个代币
        analyzer = OHLCVAnalyzer(min_swing_pct=min_swing_pct)
        results = []
        total_swings_saved = 0

        for token_id, symbol, name, liquidity, candle_count in tokens:
            try:
                df = await get_token_ohlcv(db, token_id=token_id)
                if df.empty:
                    continue

                analysis = analyzer.analyze(df)
                timeframe = df.iloc[0]['timeframe'] if not df.empty else None

                # 保存到数据库
                if save_to_db and analysis.large_swings:
                    async with db.get_session() as session:
                        saved_count = await analyzer.save_swings_to_db(
                            session=session,
                            token_id=token_id,
                            swings=analysis.large_swings,
                            timeframe=timeframe
                        )
                        total_swings_saved += saved_count
                        logger.info(f"{symbol}: 保存了 {saved_count} 条波动记录")

                results.append({
                    'symbol': symbol,
                    'name': name,
                    'liquidity': liquidity,
                    'candles': candle_count,
                    'large_swings': analysis.large_swings_count,
                    'max_rise': analysis.max_rise.swing_pct if analysis.max_rise else 0,
                    'max_fall': analysis.max_fall.swing_pct if analysis.max_fall else 0,
                    'from_ath': analysis.current_from_high_pct,
                    'to_ath_mult': analysis.to_ath_multiplier,
                    'current_price': analysis.current_price,
                    'highest_price': analysis.highest_price
                })

            except Exception as e:
                logger.error(f"分析 {symbol} 失败: {e}")
                continue

        # 输出汇总结果
        print("\n" + "=" * 120)
        print("所有代币分析汇总")
        print("=" * 120)
        print(f"{'代币':<12} {'流动性($)':<15} {'K线数':<8} {'大幅波动':<10} {'最大涨幅':<12} {'最大跌幅':<12} {'距ATH':<12} {'到ATH倍数':<12}")
        print("-" * 120)

        for r in results:
            print(f"{r['symbol']:<12} {r['liquidity']:>14,.2f} {r['candles']:>8} {r['large_swings']:>10} "
                  f"{r['max_rise']:>11.2f}% {r['max_fall']:>11.2f}% {abs(r['from_ath']):>11.2f}% {r['to_ath_mult']:>11.2f}x")

        print("=" * 120)

        if save_to_db:
            logger.info(f"\n总共保存了 {total_swings_saved} 条波动记录到数据库")

    finally:
        await db.close()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='代币价格分析工具')
    parser.add_argument('--symbol', type=str, help='代币符号')
    parser.add_argument('--token-id', type=str, help='代币ID')
    parser.add_argument('--all', action='store_true', help='分析所有代币')
    parser.add_argument('--min-swing', type=float, default=50.0, help='最小波动幅度（百分比），默认50')
    parser.add_argument('--min-liquidity', type=float, default=0, help='最小流动性过滤（USD）')
    parser.add_argument('--limit', type=int, help='限制K线数量')
    parser.add_argument('--no-save', action='store_true', help='不保存分析结果到数据库')

    args = parser.parse_args()

    save_to_db = not args.no_save

    if args.all:
        # 分析所有代币
        await analyze_all_tokens(
            min_swing_pct=args.min_swing,
            min_liquidity=args.min_liquidity,
            save_to_db=save_to_db
        )
    elif args.symbol or args.token_id:
        # 分析单个代币
        await analyze_token(
            symbol=args.symbol,
            token_id=args.token_id,
            min_swing_pct=args.min_swing,
            limit=args.limit,
            save_to_db=save_to_db
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
