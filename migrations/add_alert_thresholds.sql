-- 添加自定义报警阈值字段到 monitored_tokens 表
-- 日期: 2025-10-24

-- 添加 alert_thresholds JSON 字段（存储阈值数组，如 [70, 80, 90]）
ALTER TABLE monitored_tokens
ADD COLUMN IF NOT EXISTS alert_thresholds JSONB DEFAULT '[70, 80, 90]'::jsonb;

-- 为现有记录设置默认值 [70, 80, 90]
UPDATE monitored_tokens
SET alert_thresholds = '[70, 80, 90]'::jsonb
WHERE alert_thresholds IS NULL;

-- 添加注释
COMMENT ON COLUMN monitored_tokens.alert_thresholds IS '自定义报警阈值列表（从ATH计算跌幅），如 [70, 80, 90] 表示跌70%、80%、90%时报警';
