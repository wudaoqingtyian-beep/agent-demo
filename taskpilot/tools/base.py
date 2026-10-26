"""工具基类。所有工具必须继承此基类并实现 _execute 方法。"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    success: bool
    tool_name: str
    params: dict[str, Any]
    result_text: str
    error_text: str
    elapsed_seconds: float


class BaseTool(ABC):
    """工具基类。"""

    name: str
    description: str
    parameters: dict[str, Any]

    def __init__(self) -> None:
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def reset(self) -> None:
        self._call_count = 0

    @abstractmethod
    def _execute(self, params: dict[str, Any]) -> ToolResult:
        pass

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, str]:
        """检查参数是否有效。返回 (是否有效, 错误信息)。"""
        return True, ""

    def call(self, params: dict[str, Any]) -> ToolResult:
        self._call_count += 1
        start = time.perf_counter()
        try:
            valid, error = self.validate_params(params)
            if not valid:
                return ToolResult(
                    success=False,
                    tool_name=self.name,
                    params=params,
                    result_text="",
                    error_text=error,
                    elapsed_seconds=time.perf_counter() - start,
                )
            result = self._execute(params)
            result.elapsed_seconds = time.perf_counter() - start
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=self.name,
                params=params,
                result_text="",
                error_text=f"工具执行异常: {e}",
                elapsed_seconds=time.perf_counter() - start,
            )
