-- =====================================================
-- 数据库迁移脚本 - 监控功能增强
-- 版本: 2025-10-27
-- 说明: 添加监控配置、监控日志、爬虫日志相关表和字段
-- =====================================================

-- 开始事务
BEGIN;

-- =====================================================
-- 1. 扩展 scraper_config 表 - 添加过滤条件字段
-- =====================================================
ALTER TABLE scraper_config ADD COLUMN IF NOT EXISTS min_market_cap NUMERIC(20, 2) DEFAULT NULL;
ALTER TABLE scraper_config ADD COLUMN IF NOT EXISTS min_liquidity NUMERIC(20, 2) DEFAULT NULL;
ALTER TABLE scraper_config ADD COLUMN IF NOT EXISTS max_token_age_days INTEGER DEFAULT NULL;

-- =====================================================
-- 2. 创建 scrape_logs 表 - 记录爬虫执行日志
-- =====================================================
CREATE TABLE IF NOT EXISTS scrape_logs (
    id VARCHAR(36) PRIMARY KEY,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    chain VARCHAR(20),
    tokens_scraped INTEGER,
    tokens_filtered INTEGER,
    tokens_saved INTEGER,
    tokens_skipped INTEGER,
    filtered_by_market_cap INTEGER DEFAULT 0,
    filtered_by_liquidity INTEGER DEFAULT 0,
    filtered_by_age INTEGER DEFAULT 0,
    error_message VARCHAR(1000),
    config_snapshot JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_scrape_logs_started_at ON scrape_logs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scrape_logs_status ON scrape_logs(status);
CREATE INDEX IF NOT EXISTS idx_scrape_logs_chain ON scrape_logs(chain);

-- =====================================================
-- 3. 扩展 monitored_tokens 表 - 添加删除原因跟踪
-- =====================================================
ALTER TABLE monitored_tokens ADD COLUMN IF NOT EXISTS removal_reason VARCHAR(50) DEFAULT NULL;
ALTER TABLE monitored_tokens ADD COLUMN IF NOT EXISTS removal_threshold_value NUMERIC(30, 2) DEFAULT NULL;

-- =====================================================
-- 4. 创建 monitor_config 表 - 监控配置
-- =====================================================
CREATE TABLE IF NOT EXISTS monitor_config (
    id VARCHAR(36) PRIMARY KEY,
    min_monitor_market_cap NUMERIC(20, 2) DEFAULT NULL,
    min_monitor_liquidity NUMERIC(20, 2) DEFAULT NULL,
    update_interval_minutes INTEGER NOT NULL DEFAULT 5,
    enabled INTEGER NOT NULL DEFAULT 1,
    max_retry_count INTEGER NOT NULL DEFAULT 3,
    batch_size INTEGER NOT NULL DEFAULT 10,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认配置（如果不存在）
INSERT INTO monitor_config (id, min_monitor_market_cap, min_monitor_liquidity, update_interval_minutes, enabled)
SELECT
    gen_random_uuid()::text,
    NULL,
    NULL,
    5,
    1
WHERE NOT EXISTS (SELECT 1 FROM monitor_config LIMIT 1);

-- =====================================================
-- 5. 创建 monitor_logs 表 - 监控执行日志
-- =====================================================
CREATE TABLE IF NOT EXISTS monitor_logs (
    id VARCHAR(36) PRIMARY KEY,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    tokens_monitored INTEGER,
    tokens_updated INTEGER,
    tokens_failed INTEGER,
    tokens_auto_removed INTEGER,
    alerts_triggered INTEGER,
    removed_by_market_cap INTEGER DEFAULT 0,
    removed_by_liquidity INTEGER DEFAULT 0,
    removed_by_other INTEGER DEFAULT 0,
    error_message VARCHAR(1000),
    config_snapshot JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_monitor_logs_started_at ON monitor_logs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_monitor_logs_status ON monitor_logs(status);

-- =====================================================
-- 6. 为已有数据添加默认值
-- =====================================================

-- 确保所有 monitored_tokens 的 permanently_deleted 有默认值
UPDATE monitored_tokens
SET permanently_deleted = 0
WHERE permanently_deleted IS NULL;

-- 确保所有 potential_tokens 的 permanently_deleted 有默认值
UPDATE potential_tokens
SET permanently_deleted = 0
WHERE permanently_deleted IS NULL;

-- =====================================================
-- 提交事务
-- =====================================================
COMMIT;

-- =====================================================
-- 验证迁移结果
-- =====================================================
SELECT
    'scraper_config' as table_name,
    COUNT(*) as record_count
FROM scraper_config
UNION ALL
SELECT
    'scrape_logs' as table_name,
    COUNT(*) as record_count
FROM scrape_logs
UNION ALL
SELECT
    'monitor_config' as table_name,
    COUNT(*) as record_count
FROM monitor_config
UNION ALL
SELECT
    'monitor_logs' as table_name,
    COUNT(*) as record_count
FROM monitor_logs;

-- =====================================================
-- 迁移完成提示
-- =====================================================
SELECT '✅ 数据库迁移完成！' as status;
