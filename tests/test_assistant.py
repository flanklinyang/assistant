import asyncio
from pathlib import Path

import mcp_server
from assistant import local_answer
from langchain.mcp import MCPAdapter


def use_db(tmp_path: Path) -> None:
    mcp_server.DB_PATH = tmp_path / "todos.db"
    if mcp_server.DB_PATH.exists():
        mcp_server.DB_PATH.unlink()
    mcp_server.init_db()


def test_todo_lifecycle(tmp_path: Path):
    use_db(tmp_path)
    created = local_answer("帮我加一条待办：后天交数据库作业")
    assert "已添加待办 [1]" in created
    assert "交数据库作业" in created
    listed = local_answer("看看我有哪些待办")
    assert "⬜ [1]" in listed
    assert local_answer("把 1 标记为完成").startswith("待办 [1] 已标记为完成")
    assert "没有符合条件" in local_answer("看看我有哪些待办")
    assert "✅ [1]" in local_answer("看看已完成的待办")
    assert "已删除" in local_answer("删除待办 1")
    assert "没有找到" in local_answer("删除待办 9")


def test_export_stays_in_project(tmp_path: Path):
    use_db(tmp_path)
    local_answer("添加待办：复习软件工程")
    exported = local_answer("把待办导出成文件")
    page = mcp_server.ROOT / "todos_export.md"
    assert "todos_export.md" in exported
    assert "复习软件工程" in page.read_text(encoding="utf-8")
    page.unlink()
    try:
        mcp_server.export_todos("../../etc/passwd")
    except ValueError as exc:
        assert "离开项目目录" in str(exc)
    else:
        raise AssertionError("越界导出应被拒绝")


def test_weather_and_unclear_request():
    reply = local_answer("北京今天天气怎么样")
    assert "北京" in reply
    assert "°C" in reply
    vague = local_answer("你好")
    assert "密钥" in vague


def test_mcp_lists_six_tools():
    async def scenario():
        adapter = MCPAdapter(mcp_server.ROOT / "mcp_server.py")
        tools = await adapter.list_tools()
        return sorted(tool.name for tool in tools)

    names = asyncio.run(scenario())
    assert names == [
        "add_todo",
        "complete_todo",
        "delete_todo",
        "export_todos",
        "get_weather",
        "list_todos",
    ]


def test_explicit_date_is_stored(tmp_path: Path):
    use_db(tmp_path)
    created = local_answer("帮我加一条待办：2026-10-26 复习操作系统第五章")
    assert "2026-10-26" in created
    assert "复习操作系统第五章" in created
    row = mcp_server.connect().execute("SELECT content, due_date FROM todos").fetchone()
    assert row["content"] == "复习操作系统第五章"
    assert row["due_date"] == "2026-10-26"


def test_model_reply_without_tool_uses_database(tmp_path: Path, monkeypatch):
    use_db(tmp_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

    class FakeAdapter:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def list_tools(self):
            return []

    class FakeAgent:
        async def ainvoke(self, payload):
            del payload
            return {"messages": [type("AIMessage", (), {"content": "已添加待办 [9]：虚构事项"})()]}

    import assistant

    monkeypatch.setattr(assistant, "MCPAdapter", lambda path: FakeAdapter())
    monkeypatch.setattr(assistant, "create_agent", lambda *args, **kwargs: FakeAgent())
    monkeypatch.setattr(assistant, "build_llm", lambda: object())

    reply = asyncio.run(assistant.answer("帮我加一条待办：2026-12-01 交实验报告", []))
    assert "虚构" not in reply
    assert "已添加待办 [1]" in reply
    row = mcp_server.connect().execute("SELECT content, due_date FROM todos").fetchone()
    assert row["content"] == "交实验报告"
    assert row["due_date"] == "2026-12-01"
