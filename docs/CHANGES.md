# 数据库更新说明

## 已移除 SQLite 支持

项目现在**仅支持 PostgreSQL + TimescaleDB**，已删除所有 SQLite 相关代码。

### 修改内容

1. **数据库管理器** (`src/storage/db_manager.py`)
   - ✅ 移除 SQLite 相关逻辑
   - ✅ 简化为仅支持 PostgreSQL
   - ✅ TimescaleDB hypertable 自动创建
   - ✅ 数据压缩策略（7天后自动压缩）

2. **配置文件** (`src/utils/config.py`)
   - ✅ 删除 `get_db_path()` 方法
   - ✅ 默认数据库改为 PostgreSQL

3. **依赖包** (`requirements.txt`)
   - ✅ 移除 `aiosqlite`
   - ✅ 保留 `asyncpg` (PostgreSQL 异步驱动)
   - ✅ 保留 `psycopg2-binary` (PostgreSQL 同步驱动)

4. **环境配置** (`.env` 和 `.env.example`)
   - ✅ 移除 SQLite 配置示例
   - ✅ 默认使用 PostgreSQL 连接字符串

### 使用前准备

#### 1. 安装 PostgreSQL 和 TimescaleDB

**macOS:**
```bash
brew install postgresql@16
brew install timescaledb
```

**Ubuntu/Debian:**
```bash
sudo apt install postgresql-16
sudo apt install timescaledb-postgresql-16
```

#### 2. 创建数据库

```bash
# 创建数据库
createdb blockchain_data

# 或使用 psql
psql -U postgres
CREATE DATABASE blockchain_data;
\c blockchain_data
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
\q
```

#### 3. 配置连接

编辑 `.env` 文件：
```bash
DATABASE_URL=postgresql://postgres:你的密码@localhost:5432/blockchain_data
```

#### 4. 初始化

```bash
pip install -r requirements.txt
python -m src.main init-db
```

### TimescaleDB 优势

- **时间序列优化**: token_metrics 表自动转换为 hypertable
- **自动分区**: 按时间自动分区，查询速度提升 10-100 倍
- **数据压缩**: 7天后自动压缩，节省 90% 存储空间
- **并行查询**: 充分利用多核 CPU
- **水平扩展**: 支持分布式部署

### 详细文档

参考 [POSTGRESQL_SETUP.md](POSTGRESQL_SETUP.md) 获取完整配置指南。

---

**更新日期**: 2025-10-12
