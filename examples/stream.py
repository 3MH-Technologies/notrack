"""Stream a reply token-by-token.

    python examples/stream.py "Explain SSE in one sentence."

© 3MH Technologies — https://3mh.pages.dev/ — https://t.me/j49_c
"""

from __future__ import annotations

import asyncio
import sys

from notrack import ChatMeta, Delta, Notice, NotrackClient, Thinking, TurnEnd


async def main() -> None:
    prompt = " ".join(sys.argv[1:]) or "Hello!"

    async with NotrackClient() as client:
        async for ev in client.stream(prompt, model="C", persona="normal"):
            match ev:
                case Delta(text=text):
                    print(text, end="", flush=True)
                case TurnEnd():
                    print("\n" + "-" * 40)
                case ChatMeta(chat_id=chat_id):
                    print(f"[chat: {chat_id}]", file=sys.stderr)
                case Thinking(speaker=speaker):
                    print(f"[thinking: {speaker}]", file=sys.stderr)
                case Notice(kind=kind, message=message):
                    print(f"[notice: {kind} {message}]", file=sys.stderr)
        print()


if __name__ == "__main__":
    asyncio.run(main())
