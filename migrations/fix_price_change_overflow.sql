-- ============================================
-- 修复 price_change 字段溢出问题
-- 将 NUMERIC(10, 2) 扩展为 NUMERIC(20, 2)
-- ============================================

BEGIN;

-- 1. PotentialToken 表
ALTER TABLE potential_tokens
    ALTER COLUMN price_change_1m TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_5m TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_15m TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_30m TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_1h TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_4h TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_24h TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_24h_at_scrape TYPE NUMERIC(20, 2);

SELECT '✓ PotentialToken 表字段已更新' as status;

-- 2. MonitoredToken 表
ALTER TABLE monitored_tokens
    ALTER COLUMN price_change_1m TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_5m TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_15m TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_30m TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_1h TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_4h TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_24h TYPE NUMERIC(20, 2),
    ALTER COLUMN price_change_24h_at_entry TYPE NUMERIC(20, 2);

SELECT '✓ MonitoredToken 表字段已更新' as status;

-- 3. Token 表
ALTER TABLE tokens
    ALTER COLUMN price_change_24h TYPE NUMERIC(20, 2);

SELECT '✓ Token 表字段已更新' as status;

-- 4. DexScreenerToken 表（如果存在）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'dexscreener_tokens') THEN
        ALTER TABLE dexscreener_tokens
            ALTER COLUMN price_change_h1 TYPE NUMERIC(20, 2),
            ALTER COLUMN price_change_h6 TYPE NUMERIC(20, 2),
            ALTER COLUMN price_change_h24 TYPE NUMERIC(20, 2);
        RAISE NOTICE '✓ DexScreenerToken 表字段已更新';
    ELSE
        RAISE NOTICE 'ℹ DexScreenerToken 表不存在，跳过';
    END IF;
END $$;

COMMIT;

-- 显示更新结果
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '================================================';
    RAISE NOTICE '字段精度更新完成！';
    RAISE NOTICE '================================================';
    RAISE NOTICE '变更：NUMERIC(10, 2) → NUMERIC(20, 2)';
    RAISE NOTICE '';
    RAISE NOTICE '更新的表：';
    RAISE NOTICE '  ✓ potential_tokens (8个字段)';
    RAISE NOTICE '  ✓ monitored_tokens (8个字段)';
    RAISE NOTICE '  ✓ tokens (1个字段)';
    RAISE NOTICE '  ✓ dexscreener_tokens (3个字段)';
    RAISE NOTICE '';
    RAISE NOTICE '新的最大值: 99,999,999,999,999,999.99';
    RAISE NOTICE '================================================';
END $$;
