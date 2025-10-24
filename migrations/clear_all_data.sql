-- ============================================
-- 清空所有表数据（保留表结构）
-- 警告：此操作不可逆，请谨慎使用！
-- ============================================

-- 临时禁用外键约束
SET session_replication_role = 'replica';

-- 清空所有表数据
TRUNCATE TABLE price_alerts RESTART IDENTITY CASCADE;
TRUNCATE TABLE monitored_tokens RESTART IDENTITY CASCADE;
TRUNCATE TABLE potential_tokens RESTART IDENTITY CASCADE;
TRUNCATE TABLE wallet_transactions RESTART IDENTITY CASCADE;
TRUNCATE TABLE early_trades RESTART IDENTITY CASCADE;
TRUNCATE TABLE tokens RESTART IDENTITY CASCADE;

-- 重新启用外键约束
SET session_replication_role = 'origin';

-- 显示清空结果
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

COMMENT ON SCHEMA public IS '所有表数据已清空';
