# 📚 文档中心

欢迎查阅 BSC 链上代币数据抓取分析系统的完整文档。

## 📖 文档索引

### 快速开始

1. **[PostgreSQL 配置指南](POSTGRESQL_SETUP.md)**
   - 安装 PostgreSQL 和 TimescaleDB
   - 数据库初始化
   - 连接配置

2. **[API 使用文档](API_README.md)**
   - REST API 接口说明
   - 请求/响应示例
   - 前端集成指南

### 开发文档

3. **[开发指南](DEVELOPMENT_GUIDE.md)**
   - 开发环境搭建
   - 代码规范
   - 测试指南
   - 贡献指南

4. **[Navicat 连接指南](NAVICAT_CONNECTION_GUIDE.md)**
   - 使用 Navicat 连接 PostgreSQL
   - 数据可视化
   - SQL 查询示例

### 项目信息

5. **[项目总结](PROJECT_SUMMARY.md)**
   - 项目架构
   - 技术栈
   - 模块说明

6. **[变更日志](CHANGES.md)**
   - 版本更新记录
   - 功能变更
   - Bug 修复

## 🚀 快速导航

### 我想...

- **启动 API 服务** → 查看 [API 使用文档](API_README.md)
- **配置数据库** → 查看 [PostgreSQL 配置指南](POSTGRESQL_SETUP.md)
- **开发新功能** → 查看 [开发指南](DEVELOPMENT_GUIDE.md)
- **查看数据** → 查看 [Navicat 连接指南](NAVICAT_CONNECTION_GUIDE.md)
- **了解架构** → 查看 [项目总结](PROJECT_SUMMARY.md)

## 📊 项目概览

本项目是一个完整的区块链数据采集和分析系统，包含：

- **数据采集层**: 从多个数据源（AVE API、DexScreener、GeckoTerminal）采集代币数据
- **存储层**: PostgreSQL + TimescaleDB 存储时序数据
- **API 层**: FastAPI 提供 REST API 服务
- **CLI 工具**: 命令行工具进行数据管理

## 🛠️ 主要功能

1. **代币数据采集**
   - 支持市值过滤
   - 实时 OHLCV 数据
   - 多数据源聚合

2. **REST API 服务**
   - 代币列表查询（分页、过滤）
   - 代币详情查询
   - K线数据查询
   - 搜索功能
   - 统计信息

3. **数据分析**
   - 市场数据对比
   - 数据源统计
   - 趋势分析

## 💡 使用建议

### 新手用户

1. 先阅读 [PostgreSQL 配置指南](POSTGRESQL_SETUP.md) 配置数据库
2. 然后查看 [API 使用文档](API_README.md) 启动 API 服务
3. 使用 Swagger UI (http://localhost:8888/docs) 测试接口

### 开发者

1. 阅读 [开发指南](DEVELOPMENT_GUIDE.md) 了解项目架构
2. 查看 [项目总结](PROJECT_SUMMARY.md) 了解技术栈
3. 参考 [变更日志](CHANGES.md) 了解最新变更

### 数据分析师

1. 使用 [Navicat 连接指南](NAVICAT_CONNECTION_GUIDE.md) 连接数据库
2. 通过 API 获取数据进行分析
3. 使用 SQL 查询进行深度分析

## 🔗 相关链接

- **主项目 README**: [../README.md](../README.md)
- **API Swagger 文档**: http://localhost:8888/docs (需先启动服务)
- **AVE API 文档**: https://ave-cloud.gitbook.io/data-api

## 📝 文档维护

如发现文档有误或需要补充，请：

1. 提交 Issue 说明问题
2. 或直接提交 Pull Request 修正

---

**最后更新**: 2025-10-18
