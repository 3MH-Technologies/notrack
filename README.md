# notrack

> Official Python SDK for the NoTrack dispatch API — streaming SSE chat, typed events, bounded retries, cookie auth.

**Install**

```bash
pip install notrack
# or from source
pip install "git+https://github.com/3MH-Technologies/notrack.git"
```

**Quickstart**

```python
import asyncio
from notrack import NotrackClient, Delta


async def main() -> None:
    async with NotrackClient() as client:
        async for ev in client.stream("Explain SSE in one sentence."):
            if isinstance(ev, Delta):
                print(ev.text, end="", flush=True)


asyncio.run(main())
```

Non-streaming helper:

```python
text, chat_id = await client.complete("hello", model="C", persona="coder")
```

---

## Why this SDK

- **Streaming first.** `POST /api/dispatch` replies with an SSE stream; the SDK parses it into typed events so your UI stays instant.
- **Typed events, no string matching.** `ChatMeta`, `Thinking`, `Delta`, `TurnEnd`, `ErrorEvent`, `Notice` — all frozen dataclasses with a `type` discriminator you can re-serialize with `to_dict()`.
- **Bounded, quiet retries.** HTTP 429 and in-stream `ratelimit` errors back off linearly (`attempt × rate_limit_backoff`); transient network errors retry up to 3 times. Permanent failures raise `NotrackError` subclasses with machine-readable `code`s.
- **Cookie auth, zero key management.** Drop a browser-style cookie string into `NOTRACK_COOKIE` and it's attached to every request. No API keys, no vendor branding in your payloads.
- **Fully typed** (`py.typed`), async-native, and dependency-light: only [`httpx`](https://www.python-httpx.org/).
- **Testable by design.** Pass `transport=` to swap in an `httpx.MockTransport` — the entire test suite runs offline.

## Configuration

Every setting is available programmatically (`NotrackConfig(...)`) or via environment variables:

| Env var | Purpose | Default |
|---|---|---|
| `NOTRACK_BASE` | Service base URL | `https://notrack.ai` |
| `NOTRACK_COOKIE` | Browser-style cookie string (`k1=v1; k2=v2`) | *(empty)* |
| `NOTRACK_MODEL` | Default model code `A`/`B`/`C`/`F` | `C` |
| `NOTRACK_PERSONA` | `normal`, `creative`, `precise`, `concise`, `socratic`, `tutor`, `coder` | `normal` |
| `NOTRACK_MAX_TURNS` | Agent turns per dispatch | `6` |
| `NOTRACK_TIMEOUT` | Read timeout (seconds) | `120` |
| `NOTRACK_MAX_ATTEMPTS` | Rate-limit retry attempts | `5` |

```python
from notrack import NotrackClient, NotrackConfig

client = NotrackClient(NotrackConfig(base_url="https://upstream.internal", max_turns=8))
```

Copy `.env.example` to `.env` to get started.

## Model catalogue

| Code | Name | Description |
|---|---|---|
| `A` | AI-Minimax | Fast internal model |
| `B` | AI-ChatGPT | General-purpose internal model |
| `C` | NoTrack | Balanced internal model (default) |
| `F` | Synthesis | Multi-model internal synthesis |

Display names are the upstream service's own labels — applications are free to rebrand them (the **worm-ai** platform publishes them as *Worm Core / Pro / Flash / Synth*).

## Event stream

```
chat_meta → thinking → delta* → turn_end → … → (end)
```

| Wire event | SDK type | Notes |
|---|---|---|
| `chat_meta` | `ChatMeta` | First event; carries the server-side `chat_id` to reuse next turn |
| `thinking` | `Thinking` | A model is preparing a turn (`speaker` = model code) |
| `delta` | `Delta` | Incremental text — append to the visible reply |
| `message` / `consensus` | `Delta` + `TurnEnd` | Full content fallback when no deltas preceded it |
| `error` | `ErrorEvent` | Yielded by `stream()`, **raised** by `complete()` |
| `ctx_cut` / `busy` | `Notice` | Non-fatal information |

Unknown and malformed events are logged at `DEBUG` and skipped — one bad line never kills a stream.

## Error handling

```python
from notrack import (
    NotrackError,  # base class — catch this
    NotrackRateLimitError,  # 429 / in-stream ratelimit, retries exhausted
    NotrackTransportError,  # network failures, retries exhausted
    NotrackAPIError,  # non-200 response (.status_code)
    NotrackConfigError,  # invalid configuration
)

try:
    text, _ = await client.complete("hi")
except NotrackRateLimitError:
    ...  # back off and re-prompt the user
except NotrackError as exc:
    log.warning("notrack failed (code=%s): %s", exc.code, exc)
```

## Process-wide client

```python
from notrack import get_client

client = get_client()  # singleton — built from NOTRACK_* env on first use
```

One client per process is enough; it keeps the cookie jar and connection pool warm.

## Development

```bash
pip install -e ".[dev]"

pytest                 # offline test suite (MockTransport)
ruff check .           # lint
ruff format .          # format
mypy                   # strict type checking
python -m build        # build sdist + wheel
```

CI runs all four on every push (`.github/workflows/ci.yml`).

## Credits

© 3MH Technologies — https://3mh.pages.dev/ — https://t.me/j49_c

MIT License — see [LICENSE](LICENSE).
