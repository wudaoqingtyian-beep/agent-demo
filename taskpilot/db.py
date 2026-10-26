"""SQLite 数据访问层。

保存任务、步骤、工具调用、错误和最终报告。运行时通过 taskpilot.main 创建数据库连接。
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from taskpilot.config import DB_PATH

_thread_local = threading.local()


def get_db() -> sqlite3.Connection:
    """返回当前线程的 SQLite 连接（线程隔离，避免并发写入锁定）。"""
    conn = getattr(_thread_local, "db", None)
    if conn is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _init_db(conn)
        _thread_local.db = conn
    return conn


def close_db() -> None:
    conn = getattr(_thread_local, "db", None)
    if conn is not None:
        try:
            conn.close()
        finally:
            _thread_local.db = None


@contextmanager
def db_cursor():
    conn = get_db()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            user_task TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ended_at TEXT,
            error TEXT,
            final_report TEXT
        );

        CREATE TABLE IF NOT EXISTS steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            seq INTEGER NOT NULL,
            name TEXT NOT NULL,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            step_id INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            params TEXT NOT NULL,
            result_text TEXT,
            error_text TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (step_id) REFERENCES steps(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_steps_task ON steps(task_id);
        CREATE INDEX IF NOT EXISTS idx_tools_step ON tool_calls(step_id);
        """
    )


@dataclass
class Step:
    id: int
    task_id: str
    seq: int
    name: str
    detail: str
    created_at: str


@dataclass
class ToolCall:
    id: int
    step_id: int
    tool_name: str
    params: str
    result_text: str | None
    error_text: str | None
    created_at: str


@dataclass
class TaskRecord:
    id: str
    user_task: str
    status: str
    created_at: str
    ended_at: str | None
    error: str | None
    final_report: str | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_task(user_task: str, status: str = "pending") -> TaskRecord:
    task_id = _generate_id()
    now = _now()
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO tasks (id, user_task, status, created_at, ended_at, error, final_report)
            VALUES (?, ?, ?, ?, NULL, NULL, NULL)
            """,
            (task_id, user_task, status, now),
        )
    return get_task(task_id)


def update_task_status(task_id: str, status: str, error: str | None = None) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE tasks SET status = ?, ended_at = ?, error = ? WHERE id = ?",
            (status, _now(), error, task_id),
        )


def update_task_report(task_id: str, report: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE tasks SET final_report = ? WHERE id = ?",
            (report, task_id),
        )


def add_step(task_id: str, seq: int, name: str, detail: str) -> Step:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO steps (task_id, seq, name, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, seq, name, detail, _now()),
        )
        step_id = cur.lastrowid
    return Step(
        id=step_id,
        task_id=task_id,
        seq=seq,
        name=name,
        detail=detail,
        created_at=_now(),
    )


def add_tool_call(step_id: int, tool_name: str, params: str,
                  result_text: str | None = None, error_text: str | None = None) -> ToolCall:
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO tool_calls (step_id, tool_name, params, result_text, error_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (step_id, tool_name, params, result_text, error_text, _now()),
        )
        tool_id = cur.lastrowid
    return ToolCall(
        id=tool_id,
        step_id=step_id,
        tool_name=tool_name,
        params=params,
        result_text=result_text,
        error_text=error_text,
        created_at=_now(),
    )


def get_task_details(task_id: str) -> dict[str, Any] | None:
    task = get_task(task_id)
    if task is None:
        return None
    with db_cursor() as cur:
        rows = cur.execute(
            """
            SELECT seq, name, detail FROM steps
            WHERE task_id = ? ORDER BY seq ASC
            """,
            (task_id,),
        ).fetchall()
        steps = [
            {"seq": r["seq"], "name": r["name"], "detail": r["detail"]}
            for r in rows
        ]
        tool_rows = cur.execute(
            """
            SELECT tc.step_id, tc.tool_name, tc.params, tc.result_text, tc.error_text
            FROM tool_calls tc
            JOIN steps s ON s.id = tc.step_id
            WHERE s.task_id = ?
            ORDER BY tc.step_id ASC, tc.id ASC
            """,
            (task_id,),
        ).fetchall()

    grouped = {}
    for r in tool_rows:
        grouped.setdefault(r["step_id"], []).append({
            "tool_name": r["tool_name"],
            "params": r["params"],
            "result_text": r["result_text"],
            "error_text": r["error_text"],
        })
    tools_by_step = {k: v for k, v in grouped.items()}

    return {
        "id": task.id,
        "user_task": task.user_task,
        "status": task.status,
        "created_at": task.created_at,
        "ended_at": task.ended_at,
        "error": task.error,
        "final_report": task.final_report,
        "steps": steps,
        "tools_by_step": tools_by_step,
    }


def list_tasks(limit: int = 50, offset: int = 0) -> list[TaskRecord]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [
        TaskRecord(
            id=r["id"],
            user_task=r["user_task"],
            status=r["status"],
            created_at=r["created_at"],
            ended_at=r["ended_at"],
            error=r["error"],
            final_report=r["final_report"],
        )
        for r in rows
    ]


def _generate_id() -> str:
    import uuid
    return uuid.uuid4().hex


def get_task(task_id: str) -> TaskRecord | None:
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if row is None:
        return None
    return TaskRecord(
        id=row["id"],
        user_task=row["user_task"],
        status=row["status"],
        created_at=row["created_at"],
        ended_at=row["ended_at"],
        error=row["error"],
        final_report=row["final_report"],
    )
