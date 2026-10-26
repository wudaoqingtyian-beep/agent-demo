"""FastAPI 应用：TaskPilot AI。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from taskpilot import config, db as db_module
from taskpilot.db import (
    add_step,
    add_tool_call,
    create_task,
    get_task,
    get_task_details,
    list_tasks,
    update_task_report,
    update_task_status,
)
from taskpilot.schemas import (
    TaskCreate, TaskDetailsResponse, TaskResponse,
    TaskSummary, HealthResponse,
)
from taskpilot.tools import (
    FileReaderTool, PytestRunnerTool, ReportAnalyzerTool,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# 日志配置
logger = logging.getLogger("taskpilot")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    db_module.close_db()


app = FastAPI(
    title="TaskPilot AI",
    version="0.1.0",
    lifespan=lifespan,
)

# 工具注册表
AGENT_TOOLS = {
    FileReaderTool.name: FileReaderTool(),
    PytestRunnerTool.name: PytestRunnerTool(),
    ReportAnalyzerTool.name: ReportAnalyzerTool(),
}


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse()


@app.post("/api/tasks", response_model=TaskResponse)
def create_and_run_task(payload: TaskCreate, background_tasks: BackgroundTasks):
    if len(payload.user_task) > config.MAX_TASK_INPUT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail="输入过长，最大长度为 2000 字符。",
        )
    if not payload.user_task.strip():
        raise HTTPException(
            status_code=400,
            detail="任务不能为空。",
        )

    task = create_task(payload.user_task.strip(), status="pending")

    # 后台异步执行 Agent 环路，避免阻塞 HTTP 线程
    background_tasks.add_task(run_agent_loop, task.id, task.user_task)

    # 立即返回，任务仍在后台执行
    return TaskResponse.model_validate(task)


def run_agent_loop(task_id: str, user_task: str) -> None:
    """执行 Agent 工具调用环路，将步骤与工具调用持久化到 SQLite。

    演示环境未配置真实 LLM，因此采用基于规则的固定步骤：
    1. 规划任务
    2. 读取演示目录中的文件
    3. 运行 pytest 测试
    4. 分析测试输出
    5. 生成最终报告
    """
    try:
        _run_agent_loop_inner(task_id, user_task)
    except Exception as exc:
        logger.exception("Agent 环路执行失败，任务 %s", task_id)
        update_task_status(task_id, "failed", error=str(exc))


def _run_agent_loop_inner(task_id: str, user_task: str) -> None:
    steps: list[dict] = []
    tools_by_step: dict[int, list[dict]] = {}

    def record_step(seq: int, name: str, detail: str) -> int:
        step = add_step(task_id, seq, name, detail)
        steps.append({"seq": seq, "name": name, "detail": detail})
        return step.id

    def record_tool_call(step_id: int, tool_name: str, params: dict, result) -> None:
        params_str = str(params)
        add_tool_call(
            step_id,
            tool_name,
            params_str,
            result.result_text,
            result.error_text,
        )
        tools_by_step.setdefault(step_id, []).append({
            "tool_name": tool_name,
            "params": params_str,
            "result_text": result.result_text,
            "error_text": result.error_text,
        })

    # 步骤 1: 规划
    step1_id = record_step(1, "规划任务", f"分析用户任务: {user_task[:100]}...")

    # 步骤 2: 读取演示目录中的 README
    step2_id = record_step(2, "读取文件", "读取 demo_project_a/README.md 了解测试说明。")
    read_result = AGENT_TOOLS["read_file"].call({"path": "demo_project_a/README.md"})
    record_tool_call(step2_id, "read_file", {"path": "demo_project_a/README.md"}, read_result)

    # 步骤 3: 运行测试
    step3_id = record_step(3, "运行测试", "在 demo_project_a 目录运行 pytest -v。")
    test_result = AGENT_TOOLS["run_tests"].call({"command": "pytest -v"})
    record_tool_call(step3_id, "run_tests", {"command": "pytest -v"}, test_result)

    # 步骤 4: 分析测试结果
    step4_id = record_step(4, "分析结果", "使用 ReportAnalyzerTool 分析 pytest 输出。")
    analysis_result = AGENT_TOOLS["analyze_test_result"].call(
        {"test_output": test_result.result_text or test_result.error_text or "(无输出)"}
    )
    record_tool_call(step4_id, "analyze_test_result", {"test_output": "(truncated)"}, analysis_result)

    # 生成最终报告
    final_report = _generate_agent_report(task_id, steps, tools_by_step)
    # 附带分析工具的详细结果（安全引用）
    if analysis_result and analysis_result.result_text:
        final_report += "\n\n" + "=" * 30 + "\n" + analysis_result.result_text

    update_task_status(task_id, "completed")
    update_task_report(task_id, final_report)


@app.get("/api/tasks", response_model=list[TaskSummary])
def list_all_tasks(limit: int = 50, offset: int = 0):
    tasks = list_tasks(limit=limit, offset=offset)
    return [TaskSummary.model_validate(t) for t in tasks]


@app.get("/api/tasks/{task_id}", response_model=TaskDetailsResponse)
def get_task_endpoint(task_id: str):
    details = get_task_details(task_id)
    if details is None:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return TaskDetailsResponse.model_validate(details)


@app.get("/", response_class=HTMLResponse)
def index():
    if FRONTEND_DIR.exists():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse(
        "<h1>TaskPilot AI</h1>"
        "<p>正在开发中。请访问 <a href=\"/docs\">/docs</a> 查看 API 文档。</p>"
    )


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def _generate_agent_report(task_id: str, steps: list, tools_by_step: dict) -> str:
    """生成结构化执行报告。"""
    task = get_task(task_id)
    if not task:
        return "错误：任务不存在。"

    lines = [
        "=== 任务执行报告 ===",
        "",
        "【任务目标】",
        task.user_task,
        "",
        "【执行状态】",
        task.status,
        f"开始时间: {task.created_at}",
        f"结束时间: {task.ended_at or '未结束'}",
    ]
    if task.error:
        lines.append(f"错误: {task.error}")
    lines.extend([
        "",
        "【执行步骤】",
    ])
    for step in steps:
        lines.append(f"- [{step['seq']}] {step['name']}: {step['detail']}")
    lines.extend([
        "",
        "【调用的工具】",
    ])
    for seq, tools in sorted(tools_by_step.items()):
        for t in tools:
            lines.append(f"  步骤 {seq}: {t['tool_name']}()")
    lines.extend([
        "",
        "【关键结果】",
    ])
    if task.final_report:
        report_part = task.final_report
        if len(report_part) > 500:
            report_part = report_part[:500] + "..."
        lines.append(report_part)
    else:
        lines.append("暂无最终报告。")
    lines.extend([
        "",
        "【风险与建议】",
        "1. 任务完成程度取决于模型与工具调用结果。",
        "2. 如模型不稳定，部分步骤可能无法完成。",
        "3. 建议人工复核最终报告与工具执行证据。",
        "",
        "【未完成事项】",
        "1. 依赖真实模型 API 配置；当前演示环境未配置模型参数。",
        "2. 若模型调用失败，最终报告会被标记为待确认。",
        "",
        "【结果证据】",
        "1. 工具调用记录请参见任务详情页的每一步操作。",
        "2. 所有工具结果和错误状态已持久化到 SQLite。",
    ])

    return "\n".join(lines)
