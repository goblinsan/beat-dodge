"""WebSocket transport for camera action events."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable, MutableSet
from typing import Any


JsonEventFactory = Callable[[], dict[str, Any]]


async def serve_events(
    event_factory: JsonEventFactory,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    send_interval_seconds: float = 0.0,
    idle_interval_seconds: float = 0.05,
    max_events: int | None = None,
) -> None:
    """Broadcast JSON events from *event_factory* to connected clients.

    The event factory is called by one producer task, so multiple WebSocket
    clients receive the same camera stream instead of causing extra camera
    reads.  ``max_events`` exists for integration tests and should normally be
    left unset.
    """

    try:
        import websockets
        from websockets.exceptions import ConnectionClosed
    except ImportError as exc:
        raise RuntimeError(
            "WebSocket mode requires the 'websockets' package. "
            "Install services/camera-input/requirements.txt."
        ) from exc

    clients: MutableSet[Any] = set()

    async def handler(websocket: Any) -> None:
        clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            clients.discard(websocket)

    async def producer() -> None:
        events_sent = 0
        while max_events is None or events_sent < max_events:
            payload = event_factory()
            if payload:
                events_sent += 1
                if clients:
                    message = json.dumps(payload)
                    stale_clients: set[Any] = set()
                    for websocket in list(clients):
                        try:
                            await websocket.send(message)
                        except ConnectionClosed:
                            stale_clients.add(websocket)
                    clients.difference_update(stale_clients)

            if clients:
                await asyncio.sleep(send_interval_seconds)
            else:
                await asyncio.sleep(idle_interval_seconds)

    print(f"Camera action WebSocket listening on ws://{host}:{port}", file=sys.stderr)
    async with websockets.serve(handler, host, port):
        await producer()


def run_event_server(
    event_factory: JsonEventFactory,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    send_interval_seconds: float = 0.0,
) -> None:
    """Blocking wrapper around :func:`serve_events`."""

    asyncio.run(
        serve_events(
            event_factory,
            host=host,
            port=port,
            send_interval_seconds=send_interval_seconds,
        )
    )
