-- Migration: Add chain support to monitored_tokens table
-- Date: 2025-10-24

-- 1. 添加 chain 字段
ALTER TABLE monitored_tokens
ADD COLUMN IF NOT EXISTS chain VARCHAR(20) NOT NULL DEFAULT 'bsc';

-- 2. 添加索引
CREATE INDEX IF NOT EXISTS idx_monitored_tokens_chain ON monitored_tokens(chain);

-- 3. 添加 dex_type 字段（Solana DEX 类型）
ALTER TABLE monitored_tokens
ADD COLUMN IF NOT EXISTS dex_type VARCHAR(20);

-- 4. 扩展 token_address 长度以支持 Solana 地址（44字符）
ALTER TABLE monitored_tokens
ALTER COLUMN token_address TYPE VARCHAR(100);
