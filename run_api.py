"""
启动 FastAPI 服务
"""

import uvicorn
from src.api.app import app


if __name__ == "__main__":
    # 启动 API 服务
    PORT = 8888  # 使用 8888 端口

    print("=" * 60)
    print("🚀 启动 Blockchain Data API 服务")
    print("=" * 60)
    print(f"📍 API 地址: http://localhost:{PORT}")
    print(f"📚 API 文档: http://localhost:{PORT}/docs")
    print(f"📖 ReDoc 文档: http://localhost:{PORT}/redoc")
    print("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
