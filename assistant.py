"""命令行和网页共用的一轮对话。有密钥时走大模型，否则本地匹配工具。"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
from langchain_openai import ChatOpenAI

import mcp_server
from settings import current_model

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "mcp_server.py"

SYSTEM_PROMPT = """你是个人事务智能助手，拥有一组 MCP 工具，可以管理待办清单、查询城市天气。

## 可用工具
1. add_todo：添加一条待办事项
2. list_todos：列出全部待办事项
3. complete_todo：将指定 ID 待办标记为完成
4. delete_todo：删除指定 ID 的待办
5. get_weather：查询指定城市当前天气
6. export_todos：导出所有待办为 Markdown 文件

## 约束
1. 所有待办、天气信息必须调用工具获取，禁止凭空编造。
2. 思考过程不用展示给用户，只返回自然中文回答。
3. 用户如果指令模糊，主动询问补充信息。
   - 添加待办：确认待办内容
   - 查询天气：确认城市名称
   - 修改或删除待办：确认待办 ID
4. 导出完成后，告知用户生成的 md 文件名。
5. 用户输入 quit，结束对话。
6. 每一轮只要涉及待办或天气，都必须重新调用工具。对话历史不能代替工具结果，禁止照着历史编造编号、清单或天气。
"""


def build_llm() -> ChatOpenAI:
    config = current_model()
    if config is None:
        raise RuntimeError("没有可用的模型密钥")
    kwargs = {}
    if config.provider == "ark":
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    return ChatOpenAI(
        model=config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0,
        timeout=60,
        max_retries=0,
        **kwargs,
    )


async def answer(user_text: str, history: list[dict]) -> str:
    if current_model() is None:
        return local_answer(user_text)
    messages = [*history, {"role": "user", "content": user_text}]
    async with MCPAdapter(SERVER) as adapter:
        tools = await adapter.list_tools()
        agent = create_agent(build_llm(), tools, system_prompt=SYSTEM_PROMPT)
        result = await agent.ainvoke({"messages": messages})
        if _needs_tool(user_text) and not _tool_was_used(result["messages"]):
            nudged = [
                *messages,
                {
                    "role": "user",
                    "content": "请调用工具完成上面的请求。不要根据对话记录编造待办、编号或天气。",
                },
            ]
            result = await agent.ainvoke({"messages": nudged})
    if _needs_tool(user_text) and not _tool_was_used(result["messages"]):
        return local_answer(user_text)
    return extract_reply(result["messages"])


def _tool_was_used(messages) -> bool:
    return any(type(message).__name__ == "ToolMessage" for message in messages)


def _needs_tool(text: str) -> bool:
    if any(word in text for word in ("待办", "天气", "导出", "清单")):
        return True
    return bool(re.search(r"标记为?完成|删除", text))


def extract_reply(messages) -> str:
    for message in reversed(messages):
        if type(message).__name__ not in {"AIMessage", "AIMessageChunk"}:
            continue
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text") or "")
            text = "".join(parts).strip()
            if text:
                return text
    return "模型没有返回可展示的文字。"


def local_answer(user_text: str) -> str:
    text = user_text.strip()
    if not text:
        return "请输入内容。"
    todo_id = _id_of(text)
    if _is_export(text):
        return mcp_server.export_todos()
    if _is_complete(text) and todo_id is not None:
        return mcp_server.complete_todo(todo_id)
    if _is_delete(text) and todo_id is not None:
        return mcp_server.delete_todo(todo_id)
    if _is_list(text):
        return mcp_server.list_todos(_list_status(text))
    weather_city = _weather_city(text)
    if weather_city:
        return mcp_server.get_weather(weather_city)
    created = _new_todo(text)
    if created:
        content, due = created
        return mcp_server.add_todo(content, due)
    if todo_id is not None and ("完成" in text or "做完" in text):
        return mcp_server.complete_todo(todo_id)
    return (
        "当前环境没有读到 Cielo 的火山方舟密钥，也没有读到 DeepSeek 密钥，"
        "所以这一轮用本地规则调用了工具。可以直接说：\n"
        "· 帮我加一条待办：后天交数据库作业\n"
        "· 看看我有哪些待办\n"
        "· 把 1 标记为完成\n"
        "· 删除待办 1\n"
        "· 北京今天天气怎么样\n"
        "· 把待办导出成文件\n"
        "把密钥写进 .env 后，会改由大模型选择工具。"
    )


def _new_todo(text: str) -> tuple[str, str] | None:
    matched = re.search(
        r"(?:帮我)?(?:加一条|添加|新建|记一条|记录一条)待办[:：]?\s*(.+)",
        text,
    )
    if not matched:
        return None
    raw = matched.group(1).strip()
    due = ""
    today = date.today()
    dated = re.search(r"\d{4}-\d{2}-\d{2}", raw)
    if dated:
        due = dated.group(0)
        raw = raw.replace(due, "", 1)
    for word, delta in (("大后天", 3), ("后天", 2), ("明天", 1), ("今天", 0)):
        if word in raw:
            due = (today + timedelta(days=delta)).isoformat()
            raw = raw.replace(word, "", 1)
            break
    content = raw.strip(" ，,。")
    return (content, due) if content else None


def _is_list(text: str) -> bool:
    return bool(re.search(r"待办|清单", text) and re.search(r"看|列出|有哪些|查询|显示|全部|已完成", text))


def _list_status(text: str) -> str:
    if "已完成" in text or "完成了的" in text:
        return "completed"
    if "全部" in text or "所有" in text:
        return "all"
    return "pending"


def _is_complete(text: str) -> bool:
    return bool(re.search(r"标记为?完成|标为完成|设为完成|完成待办", text))


def _is_delete(text: str) -> bool:
    return "删除" in text and "待办" in text


def _is_export(text: str) -> bool:
    return "导出" in text


def _id_of(text: str) -> int | None:
    matched = re.search(r"\d+", text)
    return int(matched.group(0)) if matched else None


def _weather_city(text: str) -> str | None:
    if "天气" not in text:
        return None
    matched = re.search(r"([\u4e00-\u9fff]{2,8})(?:今天|现在|当前|的)?天气", text)
    if matched:
        city = matched.group(1)
        city = re.sub(r"^(查询|看看|帮我查|帮我看|请问)", "", city)
        return city or None
    matched = re.search(r"天气(?:怎么样|如何)?[:：]?\s*([\u4e00-\u9fff]{2,8})", text)
    return matched.group(1) if matched else None
