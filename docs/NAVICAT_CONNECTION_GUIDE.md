# Navicat 远程连接指南

## 配置完成 ✅

PostgreSQL 已配置为允许局域网访问。

## 连接信息

### Mac 服务器信息
- **IP 地址**: `192.168.50.60`
- **端口**: `5432`
- **数据库名**: `blockchain_data`
- **用户名**: `mac`
- **密码**: `blockchain2024`

## Navicat 连接步骤

### 1. 打开 Navicat

在 Windows 电脑上启动 Navicat Premium 或 Navicat for PostgreSQL。

### 2. 新建连接

点击左上角 **"连接"** → 选择 **"PostgreSQL"**

### 3. 填写连接信息

在弹出的对话框中填写：

```
连接名:      BSC Token Data (或任意名称)
主机:        192.168.50.60
端口:        5432
初始数据库:  blockchain_data
用户名:      mac
密码:        blockchain2024
```

**重要设置：**
- ✅ 勾选 "保存密码"
- ✅ 连接类型选择 "基本"（不是 SSH）

### 4. 测试连接

点击 **"测试连接"** 按钮，如果显示 **"连接成功"**，说明配置正确。

### 5. 连接数据库

点击 **"确定"** 保存连接，然后双击连接名即可连接。

## 数据库表结构

连接成功后，你会看到以下3个表：

### 1. tokens（代币基本信息）
- `id`: 主键
- `address`: 合约地址（唯一）
- `name`: 代币名称
- `symbol`: 代币符号
- `decimals`: 小数位数
- `total_supply`: 总供应量
- `created_at`: 创建时间
- `updated_at`: 更新时间

### 2. token_metrics（代币指标，时间序列）
- `id`: 主键
- `token_id`: 关联 tokens 表
- `timestamp`: 时间戳
- `price_usd`: 美元价格
- `market_cap`: 市值
- `liquidity_usd`: 流动性
- `volume_24h`: 24小时交易量
- `price_change_24h`: 24小时涨跌幅
- `holders_count`: 持有者数量
- `transactions_24h`: 24小时交易次数

### 3. token_pairs（交易对信息）
- `id`: 主键
- `token_id`: 关联 tokens 表
- `dex_name`: DEX名称（如 PancakeSwap）
- `pair_address`: 交易对地址
- `base_token`: 基础代币（如 WBNB）
- `liquidity_usd`: 流动性
- `volume_24h`: 24小时交易量

## 常用查询示例

### 查询市值前10的代币

```sql
SELECT
    t.symbol,
    t.name,
    tm.price_usd,
    tm.market_cap,
    tm.volume_24h,
    tm.price_change_24h
FROM tokens t
INNER JOIN token_metrics tm ON t.id = tm.token_id
INNER JOIN (
    SELECT token_id, MAX(timestamp) as max_timestamp
    FROM token_metrics
    GROUP BY token_id
) latest ON tm.token_id = latest.token_id
    AND tm.timestamp = latest.max_timestamp
WHERE tm.market_cap >= 1000000
ORDER BY tm.market_cap DESC
LIMIT 10;
```

### 查询24小时涨幅最大的代币

```sql
SELECT
    t.symbol,
    t.name,
    tm.price_change_24h,
    tm.market_cap
FROM tokens t
INNER JOIN token_metrics tm ON t.id = tm.token_id
INNER JOIN (
    SELECT token_id, MAX(timestamp) as max_timestamp
    FROM token_metrics
    GROUP BY token_id
) latest ON tm.token_id = latest.token_id
    AND tm.timestamp = latest.max_timestamp
WHERE tm.price_change_24h > 0
ORDER BY tm.price_change_24h DESC
LIMIT 10;
```

### 查询某个代币的历史数据

```sql
SELECT
    timestamp,
    price_usd,
    market_cap,
    volume_24h
FROM token_metrics
WHERE token_id = (SELECT id FROM tokens WHERE symbol = 'BNB')
ORDER BY timestamp DESC
LIMIT 100;
```

## 故障排除

### 问题1: 连接超时

**原因**: 防火墙阻止
**解决**: 在 Mac 上运行：
```bash
sudo pfctl -d  # 临时关闭防火墙测试
```

或添加防火墙规则：
```bash
# 允许5432端口
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /opt/homebrew/opt/postgresql@16/bin/postgres
```

### 问题2: 身份验证失败

**原因**: 密码错误
**解决**: 确认密码是 `blockchain2024`，或重新设置密码：
```bash
/opt/homebrew/opt/postgresql@16/bin/psql -d postgres -c "ALTER USER mac WITH PASSWORD 'your_new_password';"
```

### 问题3: 无法连接到服务器

**原因**: PostgreSQL 服务未启动
**解决**:
```bash
brew services start postgresql@16
```

### 问题4: 找不到数据库

**原因**: 数据库名称错误
**解决**: 确保初始数据库名称是 `blockchain_data`

## 查看服务状态

在 Mac 上检查 PostgreSQL 状态：
```bash
brew services list | grep postgresql@16
```

查看当前连接：
```bash
/opt/homebrew/opt/postgresql@16/bin/psql -d blockchain_data -c "SELECT * FROM pg_stat_activity WHERE datname = 'blockchain_data';"
```

## 安全建议

### 生产环境
1. **修改默认密码**: 使用更强的密码
2. **限制IP范围**: 只允许特定IP连接
3. **使用SSL连接**: 启用 SSL 加密
4. **定期备份**: 设置自动备份策略

### 当前配置（开发环境）
- ✅ 仅允许局域网 192.168.50.0/24 访问
- ✅ 使用密码认证（md5）
- ⚠️ 未启用 SSL（开发环境可接受）

## 数据收集和查询

### 收集数据
在 Mac 上运行：
```bash
cd /Users/mac/Documents/code/blockchain-data
python -m src.main collect
```

### 查询数据
在 Mac 上运行：
```bash
python -m src.main query --limit 20
```

或直接在 Navicat 中查询。

## 配置文件位置

如需手动修改：
- **PostgreSQL 配置**: `/opt/homebrew/var/postgresql@16/postgresql.conf`
- **访问控制**: `/opt/homebrew/var/postgresql@16/pg_hba.conf`

修改后需重启：
```bash
brew services restart postgresql@16
```

---

**连接信息速查**

```
Host:     192.168.50.60
Port:     5432
Database: blockchain_data
User:     mac
Password: blockchain2024
```

现在可以在 Windows 的 Navicat 中连接了！
