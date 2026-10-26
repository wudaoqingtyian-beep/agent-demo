"""TaskPilot AI 配置模块。

配置通过环境变量读取，支持：
- TASKPILOT_LLM_BASE_URL
- TASKPILOT_LLM_API_KEY
- TASKPILOT_LLM_MODEL
- TASKPILOT_LLM_TIMEOUT

真实 .env 文件必须由运行者提供，且已被 .gitignore 忽略。
"""

from __future__ import annotations

import os
from pathlib import Path

# 从项目根目录加载 .env（如果存在）。
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

# 演示目录：只允许工具访问该目录及其子目录。
DEMO_PROJECT_ROOT = os.getenv(
    "TASKPILOT_DEMO_PROJECT_ROOT",
    str(Path(__file__).resolve().parent.parent / "demo_projects"),
)

# 运行时 SQLite 数据库路径。
DB_PATH = os.getenv(
    "TASKPILOT_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "taskpilot.db"),
)

# 模型配置（OpenAI 兼容接口）
LLM_BASE_URL = os.getenv("TASKPILOT_LLM_BASE_URL", "").strip()
LLM_API_KEY = os.getenv("TASKPILOT_LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("TASKPILOT_LLM_MODEL", "").strip()
LLM_TIMEOUT = float(os.getenv("TASKPILOT_LLM_TIMEOUT", "30"))

# 执行安全限制
MAX_TASK_INPUT_LENGTH = int(os.getenv("TASKPILOT_MAX_INPUT_LENGTH", "2000"))
MAX_FILE_SIZE = int(os.getenv("TASKPILOT_MAX_FILE_SIZE", "204800"))
MAX_OUTPUT_SIZE = int(os.getenv("TASKPILOT_MAX_OUTPUT_SIZE", "204800"))
MAX_RUN_TIMEOUT = int(os.getenv("TASKPILOT_MAX_RUN_TIMEOUT", "120"))
MAX_STEPS = int(os.getenv("TASKPILOT_MAX_STEPS", "10"))

def load_llm_config() -> dict:
    """返回模型配置。真实运行时由运行者设置环境变量；无配置时返回空字典。"""
    return {
        "base_url": LLM_BASE_URL,
        "api_key": LLM_API_KEY,
        "model": LLM_MODEL,
        "timeout": LLM_TIMEOUT,
    }
