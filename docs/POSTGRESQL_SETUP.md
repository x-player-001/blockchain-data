# PostgreSQL + TimescaleDB 设置指南

## 已完成的修改

代码已更新以支持 PostgreSQL 和 TimescaleDB：

1. ✅ 数据库管理器支持 TimescaleDB 扩展
2. ✅ 自动创建 hypertable（时间序列优化）
3. ✅ 数据压缩策略（7天后自动压缩）
4. ✅ 添加 asyncpg 驱动
5. ✅ 更新 .env 配置

## 配置步骤

### 1. 创建数据库

```bash
# 连接到 PostgreSQL
psql -U postgres

# 创建数据库
CREATE DATABASE blockchain_data;

# 连接到新数据库
\c blockchain_data

# 启用 TimescaleDB 扩展（如果还没启用）
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

# 退出
\q
```

### 2. 修改 .env 配置

编辑 `.env` 文件，设置数据库连接字符串：

```bash
# 格式: postgresql://用户名:密码@主机:端口/数据库名
DATABASE_URL=postgresql://postgres:你的密码@localhost:5432/blockchain_data
```

常见配置：
- 默认用户：`postgres`
- 默认端口：`5432`
- 主机：`localhost` 或 `127.0.0.1`

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

关键包：
- `asyncpg`: PostgreSQL 异步驱动
- `psycopg2-binary`: PostgreSQL 同步驱动
- `sqlalchemy`: ORM

### 4. 初始化数据库

```bash
python -m src.main init-db
```

这将：
- 创建所有表
- 启用 TimescaleDB 扩展
- 将 `token_metrics` 转换为 hypertable
- 设置数据压缩策略

### 5. 验证设置

```bash
# 测试数据源
python -m src.main health

# 收集数据测试
python -m src.main collect --min-market-cap 1000000
```

## TimescaleDB 功能

### Hypertable（超表）

`token_metrics` 表已被转换为 hypertable，提供：

- ✅ 自动数据分区（按时间）
- ✅ 高效的时间范围查询
- ✅ 并行查询优化
- ✅ 自动数据压缩

### 数据压缩

配置的压缩策略：
- 7天后的数据自动压缩
- 按 `token_id` 分段压缩
- 节省存储空间 90%+
- 查询时自动解压

### 查询 TimescaleDB 状态

```sql
-- 查看 hypertables
SELECT * FROM timescaledb_information.hypertables;

-- 查看压缩状态
SELECT * FROM timescaledb_information.chunks;

-- 查看压缩策略
SELECT * FROM timescaledb_information.jobs;
```

## PostgreSQL vs SQLite 对比

| 特性 | PostgreSQL + TimescaleDB | SQLite |
|------|-------------------------|--------|
| **时间序列优化** | ✅ Hypertable | ❌ |
| **数据压缩** | ✅ 自动压缩 | ❌ |
| **并发写入** | ✅ 完全支持 | ⚠️ 有限 |
| **性能（大数据）** | ✅ 优秀 | ⚠️ 一般 |
| **部署复杂度** | ⚠️ 需要服务 | ✅ 无需服务 |

## 常见问题

### Q: 如何查看数据库大小？

```sql
SELECT
    pg_size_pretty(pg_database_size('blockchain_data')) as database_size;
```

### Q: 如何查看表大小？

```sql
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Q: 如何手动触发压缩？

```sql
SELECT compress_chunk(c)
FROM show_chunks('token_metrics') c;
```

### Q: 如何切换回 SQLite？

编辑 `.env` 文件：

```bash
# 注释掉 PostgreSQL
# DATABASE_URL=postgresql://postgres:password@localhost:5432/blockchain_data

# 启用 SQLite
DATABASE_URL=sqlite:///data/blockchain_data.db
```

然后重新初始化：
```bash
python -m src.main init-db
```

## 性能优化建议

### 1. 连接池配置

可以在 `config.py` 中添加连接池参数：

```python
# 示例（未添加到代码中）
engine = create_async_engine(
    database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
```

### 2. 创建索引

```sql
-- 为常用查询创建索引
CREATE INDEX idx_metrics_market_cap_timestamp
ON token_metrics(market_cap DESC, timestamp DESC);

CREATE INDEX idx_metrics_volume
ON token_metrics(volume_24h DESC);
```

### 3. 数据清理

定期清理旧数据：

```sql
-- 删除 30 天前的数据
DELETE FROM token_metrics
WHERE timestamp < NOW() - INTERVAL '30 days';
```

或使用 TimescaleDB 的数据保留策略：

```sql
SELECT add_retention_policy('token_metrics', INTERVAL '30 days');
```

## 监控和维护

### 检查数据库连接

```bash
# 查看活跃连接
psql -U postgres -d blockchain_data -c "SELECT * FROM pg_stat_activity;"
```

### 查看表统计

```bash
psql -U postgres -d blockchain_data -c "SELECT * FROM pg_stat_user_tables;"
```

### 备份数据库

```bash
# 备份
pg_dump -U postgres blockchain_data > backup.sql

# 恢复
psql -U postgres blockchain_data < backup.sql
```

## 故障排除

### 连接失败

```bash
# 检查 PostgreSQL 是否运行
pg_ctl status

# 或
brew services list | grep postgresql
```

### TimescaleDB 扩展未找到

```bash
# 重新安装 TimescaleDB
brew reinstall timescaledb

# 或参考官方文档
# https://docs.timescale.com/install/latest/
```

### 权限问题

```sql
-- 授予用户权限
GRANT ALL PRIVILEGES ON DATABASE blockchain_data TO postgres;
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;
```

---

**配置完成！** 现在可以享受 TimescaleDB 的高性能时间序列数据处理了。
