"""受限文件读取工具。只允许读取配置的演示目录。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from taskpilot.config import DEMO_PROJECT_ROOT, MAX_FILE_SIZE
from taskpilot.tools.base import BaseTool, ToolResult

# 禁止访问的敏感文件模式
FORBIDDEN_PATTERNS = {
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_rsa.pub",
    "id_ed25519",
    "id_ed25519.pub",
    "secrets",
    "credentials",
    "*.pem",
    "*.key",
    "config/secrets",
    "config/credentials",
}

# 只允许读取演示目录
_ALLOWED_ROOT: Path = Path(DEMO_PROJECT_ROOT).resolve()


def _is_within_allowed(path: Path) -> bool:
    try:
        path.resolve().relative_to(_ALLOWED_ROOT)
        return True
    except ValueError:
        return False


def _is_forbidden(path: Path) -> bool:
    name_lower = path.name.lower()
    for pattern in FORBIDDEN_PATTERNS:
        pat_lower = pattern.lower()
        if pat_lower.endswith("*"):
            if name_lower.startswith(pat_lower[:-1]):
                return True
        elif pat_lower.startswith("*"):
            if name_lower.endswith(pat_lower[1:]):
                return True
        elif pat_lower in name_lower:
            return True
    return False


class FileReaderTool(BaseTool):
    """读取指定目录内文件的工具。"""

    name = "read_file"
    description = "读取指定目录内文件内容。只允许访问演示目录，禁止读取敏感文件。"

    def __init__(self) -> None:
        super().__init__()
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于演示目录的文件路径，如 'readme.md'。为空表示读取目录列表。",
                }
            },
            "required": ["path"],
        }

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, str]:
        path_value = params.get("path", "")
        if not isinstance(path_value, str):
            return False, "参数 'path' 必须是字符串。"

        if not path_value:
            return False, "参数 'path' 不能为空。"

        if len(path_value.encode("utf-8")) > 500:
            return False, "路径过长。"

        candidate = _ALLOWED_ROOT / path_value
        if not _is_within_allowed(candidate):
            return False, "路径超出演示目录范围。"

        if _is_forbidden(candidate):
            return False, "访问的文件类型受限。"

        try:
            if not candidate.exists():
                return False, "文件不存在。"
            if not candidate.is_file():
                return False, "路径不是文件。"
            if candidate.stat().st_size > MAX_FILE_SIZE:
                return False, "文件过大，超过 200 KB 上限。"
        except Exception as e:
            return False, f"路径检查失败: {e}"

        return True, ""

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        path_value = params.get("path", "")
        candidate = (_ALLOWED_ROOT / path_value).resolve()

        try:
            content = candidate.read_text(encoding="utf-8")
            rel_path = candidate.relative_to(_ALLOWED_ROOT)
            return ToolResult(
                success=True,
                tool_name=self.name,
                params=params,
                result_text=f"文件: {rel_path}\n大小: {candidate.stat().st_size} 字节\n内容:\n{content}",
                error_text="",
                elapsed_seconds=0.0,
            )
        except UnicodeDecodeError:
            try:
                content = candidate.read_bytes().decode("utf-8", errors="replace")
            except Exception as e:
                return ToolResult(
                    success=False,
                    tool_name=self.name,
                    params=params,
                    result_text="",
                    error_text=f"读取文件失败: {e}",
                    elapsed_seconds=0.0,
                )
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=self.name,
                params=params,
                result_text="",
                error_text=f"读取文件失败: {e}",
                elapsed_seconds=0.0,
            )
