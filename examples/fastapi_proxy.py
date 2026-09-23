"""Proxy the SDK's SSE stream to a browser through FastAPI.

    uvicorn examples.fastapi_proxy:app --port 8000

The browser connects to GET /chat (text/event-stream) and receives the
same typed events re-serialized with notrack.to_dict().

© 3MH Technologies — https://3mh.pages.dev/ — https://t.me/j49_c
"""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from notrack import NotrackClient, to_dict

app = FastAPI(title="notrack proxy example")
_client = NotrackClient()


class Ask(BaseModel):
    prompt: str
    model: str = "C"
    persona: str = "normal"
    chat_id: str | None = None


@app.post("/ask")
async def ask(body: Ask) -> StreamingResponse:
    async def event_gen():
        async for ev in _client.stream(
            body.prompt,
            chat_id=body.chat_id,
            model=body.model,
            persona=body.persona,
        ):
            payload = to_dict(ev)
            yield f"event: {payload['type']}\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.on_event("shutdown")
async def shutdown() -> None:
    await _client.aclose()
