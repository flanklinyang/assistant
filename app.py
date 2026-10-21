"""Gradio 网页版个人事务智能助手。"""

from __future__ import annotations

import asyncio
import os
import threading

import gradio as gr

from assistant import answer
from settings import provider_label

_memory: list[dict] = []
_bg_loop = asyncio.new_event_loop()


def _run_bg_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


_bg_thread = threading.Thread(target=_run_bg_loop, args=(_bg_loop,), daemon=True)
_bg_thread.start()


async def handle_message(user_message: str) -> str:
    reply = await answer(user_message, _memory)
    _memory.append({"role": "user", "content": user_message})
    _memory.append({"role": "assistant", "content": reply})
    if len(_memory) > 40:
        del _memory[:-40]
    return reply


def chat(message, history):
    del history
    future = asyncio.run_coroutine_threadsafe(handle_message(message), _bg_loop)
    try:
        return future.result(timeout=180)
    except Exception as exc:
        return f"调用失败：{type(exc).__name__}: {exc}"


demo = gr.ChatInterface(
    fn=chat,
    title="个人事务智能助手 3.0-Astra",
    description=(
        f"当前模型：{provider_label()}。"
        "我可以帮你管理待办、查询天气、导出清单。"
        "试试说「帮我加一条待办：明天开会」。"
    ),
    examples=[
        "帮我加一条待办：后天交数据库作业",
        "看看我有哪些待办",
        "北京今天天气怎么样",
        "把待办导出成文件",
    ],
    concurrency_limit=1,
)


if __name__ == "__main__":
    demo.launch(
        server_name=os.environ.get("GRADIO_HOST", "0.0.0.0"),
        server_port=int(os.environ.get("GRADIO_PORT", "7860")),
    )
