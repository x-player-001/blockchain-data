"""
启动 FastAPI 服务
"""

import os
import uvicorn
from src.api.app import app


if __name__ == "__main__":
    # 从环境变量读取端口，默认使用 18763（更安全的非标准端口）
    PORT = int(os.getenv("API_PORT", 18763))

    print("=" * 60)
    print("🚀 启动 Blockchain Data API 服务")
    print("=" * 60)
    print(f"📍 API 地址: http://localhost:{PORT}")
    print(f"📚 API 文档: http://localhost:{PORT}/docs")
    print(f"📖 ReDoc 文档: http://localhost:{PORT}/redoc")
    print("=" * 60)

    # 从环境变量读取监听地址
    # 生产环境：使用 0.0.0.0 + 防火墙限制特定IP访问
    # 纯本地环境：使用 127.0.0.1
    HOST = os.getenv("API_HOST", "0.0.0.0")

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info"
    )
