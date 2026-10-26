"""TaskPilot AI 启动脚本。"""

from pathlib import Path

from taskpilot.main import app

if __name__ == "__main__":
    import uvicorn

    # 默认运行在 127.0.0.1:8000；可通过环境变量覆盖 HOST / PORT。
    host = "127.0.0.1"
    port = int("8000")
    uvicorn.run(app, host=host, port=port)
