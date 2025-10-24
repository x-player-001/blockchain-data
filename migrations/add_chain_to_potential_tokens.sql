-- 为 potential_tokens 表添加 chain 和 dex_type 字段
-- 日期: 2025-10-24

-- 1. 添加 chain 字段（默认为 'bsc'，因为现有数据都是 BSC）
ALTER TABLE potential_tokens
ADD COLUMN IF NOT EXISTS chain VARCHAR(20) NOT NULL DEFAULT 'bsc';

-- 2. 为 chain 字段添加索引
CREATE INDEX IF NOT EXISTS idx_potential_tokens_chain ON potential_tokens(chain);

-- 3. 添加 dex_type 字段（Solana DEX 类型：CPMM, DLMM等）
ALTER TABLE potential_tokens
ADD COLUMN IF NOT EXISTS dex_type VARCHAR(20);

-- 4. 修改 token_address 长度以支持 Solana (44位地址)
ALTER TABLE potential_tokens
ALTER COLUMN token_address TYPE VARCHAR(100);

-- 验证
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'potential_tokens'
  AND column_name IN ('chain', 'dex_type', 'token_address')
ORDER BY column_name;
