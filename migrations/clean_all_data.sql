-- ============================================
-- 清空数据库脚本
-- 清空所有历史数据，但保留表结构和配置
-- ============================================

BEGIN;

-- 1. 清空价格报警表
DELETE FROM price_alerts;
SELECT '✓ 已清空 price_alerts 表' as status;

-- 2. 清空监控代币表
DELETE FROM monitored_tokens;
SELECT '✓ 已清空 monitored_tokens 表' as status;

-- 3. 清空潜力代币表
DELETE FROM potential_tokens;
SELECT '✓ 已清空 potential_tokens 表' as status;

-- 4. 清空 DexScreener 代币表（如果存在）
DELETE FROM dexscreener_tokens;
SELECT '✓ 已清空 dexscreener_tokens 表' as status;

-- 5. 不清空 scraper_config 表（保留配置）
-- DELETE FROM scraper_config;  -- 保留配置数据

COMMIT;

-- 显示清空结果
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '================================================';
    RAISE NOTICE '数据清空完成！';
    RAISE NOTICE '================================================';
    RAISE NOTICE '✓ price_alerts 已清空';
    RAISE NOTICE '✓ monitored_tokens 已清空';
    RAISE NOTICE '✓ potential_tokens 已清空';
    RAISE NOTICE '✓ dexscreener_tokens 已清空';
    RAISE NOTICE '✓ scraper_config 保留（未清空）';
    RAISE NOTICE '================================================';
END $$;
