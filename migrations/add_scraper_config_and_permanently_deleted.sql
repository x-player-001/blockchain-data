-- Migration: 添加爬虫配置表和彻底删除标记
-- Date: 2025-10-24
-- Description:
--   1. 创建 scraper_config 表用于存储爬取配置
--   2. 给 monitored_tokens 和 potential_tokens 添加 permanently_deleted 字段

-- ============================================
-- 1. 创建爬虫配置表
-- ============================================

CREATE TABLE IF NOT EXISTS scraper_config (
    id VARCHAR(36) PRIMARY KEY,

    -- 爬取参数
    top_n_per_chain INTEGER NOT NULL DEFAULT 10,  -- 每条链取前N名代币
    count_per_chain INTEGER NOT NULL DEFAULT 100,  -- 每条链爬取总数
    scrape_interval_min INTEGER NOT NULL DEFAULT 9,  -- 爬取间隔最小值（分钟）
    scrape_interval_max INTEGER NOT NULL DEFAULT 15,  -- 爬取间隔最大值（分钟）

    -- 链配置
    enabled_chains JSONB NOT NULL DEFAULT '["bsc", "solana"]'::jsonb,  -- 启用的链列表

    -- 爬取方法
    use_undetected_chrome INTEGER NOT NULL DEFAULT 0,  -- 是否使用undetected-chrome（0=否，1=是）

    -- 其他配置
    enabled INTEGER NOT NULL DEFAULT 1,  -- 是否启用爬虫（0=禁用，1=启用）

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 备注
    description VARCHAR(500)  -- 配置说明
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_scraper_config_enabled ON scraper_config(enabled);

-- 插入默认配置（如果不存在）
INSERT INTO scraper_config (
    id,
    top_n_per_chain,
    count_per_chain,
    scrape_interval_min,
    scrape_interval_max,
    enabled_chains,
    use_undetected_chrome,
    enabled,
    description
)
SELECT
    gen_random_uuid()::varchar,
    10,
    100,
    9,
    15,
    '["bsc", "solana"]'::jsonb,
    1,  -- 默认使用 undetected-chrome（服务器环境）
    1,
    '默认爬虫配置'
WHERE NOT EXISTS (SELECT 1 FROM scraper_config LIMIT 1);

-- ============================================
-- 2. 添加 permanently_deleted 字段
-- ============================================

-- 给 potential_tokens 表添加 permanently_deleted 字段
ALTER TABLE potential_tokens
ADD COLUMN IF NOT EXISTS permanently_deleted INTEGER NOT NULL DEFAULT 0;

-- 给 monitored_tokens 表添加 permanently_deleted 字段
ALTER TABLE monitored_tokens
ADD COLUMN IF NOT EXISTS permanently_deleted INTEGER NOT NULL DEFAULT 0;

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_potential_permanently_deleted ON potential_tokens(permanently_deleted);
CREATE INDEX IF NOT EXISTS idx_monitored_permanently_deleted ON monitored_tokens(permanently_deleted);

-- 添加注释
COMMENT ON COLUMN potential_tokens.permanently_deleted IS '是否彻底删除：0=正常，1=彻底删除（不返回前端）';
COMMENT ON COLUMN monitored_tokens.permanently_deleted IS '是否彻底删除：0=正常，1=彻底删除（不返回前端）';
COMMENT ON TABLE scraper_config IS '爬虫配置表：存储爬取参数，每次爬取前从此表读取配置';

-- ============================================
-- 完成
-- ============================================

-- 验证
DO $$
BEGIN
    RAISE NOTICE '迁移完成！';
    RAISE NOTICE '1. scraper_config 表已创建';
    RAISE NOTICE '2. potential_tokens.permanently_deleted 字段已添加';
    RAISE NOTICE '3. monitored_tokens.permanently_deleted 字段已添加';
END $$;
