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
ALTER TABLE scraper_config
ADD COLUMN IF NOT EXISTS min_market_cap NUMERIC(20, 2) DEFAULT NULL
COMMENT '最小市值（美元），为空则不过滤';

ALTER TABLE scraper_config
ADD COLUMN IF NOT EXISTS min_liquidity NUMERIC(20, 2) DEFAULT NULL
COMMENT '最小流动性（美元），为空则不过滤';

ALTER TABLE scraper_config
ADD COLUMN IF NOT EXISTS max_token_age_days INTEGER DEFAULT NULL
COMMENT '最大代币年龄（天），为空则不过滤';

-- =====================================================
-- 2. 创建 scrape_logs 表 - 记录爬虫执行日志
-- =====================================================
CREATE TABLE IF NOT EXISTS scrape_logs (
    id VARCHAR(36) PRIMARY KEY,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, success, failed
    chain VARCHAR(20),
    tokens_scraped INTEGER COMMENT '爬取到的代币总数',
    tokens_filtered INTEGER COMMENT '过滤后剩余的代币数',
    tokens_saved INTEGER COMMENT '保存到数据库的代币数',
    tokens_skipped INTEGER COMMENT '跳过的代币数',
    filtered_by_market_cap INTEGER DEFAULT 0 COMMENT '因市值被过滤的数量',
    filtered_by_liquidity INTEGER DEFAULT 0 COMMENT '因流动性被过滤的数量',
    filtered_by_age INTEGER DEFAULT 0 COMMENT '因年龄被过滤的数量',
    error_message VARCHAR(1000),
    config_snapshot JSONB COMMENT '配置快照',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_scrape_logs_started_at ON scrape_logs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scrape_logs_status ON scrape_logs(status);
CREATE INDEX IF NOT EXISTS idx_scrape_logs_chain ON scrape_logs(chain);

-- =====================================================
-- 3. 扩展 monitored_tokens 表 - 添加删除原因跟踪
-- =====================================================
ALTER TABLE monitored_tokens
ADD COLUMN IF NOT EXISTS removal_reason VARCHAR(50) DEFAULT NULL
COMMENT '删除原因: low_market_cap, low_liquidity, manual, other';

ALTER TABLE monitored_tokens
ADD COLUMN IF NOT EXISTS removal_threshold_value NUMERIC(30, 2) DEFAULT NULL
COMMENT '触发删除的阈值（市值或流动性）';

-- =====================================================
-- 4. 创建 monitor_config 表 - 监控配置
-- =====================================================
CREATE TABLE IF NOT EXISTS monitor_config (
    id VARCHAR(36) PRIMARY KEY,
    min_monitor_market_cap NUMERIC(20, 2) DEFAULT NULL COMMENT '最小监控市值阈值',
    min_monitor_liquidity NUMERIC(20, 2) DEFAULT NULL COMMENT '最小监控流动性阈值',
    update_interval_minutes INTEGER NOT NULL DEFAULT 5 COMMENT '更新间隔（分钟）',
    default_drop_threshold NUMERIC(5, 2) NOT NULL DEFAULT 20.0 COMMENT '默认跌幅阈值',
    default_alert_thresholds JSONB NOT NULL DEFAULT '[70, 80, 90]' COMMENT '默认报警阈值',
    enabled INTEGER NOT NULL DEFAULT 1 COMMENT '是否启用',
    max_retry_count INTEGER NOT NULL DEFAULT 3 COMMENT '最大重试次数',
    batch_size INTEGER NOT NULL DEFAULT 10 COMMENT '批处理大小',
    description TEXT COMMENT '配置说明',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认配置（如果不存在）
INSERT INTO monitor_config (id, min_monitor_market_cap, min_monitor_liquidity, update_interval_minutes, default_drop_threshold, default_alert_thresholds, enabled)
SELECT
    gen_random_uuid()::text,
    NULL,
    NULL,
    5,
    20.0,
    '[70, 80, 90]'::jsonb,
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
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, success, failed
    tokens_monitored INTEGER COMMENT '监控的代币总数',
    tokens_updated INTEGER COMMENT '成功更新的代币数',
    tokens_failed INTEGER COMMENT '更新失败的代币数',
    tokens_auto_removed INTEGER COMMENT '自动删除的代币数',
    alerts_triggered INTEGER COMMENT '触发的报警次数',
    removed_by_market_cap INTEGER DEFAULT 0 COMMENT '因市值被删除的数量',
    removed_by_liquidity INTEGER DEFAULT 0 COMMENT '因流动性被删除的数量',
    removed_by_other INTEGER DEFAULT 0 COMMENT '因其他原因被删除的数量',
    error_message VARCHAR(1000),
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
