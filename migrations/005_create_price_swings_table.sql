-- Create price_swings table to store price movement analysis results
-- Records all significant price swings (>50% by default) for each token

CREATE TABLE IF NOT EXISTS price_swings (
    id VARCHAR(36) PRIMARY KEY,
    token_id VARCHAR(36) NOT NULL,  -- References dexscreener_tokens.id (no FK constraint)

    -- Swing details
    swing_type VARCHAR(10) NOT NULL,  -- 'rise' or 'fall'
    swing_pct NUMERIC(12,2) NOT NULL,  -- Percentage change (can be negative for falls)

    -- Time information
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    duration_hours NUMERIC(10,2) NOT NULL,

    -- Price information
    start_price NUMERIC(30,18) NOT NULL,
    end_price NUMERIC(30,18) NOT NULL,

    -- Analysis metadata
    min_swing_threshold NUMERIC(6,2) NOT NULL,  -- The threshold used for this analysis (e.g., 50.0)
    timeframe VARCHAR(20),  -- The K-line timeframe used (e.g., '4h', '1h')

    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient querying
CREATE INDEX idx_price_swings_token_id ON price_swings(token_id);
CREATE INDEX idx_price_swings_swing_type ON price_swings(swing_type);
CREATE INDEX idx_price_swings_start_time ON price_swings(start_time);
CREATE INDEX idx_price_swings_swing_pct ON price_swings(swing_pct);

-- Create composite index for common queries
CREATE INDEX idx_price_swings_token_time ON price_swings(token_id, start_time DESC);

-- Add comments
COMMENT ON TABLE price_swings IS '代币价格大幅波动记录表';
COMMENT ON COLUMN price_swings.token_id IS '代币ID，引用dexscreener_tokens.id';
COMMENT ON COLUMN price_swings.swing_type IS '波动类型：rise(上涨) 或 fall(下跌)';
COMMENT ON COLUMN price_swings.swing_pct IS '涨跌幅百分比';
COMMENT ON COLUMN price_swings.min_swing_threshold IS '分析时使用的最小波动阈值';
COMMENT ON COLUMN price_swings.timeframe IS 'K线时间周期';
