"""命令行版个人事务智能助手。"""

from __future__ import annotations

import asyncio

from assistant import answer
from settings import provider_label

QUIT = {"quit", "exit", "q"}


async def chat_loop() -> None:
    history: list[dict] = []
    print(f"个人事务智能助手已就绪（{provider_label()}）")
    print("输入 quit 退出。")
    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return
        if not user_input:
            continue
        if user_input.lower() in QUIT:
            print("再见。")
            return
        try:
            reply = await answer(user_input, history)
        except Exception as exc:
            print(f"\n调用失败：{exc}")
            continue
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})
        print(f"\n助手: {reply}")


if __name__ == "__main__":
    asyncio.run(chat_loop())
