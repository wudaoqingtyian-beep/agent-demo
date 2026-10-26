"""Test result analysis and report generation tool."""

from __future__ import annotations

import re
from typing import Any

from taskpilot.tools.base import BaseTool, ToolResult


class ReportAnalyzerTool(BaseTool):
    """Analyze test output and generate a structured report."""

    name = "analyze_test_result"
    description = "Receive real test output and summarize failure reasons, risks, and suggestions."

    def __init__(self) -> None:
        super().__init__()
        self.parameters = {
            "type": "object",
            "properties": {
                "test_output": {
                    "type": "string",
                    "description": "Real test command output content.",
                }
            },
            "required": ["test_output"],
        }

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, str]:
        output = params.get("test_output", "")
        if not isinstance(output, str):
            return False, "Parameter 'test_output' must be a string."

        if len(output) > 200000:
            return False, "Test output too long."

        if not output.strip():
            return False, "Test output cannot be empty."

        return True, ""

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        output = params.get("test_output", "")

        facts = self._extract_facts(output)
        risk = self._classify_risk(output)
        suggestion = self._suggest_fixes(output)

        report_lines = [
            "=== Test Result Analysis Report ===",
            "",
            "【Facts (actual observations)】",
        ]
        report_lines.extend(facts)
        report_lines.extend([
            "",
            "【Risk Assessment】",
        ])
        report_lines.extend(risk)
        report_lines.extend([
            "",
            "【Suggestions】",
        ])
        report_lines.extend(suggestion)
        report_lines.extend([
            "",
            "【Notes】",
            "- The 'facts' section is auto-extracted from real test output.",
            "- Other analysis (risk, suggestions, conclusions) is model/rule inference.",
            "- If model is unavailable, only rule-based analysis is used.",
        ])

        return ToolResult(
            success=True,
            tool_name=self.name,
            params=params,
            result_text=chr(10).join(report_lines),
            error_text="",
            elapsed_seconds=0.0,
        )

    def _extract_facts(self, output: str) -> list[str]:
        facts = []
        lines = output.splitlines()

        for line in lines:
            ls = line.strip()
            if not ls:
                continue
            if "FAILED" in ls.upper():
                facts.append(f"Failure item: {ls}")
            elif "assert" in ls.lower():
                facts.append(f"Assertion failure: {ls}")
            elif "passed" in ls.lower():
                facts.append(f"Passed item: {ls}")

        if not facts:
            low = output.lower()
            if "error" in low or "exception" in low:
                facts.append("Output contains error or exception.")
            elif "fail" in low:
                facts.append("Output contains failure-related keywords.")
            else:
                facts.append("No clear failure or pass markers detected.")

        return facts

    def _classify_risk(self, output: str) -> list[str]:
        risks = []
        low = output.lower()

        if "timeout" in low or "timed out" in low:
            risks.append("High risk: test may timeout.")
        if re.search(r"assert.*None", output, re.IGNORECASE):
            risks.append("Medium risk: assertion may be None.")

        if not risks:
            risks.append("Low risk: no obvious issues detected.")

        return risks

    def _suggest_fixes(self, output: str) -> list[str]:
        suggestions = []
        lines = output.splitlines()

        for line in lines:
            ls = line.strip()
            if "FAILED" in ls.upper() and "assert" in ls.lower():
                suggestions.append("Fix assertion failure: check expected vs actual values.")
                break

        if not suggestions:
            suggestions.append("Locate the issue from actual output.")
            suggestions.append("Check the latest test log for specific failure lines.")

        return suggestions
