"""WebSocket transport for camera action events."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable
from typing import Any


JsonEventFactory = Callable[[], dict[str, Any]]


async def serve_events(
    event_factory: JsonEventFactory,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Serve JSON events from *event_factory* to one WebSocket client at a time."""

    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError(
            "WebSocket mode requires the 'websockets' package. "
            "Install services/camera-input/requirements.txt."
        ) from exc

    async def handler(websocket: Any) -> None:
        while True:
            payload = event_factory()
            await websocket.send(json.dumps(payload))
            await asyncio.sleep(0)

    print(f"Camera action WebSocket listening on ws://{host}:{port}", file=sys.stderr)
    async with websockets.serve(handler, host, port):
        await asyncio.Future()


def run_event_server(
    event_factory: JsonEventFactory,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Blocking wrapper around :func:`serve_events`."""

    asyncio.run(serve_events(event_factory, host=host, port=port))
