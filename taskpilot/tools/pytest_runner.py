"""测试执行工具（优先支持 pytest）。"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

from taskpilot.config import DEMO_PROJECT_ROOT, MAX_RUN_TIMEOUT, MAX_OUTPUT_SIZE
from taskpilot.tools.base import BaseTool, ToolResult

# 白名单中的测试命令
ALLOWED_TEST_CMDS = {"pytest", "pytest -x", "pytest -v"}


def _resolve_demo_projects() -> Path:
    root = Path(DEMO_PROJECT_ROOT).resolve()
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    return root


class PytestRunnerTool(BaseTool):
    """在预先配置的 Demo 项目目录中运行指定的测试命令。"""

    name = "run_tests"
    description = "在指定的 Demo 项目目录中运行白名单内的测试命令（第一版仅支持 pytest）。"

    def __init__(self) -> None:
        super().__init__()
        self.parameters = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": list(ALLOWED_TEST_CMDS),
                    "description": "测试命令，仅允许白名单内的命令。",
                }
            },
            "required": ["command"],
        }

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, str]:
        cmd = params.get("command", "")
        if not isinstance(cmd, str):
            return False, "参数 'command' 必须是字符串。"

        if cmd not in ALLOWED_TEST_CMDS:
            return False, f"命令 '{cmd}' 不在白名单内。仅允许: {', '.join(sorted(ALLOWED_TEST_CMDS))}。"

        return True, ""

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        cmd = params.get("command", "")
        project_root = _resolve_demo_projects()
        start_time = time.perf_counter()

        try:
            proc = subprocess.run(
                cmd.split(),
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=MAX_RUN_TIMEOUT,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            combined = stdout + "\n" + stderr

            # 严格限制输出总长度不超过 MAX_OUTPUT_SIZE
            truncated = ""
            if len(combined) > MAX_OUTPUT_SIZE:
                keep = MAX_OUTPUT_SIZE - len(f"\n[输出被截断，已限制 {MAX_OUTPUT_SIZE} 字符]...")
                truncated = f"\n[输出被截断，已限制 {MAX_OUTPUT_SIZE} 字符]..."
                combined = combined[:max(keep, 0)] + truncated

            elapsed = time.perf_counter() - start_time
            return ToolResult(
                success=True,
                tool_name=self.name,
                params=params,
                result_text=(
                    f"命令: {cmd}\n"
                    f"工作目录: {project_root}\n"
                    f"退出码: {proc.returncode}\n"
                    f"耗时: {elapsed:.2f} 秒\n"
                    f"标准输出:\n{stdout}"
                    f"标准错误:\n{stderr}"
                    f"{truncated}"
                ),
                error_text="",
                elapsed_seconds=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - start_time
            return ToolResult(
                success=False,
                tool_name=self.name,
                params=params,
                result_text="",
                error_text=f"测试执行超时，超过 {MAX_RUN_TIMEOUT} 秒。",
                elapsed_seconds=elapsed,
            )
        except FileNotFoundError:
            elapsed = time.perf_counter() - start_time
            return ToolResult(
                success=False,
                tool_name=self.name,
                params=params,
                result_text="",
                error_text="未找到测试运行器（如 pytest）。请确认环境已安装pytest。",
                elapsed_seconds=elapsed,
            )
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            return ToolResult(
                success=False,
                tool_name=self.name,
                params=params,
                result_text="",
                error_text=f"测试执行异常: {e}",
                elapsed_seconds=elapsed,
            )
