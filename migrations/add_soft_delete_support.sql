-- 添加软删除支持
-- 为 potential_tokens 和 monitored_tokens 表添加 deleted_at 字段

-- 为 potential_tokens 添加 deleted_at 字段
ALTER TABLE potential_tokens
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP DEFAULT NULL;

-- 为 monitored_tokens 添加 deleted_at 字段
ALTER TABLE monitored_tokens
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP DEFAULT NULL;

-- 为 potential_tokens 添加索引
CREATE INDEX IF NOT EXISTS idx_potential_deleted_at ON potential_tokens(deleted_at);

-- 为 monitored_tokens 添加索引
CREATE INDEX IF NOT EXISTS idx_monitored_deleted_at ON monitored_tokens(deleted_at);

-- 添加注释
COMMENT ON COLUMN potential_tokens.deleted_at IS '软删除时间戳，NULL表示未删除';
COMMENT ON COLUMN monitored_tokens.deleted_at IS '软删除时间戳，NULL表示未删除';
