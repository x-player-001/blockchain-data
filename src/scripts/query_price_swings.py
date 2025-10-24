#!/usr/bin/env python3
"""
查询价格波动数据的辅助脚本
提供各种有用的查询示例
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.db_manager import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def get_token_swings(db: DatabaseManager, symbol: str = None, token_id: str = None):
    """
    获取特定代币的所有波动记录

    Args:
        db: 数据库管理器
        symbol: 代币符号
        token_id: 代币ID
    """
    async with db.get_session() as session:
        if symbol:
            query = """
                SELECT
                    ps.swing_type,
                    ps.swing_pct,
                    ps.start_time,
                    ps.end_time,
                    ps.duration_hours,
                    ps.start_price,
                    ps.end_price,
                    ps.timeframe,
                    d.base_token_symbol,
                    d.base_token_name
                FROM price_swings ps
                JOIN dexscreener_tokens d ON ps.token_id = d.id
                WHERE d.base_token_symbol = :symbol
                ORDER BY ps.start_time ASC
            """
            result = await session.execute(text(query), {"symbol": symbol})
        elif token_id:
            query = """
                SELECT
                    ps.swing_type,
                    ps.swing_pct,
                    ps.start_time,
                    ps.end_time,
                    ps.duration_hours,
                    ps.start_price,
                    ps.end_price,
                    ps.timeframe,
                    d.base_token_symbol,
                    d.base_token_name
                FROM price_swings ps
                JOIN dexscreener_tokens d ON ps.token_id = d.id
                WHERE ps.token_id = :token_id
                ORDER BY ps.start_time ASC
            """
            result = await session.execute(text(query), {"token_id": token_id})
        else:
            raise ValueError("Must provide either symbol or token_id")

        rows = result.fetchall()
        return rows


async def get_largest_rises(db: DatabaseManager, limit: int = 10):
    """
    获取最大的涨幅记录

    Args:
        db: 数据库管理器
        limit: 返回数量
    """
    async with db.get_session() as session:
        query = """
            SELECT
                d.base_token_symbol,
                d.base_token_name,
                ps.swing_pct,
                ps.start_time,
                ps.end_time,
                ps.duration_hours,
                ps.start_price,
                ps.end_price
            FROM price_swings ps
            JOIN dexscreener_tokens d ON ps.token_id = d.id
            WHERE ps.swing_type = 'rise'
            ORDER BY ps.swing_pct DESC
            LIMIT :limit
        """
        result = await session.execute(text(query), {"limit": limit})
        rows = result.fetchall()
        return rows


async def get_largest_falls(db: DatabaseManager, limit: int = 10):
    """
    获取最大的跌幅记录

    Args:
        db: 数据库管理器
        limit: 返回数量
    """
    async with db.get_session() as session:
        query = """
            SELECT
                d.base_token_symbol,
                d.base_token_name,
                ps.swing_pct,
                ps.start_time,
                ps.end_time,
                ps.duration_hours,
                ps.start_price,
                ps.end_price
            FROM price_swings ps
            JOIN dexscreener_tokens d ON ps.token_id = d.id
            WHERE ps.swing_type = 'fall'
            ORDER BY ps.swing_pct ASC
            LIMIT :limit
        """
        result = await session.execute(text(query), {"limit": limit})
        rows = result.fetchall()
        return rows


async def get_token_swing_stats(db: DatabaseManager):
    """
    获取每个代币的波动统计

    Args:
        db: 数据库管理器
    """
    async with db.get_session() as session:
        query = """
            SELECT
                d.base_token_symbol,
                d.base_token_name,
                COUNT(*) as total_swings,
                COUNT(CASE WHEN ps.swing_type = 'rise' THEN 1 END) as rises,
                COUNT(CASE WHEN ps.swing_type = 'fall' THEN 1 END) as falls,
                MAX(CASE WHEN ps.swing_type = 'rise' THEN ps.swing_pct END) as max_rise,
                MIN(CASE WHEN ps.swing_type = 'fall' THEN ps.swing_pct END) as max_fall,
                AVG(ps.duration_hours) as avg_duration
            FROM price_swings ps
            JOIN dexscreener_tokens d ON ps.token_id = d.id
            GROUP BY d.base_token_symbol, d.base_token_name
            ORDER BY total_swings DESC
        """
        result = await session.execute(text(query))
        rows = result.fetchall()
        return rows


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='查询价格波动数据')
    parser.add_argument('--symbol', type=str, help='查询特定代币的波动')
    parser.add_argument('--top-rises', type=int, help='查询最大涨幅TOP N')
    parser.add_argument('--top-falls', type=int, help='查询最大跌幅TOP N')
    parser.add_argument('--stats', action='store_true', help='显示所有代币的波动统计')

    args = parser.parse_args()

    db = DatabaseManager()
    await db.init_async_db()

    try:
        if args.symbol:
            # 查询特定代币
            rows = await get_token_swings(db, symbol=args.symbol)
            if not rows:
                logger.warning(f"未找到 {args.symbol} 的波动记录")
                return

            print(f"\n{args.symbol} 的价格波动记录:")
            print("=" * 120)
            for row in rows:
                swing_type, swing_pct, start_time, end_time, duration, start_price, end_price, timeframe, symbol, name = row
                direction = "上涨" if swing_type == 'rise' else "下跌"
                print(f"{direction} {abs(swing_pct):.2f}% | "
                      f"{start_time.strftime('%Y-%m-%d %H:%M')} → {end_time.strftime('%Y-%m-%d %H:%M')} | "
                      f"${start_price:.8f} → ${end_price:.8f} | "
                      f"{duration:.1f}h")
            print("=" * 120)

        elif args.top_rises:
            # 查询最大涨幅
            rows = await get_largest_rises(db, limit=args.top_rises)
            print(f"\n最大涨幅 TOP {args.top_rises}:")
            print("=" * 120)
            print(f"{'排名':<5} {'代币':<12} {'涨幅':<12} {'起始时间':<20} {'结束时间':<20} {'持续(h)':<10}")
            print("-" * 120)
            for i, row in enumerate(rows, 1):
                symbol, name, swing_pct, start_time, end_time, duration, start_price, end_price = row
                print(f"{i:<5} {symbol:<12} {swing_pct:>10.2f}% "
                      f"{start_time.strftime('%Y-%m-%d %H:%M'):<20} "
                      f"{end_time.strftime('%Y-%m-%d %H:%M'):<20} "
                      f"{duration:>8.1f}")
            print("=" * 120)

        elif args.top_falls:
            # 查询最大跌幅
            rows = await get_largest_falls(db, limit=args.top_falls)
            print(f"\n最大跌幅 TOP {args.top_falls}:")
            print("=" * 120)
            print(f"{'排名':<5} {'代币':<12} {'跌幅':<12} {'起始时间':<20} {'结束时间':<20} {'持续(h)':<10}")
            print("-" * 120)
            for i, row in enumerate(rows, 1):
                symbol, name, swing_pct, start_time, end_time, duration, start_price, end_price = row
                print(f"{i:<5} {symbol:<12} {swing_pct:>10.2f}% "
                      f"{start_time.strftime('%Y-%m-%d %H:%M'):<20} "
                      f"{end_time.strftime('%Y-%m-%d %H:%M'):<20} "
                      f"{duration:>8.1f}")
            print("=" * 120)

        elif args.stats:
            # 显示统计信息
            rows = await get_token_swing_stats(db)
            print("\n所有代币波动统计:")
            print("=" * 120)
            print(f"{'代币':<12} {'总波动':<8} {'上涨':<6} {'下跌':<6} {'最大涨幅':<12} {'最大跌幅':<12} {'平均时长(h)':<12}")
            print("-" * 120)
            for row in rows:
                symbol, name, total, rises, falls, max_rise, max_fall, avg_duration = row
                print(f"{symbol:<12} {total:>7} {rises:>6} {falls:>6} "
                      f"{max_rise if max_rise else 0:>11.2f}% "
                      f"{max_fall if max_fall else 0:>11.2f}% "
                      f"{avg_duration if avg_duration else 0:>11.1f}")
            print("=" * 120)

        else:
            parser.print_help()

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
