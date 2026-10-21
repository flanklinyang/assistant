"""个人事务助手的 MCP 工具服务。"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import requests
from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("TODO_DB_PATH", ROOT / "todos.db"))

mcp = FastMCP("个人事务助手工具集")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS todos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            due_date TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def init_db() -> None:
    with connect():
        return


def add_todo(content: str, due_date: str = "") -> str:
    """添加一条待办事项。

    Args:
        content: 待办事项的内容描述
        due_date: 截止日期，格式为 YYYY-MM-DD，不填则无截止日期
    """
    text = (content or "").strip()
    if not text:
        return "没有写待办内容。"
    due = (due_date or "").strip()
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO todos (content, due_date) VALUES (?, ?)",
            (text, due),
        )
        todo_id = cursor.lastrowid
    return f"已添加待办 [{todo_id}]：{text}（截止：{due or '未设定'}）"


def list_todos(status: str = "pending") -> str:
    """列出待办事项。

    Args:
        status: 筛选状态，可选 pending（未完成）、completed（已完成）、all（全部）
    """
    chosen = (status or "pending").strip().lower()
    if chosen not in {"pending", "completed", "all"}:
        return "状态只能是 pending、completed 或 all。"
    with connect() as conn:
        if chosen == "all":
            rows = conn.execute(
                "SELECT id, content, due_date, status FROM todos ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, content, due_date, status FROM todos WHERE status = ? ORDER BY id",
                (chosen,),
            ).fetchall()
    if not rows:
        return "当前没有符合条件的待办事项。"
    lines = []
    for row in rows:
        mark = "✅" if row["status"] == "completed" else "⬜"
        lines.append(f"{mark} [{row['id']}] {row['content']}  |  截止: {row['due_date'] or '—'}")
    return "\n".join(lines)


def complete_todo(todo_id: int) -> str:
    """将指定 ID 的待办事项标记为已完成。

    Args:
        todo_id: 待办事项的 ID 编号
    """
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE todos SET status = 'completed' WHERE id = ?",
            (int(todo_id),),
        )
        changed = cursor.rowcount
    if changed == 0:
        return f"没有找到 ID 为 {todo_id} 的待办事项。"
    return f"待办 [{todo_id}] 已标记为完成 ✅"


def delete_todo(todo_id: int) -> str:
    """删除指定 ID 的待办事项。

    Args:
        todo_id: 待办事项的 ID 编号
    """
    with connect() as conn:
        cursor = conn.execute("DELETE FROM todos WHERE id = ?", (int(todo_id),))
        changed = cursor.rowcount
    if changed == 0:
        return f"没有找到 ID 为 {todo_id} 的待办事项。"
    return f"待办 [{todo_id}] 已删除 🗑️"


def get_weather(city: str) -> str:
    """查询指定城市的当前天气信息。

    Args:
        city: 城市名称，例如 北京、上海、广州
    """
    name = (city or "").strip()
    if not name:
        return "请告诉我要查询的城市。"
    try:
        response = requests.get(
            f"https://wttr.in/{name}?format=j1",
            timeout=8,
            headers={"User-Agent": "astra-todo-agent"},
        )
        response.raise_for_status()
        current = response.json()["current_condition"][0]
        desc = current["weatherDesc"][0]["value"]
        return (
            f"📍 {name} 当前天气：{desc}，"
            f"温度 {current['temp_C']}°C，"
            f"体感 {current['FeelsLikeC']}°C，"
            f"湿度 {current['humidity']}%，"
            f"风速 {current['windspeedKmph']} km/h"
        )
    except Exception as exc:
        return f"天气查询失败：{exc}"


def export_todos(filepath: str = "todos_export.md") -> str:
    """将当前所有待办事项导出为 Markdown 文件。

    Args:
        filepath: 导出的文件路径，默认为 todos_export.md
    """
    target = _export_path(filepath)
    with connect() as conn:
        rows = conn.execute(
            "SELECT content, due_date, status FROM todos ORDER BY id"
        ).fetchall()
    lines = [
        "# 📋 待办清单",
        "",
        f"> 导出时间：{datetime.now():%Y-%m-%d %H:%M}",
        "",
    ]
    for row in rows:
        mark = "x" if row["status"] == "completed" else " "
        lines.append(f"- [{mark}] {row['content']}  (截止: {row['due_date'] or '—'})")
    if not rows:
        lines.append("- （没有待办）")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"已导出 {len(rows)} 条待办到 {target.name}"


def _export_path(filepath: str) -> Path:
    raw = (filepath or "todos_export.md").strip() or "todos_export.md"
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError("导出路径请使用文件名，不要写绝对路径。")
    target = (ROOT / candidate).resolve()
    if ROOT not in target.parents and target != ROOT:
        raise ValueError("导出路径不能离开项目目录。")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


mcp.tool()(add_todo)
mcp.tool()(list_todos)
mcp.tool()(complete_todo)
mcp.tool()(delete_todo)
mcp.tool()(get_weather)
mcp.tool()(export_todos)

init_db()


if __name__ == "__main__":
    init_db()
    mcp.run()
