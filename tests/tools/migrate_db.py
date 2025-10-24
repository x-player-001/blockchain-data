#!/usr/bin/env python3
"""
数据库迁移脚本
应用新的表结构变更，添加AVE API相关字段
"""

import asyncio
from sqlalchemy import text, inspect
from src.storage.db_manager import DatabaseManager
from src.storage.models import Base


def _inspect_tables(conn):
    """同步函数：检查表结构"""
    inspector = inspect(conn)
    table_names = inspector.get_table_names()
    columns = {}
    if 'monitored_tokens' in table_names:
        columns = {col['name'] for col in inspector.get_columns('monitored_tokens')}
    return table_names, columns


async def apply_migration():
    """应用数据库迁移"""
    print("\n" + "="*80)
    print("数据库迁移 - 添加AVE API字段到MonitoredToken表")
    print("="*80 + "\n")

    db_manager = DatabaseManager()
    await db_manager.init_async_db()

    # 使用async_engine的connection来检查表结构
    async with db_manager.async_engine.connect() as conn:
        # 获取当前表结构
        table_names, existing_columns = await conn.run_sync(_inspect_tables)

        # 检查monitored_tokens表是否存在
        if 'monitored_tokens' in table_names:
            print("✓ monitored_tokens表已存在")

            # 需要添加的新列及其定义
            new_columns = {
                'amm': 'VARCHAR(50)',
                'price_ath_usd': 'NUMERIC(30, 18)',
                'current_tvl': 'NUMERIC(30, 2)',
                'current_market_cap': 'NUMERIC(30, 2)',
                'price_change_1m': 'NUMERIC(10, 2)',
                'price_change_5m': 'NUMERIC(10, 2)',
                'price_change_15m': 'NUMERIC(10, 2)',
                'price_change_30m': 'NUMERIC(10, 2)',
                'price_change_1h': 'NUMERIC(10, 2)',
                'price_change_4h': 'NUMERIC(10, 2)',
                'price_change_24h': 'NUMERIC(10, 2)',
                'volume_1m': 'NUMERIC(30, 2)',
                'volume_5m': 'NUMERIC(30, 2)',
                'volume_15m': 'NUMERIC(30, 2)',
                'volume_30m': 'NUMERIC(30, 2)',
                'volume_1h': 'NUMERIC(30, 2)',
                'volume_4h': 'NUMERIC(30, 2)',
                'volume_24h': 'NUMERIC(30, 2)',
                'tx_count_1m': 'INTEGER',
                'tx_count_5m': 'INTEGER',
                'tx_count_15m': 'INTEGER',
                'tx_count_30m': 'INTEGER',
                'tx_count_1h': 'INTEGER',
                'tx_count_4h': 'INTEGER',
                'tx_count_24h': 'INTEGER',
                'buys_24h': 'INTEGER',
                'sells_24h': 'INTEGER',
                'makers_24h': 'INTEGER',
                'buyers_24h': 'INTEGER',
                'sellers_24h': 'INTEGER',
                'price_24h_high': 'NUMERIC(30, 18)',
                'price_24h_low': 'NUMERIC(30, 18)',
                'open_price_24h': 'NUMERIC(30, 18)',
                'token_created_at': 'TIMESTAMP',
                'first_trade_at': 'TIMESTAMP',
                'creation_block_number': 'BIGINT',
                'creation_tx_hash': 'VARCHAR(66)',
                'lp_holders': 'INTEGER',
                'lp_locked_percent': 'NUMERIC(5, 2)',
                'lp_lock_platform': 'VARCHAR(100)',
                'rusher_tx_count': 'INTEGER',
                'sniper_tx_count': 'INTEGER',
            }

            # 找出需要添加的列
            columns_to_add = {col: dtype for col, dtype in new_columns.items() if col not in existing_columns}

            if columns_to_add:
                print(f"\n需要添加 {len(columns_to_add)} 个新字段:\n")

                # 开启事务来添加列
                async with db_manager.async_engine.begin() as trans_conn:
                    for i, (col_name, col_type) in enumerate(columns_to_add.items(), 1):
                        try:
                            alter_sql = f"ALTER TABLE monitored_tokens ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                            await trans_conn.execute(text(alter_sql))
                            print(f"  {i}. {col_name:30s} {col_type:20s} ✓")
                        except Exception as e:
                            print(f"  {i}. {col_name:30s} {col_type:20s} ✗ ({e})")

                print(f"\n✓ 成功添加 {len(columns_to_add)} 个字段")
            else:
                print("\n所有字段已存在，无需添加")
        else:
            # 表不存在，创建所有表
            print("monitored_tokens表不存在，创建所有表...")

            async with db_manager.async_engine.begin() as conn_create:
                await conn_create.run_sync(Base.metadata.create_all)

            print("✓ 所有表创建完成")

    await db_manager.close()

    print("\n" + "="*80)
    print("迁移完成")
    print("="*80 + "\n")


if __name__ == '__main__':
    asyncio.run(apply_migration())
