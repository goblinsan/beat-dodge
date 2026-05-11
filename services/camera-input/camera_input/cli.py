"""CLI entry point for the camera-input service.

Usage
-----
    capture-pose [--device N] [--debug] [--actions] [--websocket]

    python -m camera_input.cli [--device N] [--debug] [--max-frames N]

By default, each frame emits one JSON line to stdout conforming to
``docs/schemas/camera-frame.schema.json``.  With ``--actions``, the service
emits sparse gameplay actions conforming to
``docs/schemas/camera-action.schema.json``.  With ``--websocket``, action
events are served over WebSocket for the Godot runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any

from camera_input.capture import CameraCapture, CameraUnavailableError
from camera_input.detector import PoseDetector
from camera_input.movement import (
    MovementClassifier,
    action_event_payload,
    status_event_payload,
)
from camera_input.players import assign_players


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments, open the webcam, and stream frame JSON to stdout."""
    parser = argparse.ArgumentParser(
        prog="capture-pose",
        description=(
            "Capture webcam frames and emit player pose data as JSON lines, "
            "one object per frame, conforming to camera-frame.schema.json."
        ),
    )
    parser.add_argument(
        "--device",
        type=int,
        default=0,
        metavar="N",
        help="Camera device index (default: 0).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show a debug window with skeleton overlay and lane boundaries.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        metavar="N",
        help="Stop after N frames (default: run until Ctrl-C or 'q' in debug window).",
    )
    parser.add_argument(
        "--actions",
        action="store_true",
        help="Emit camera action events instead of raw frame telemetry.",
    )
    parser.add_argument(
        "--websocket",
        action="store_true",
        help="Serve camera action events over WebSocket instead of printing JSON lines.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="WebSocket host when --websocket is enabled (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="WebSocket port when --websocket is enabled (default: 8765).",
    )
    parser.add_argument(
        "--calibration-frames",
        type=int,
        default=20,
        metavar="N",
        help="Visible standing frames to collect before action detection (default: 20).",
    )
    parser.add_argument(
        "--min-action-confidence",
        type=float,
        default=0.55,
        metavar="N",
        help="Minimum action confidence to emit, 0-1 (default: 0.55).",
    )

    args = parser.parse_args(argv)

    try:
        capture = CameraCapture(args.device)
    except CameraUnavailableError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    debug = args.debug
    if debug:
        try:
            import cv2  # noqa: F401 – verify display is available
            from camera_input.overlay import (
                draw_lane_boundaries,
                draw_player_labels,
                draw_skeleton,
            )
        except ImportError as exc:
            print(f"Warning: Cannot enable debug overlay: {exc}", file=sys.stderr)
            debug = False

    classifier = MovementClassifier(
        calibration_frames=args.calibration_frames,
        min_confidence=args.min_action_confidence,
    )

    try:
        with capture, PoseDetector() as detector:
            next_event = _make_event_reader(
                capture=capture,
                detector=detector,
                classifier=classifier,
                debug=debug,
                emit_actions=args.actions or args.websocket,
            )

            if args.websocket:
                from camera_input.server import run_event_server

                try:
                    run_event_server(next_event, host=args.host, port=args.port)
                except RuntimeError as exc:
                    print(f"Error: {exc}", file=sys.stderr)
                    sys.exit(1)
            else:
                frame_count = 0
                while True:
                    payload = next_event()
                    if payload:
                        print(json.dumps(payload), flush=True)

                    frame_count += 1
                    if args.max_frames is not None and frame_count >= args.max_frames:
                        break
    except KeyboardInterrupt:
        pass
    finally:
        if debug:
            cv2.destroyAllWindows()


def _make_event_reader(
    *,
    capture: CameraCapture,
    detector: PoseDetector,
    classifier: MovementClassifier,
    debug: bool,
    emit_actions: bool,
) -> Callable[[], dict[str, Any]]:
    if debug:
        import cv2
        from camera_input.overlay import (
            draw_lane_boundaries,
            draw_player_labels,
            draw_skeleton,
        )

    def read_event() -> dict[str, Any]:
        timestamp_ms, frame = capture.read_frame()
        if frame is None:
            print("Warning: Failed to read frame.", file=sys.stderr)
            return {}

        left_pose, right_pose = detector.detect(frame)
        players = assign_players(left_pose, right_pose)

        actions = classifier.update(timestamp_ms, players)
        payload: dict[str, Any]
        if emit_actions:
            if actions:
                payload = action_event_payload(timestamp_ms, actions)
            else:
                payload = status_event_payload(timestamp_ms, classifier.status)
        else:
            payload = _frame_payload(timestamp_ms, players)

        if debug:
            draw_lane_boundaries(frame)
            draw_skeleton(frame, left_pose, player_id=1)
            draw_skeleton(frame, right_pose, player_id=2)
            draw_player_labels(frame, players)
            cv2.imshow("Beat Dodge - Camera Input", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                raise KeyboardInterrupt

        return payload

    return read_event


def _frame_payload(timestamp_ms: int, players: list[Any]) -> dict[str, Any]:
    return {
        "timestamp_ms": timestamp_ms,
        "players": [
            {
                "player_id": p.player_id,
                "visible": p.visible,
                "x": p.x,
                "y": p.y,
            }
            for p in players
        ],
    }


if __name__ == "__main__":
    main()
