"""Multi-turn chat that reuses the server-side chat id.

    python examples/multi_turn.py

© 3MH Technologies — https://3mh.pages.dev/ — https://t.me/j49_c
"""

from __future__ import annotations

import asyncio

from notrack import NotrackClient


async def main() -> None:
    chat_id: str | None = None

    async with NotrackClient() as client:
        for prompt in ("My name is Sam.", "What is my name?"):
            print(f"you> {prompt}")
            reply, chat_id = await client.complete(prompt, chat_id=chat_id)
            print(f"bot> {reply}\n")
            # chat_id now points at the server-side thread, so the second
            # turn sees the first — no local history management needed.


if __name__ == "__main__":
    asyncio.run(main())
