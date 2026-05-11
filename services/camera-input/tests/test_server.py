"""Tests for camera_input.server WebSocket transport."""

from __future__ import annotations

import asyncio
import json
import socket

import pytest

from camera_input.server import serve_events


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _connect_with_retry(websockets, uri: str):
    last_error: Exception | None = None
    for _ in range(20):
        try:
            return await websockets.connect(uri)
        except OSError as exc:
            last_error = exc
            await asyncio.sleep(0.05)
    raise AssertionError(f"Timed out connecting to {uri}") from last_error


def test_websocket_client_receives_json_events():
    async def run() -> None:
        websockets = pytest.importorskip("websockets")
        port = _free_port()
        counter = {"value": 0}

        def next_event() -> dict:
            counter["value"] += 1
            return {
                "timestamp_ms": counter["value"],
                "players": [{"id": 1, "action": "jump", "confidence": 0.9}],
            }

        task = asyncio.create_task(
            serve_events(
                next_event,
                host="127.0.0.1",
                port=port,
                send_interval_seconds=0.01,
                idle_interval_seconds=0.01,
            )
        )
        try:
            async with (await _connect_with_retry(websockets, f"ws://127.0.0.1:{port}")) as websocket:
                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)

            payload = json.loads(message)
            assert payload["players"][0]["action"] == "jump"
            assert payload["players"][0]["confidence"] == 0.9
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())


def test_client_disconnect_does_not_stop_server():
    async def run() -> None:
        websockets = pytest.importorskip("websockets")
        port = _free_port()
        counter = {"value": 0}

        def next_event() -> dict:
            counter["value"] += 1
            return {
                "timestamp_ms": counter["value"],
                "type": "status",
                "players": [{"id": 1, "visible": True, "calibrated": True, "confidence": 0.8}],
            }

        task = asyncio.create_task(
            serve_events(
                next_event,
                host="127.0.0.1",
                port=port,
                send_interval_seconds=0.01,
                idle_interval_seconds=0.01,
            )
        )
        try:
            async with (await _connect_with_retry(websockets, f"ws://127.0.0.1:{port}")) as websocket:
                first = json.loads(await asyncio.wait_for(websocket.recv(), timeout=1.0))

            async with (await _connect_with_retry(websockets, f"ws://127.0.0.1:{port}")) as websocket:
                second = json.loads(await asyncio.wait_for(websocket.recv(), timeout=1.0))

            assert first["type"] == "status"
            assert second["type"] == "status"
            assert second["timestamp_ms"] > first["timestamp_ms"]
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())
