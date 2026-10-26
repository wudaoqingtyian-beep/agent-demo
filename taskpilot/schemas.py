"""Pydantic 数据模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    user_task: str = Field(..., min_length=1, max_length=2000)


class TaskResponse(BaseModel):
    id: str
    user_task: str
    status: str
    created_at: str
    ended_at: str | None
    error: str | None
    final_report: str | None

    class Config:
        from_attributes = True


class StepResponse(BaseModel):
    seq: int
    name: str
    detail: str


class ToolCallResponse(BaseModel):
    tool_name: str
    params: str
    result_text: str | None
    error_text: str | None


class TaskDetailsResponse(BaseModel):
    id: str
    user_task: str
    status: str
    created_at: str
    ended_at: str | None
    error: str | None
    final_report: str | None
    steps: list[StepResponse]
    tools_by_step: dict[int, list[ToolCallResponse]]

    class Config:
        from_attributes = True


class TaskSummary(BaseModel):
    id: str
    user_task: str
    status: str
    created_at: str
    ended_at: str | None

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
