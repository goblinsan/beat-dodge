"""CLI entry point for the camera-input service.

Usage
-----
    capture-pose [--device N] [--debug] [--max-frames N]

    python -m camera_input.cli [--device N] [--debug] [--max-frames N]

Each frame emits one JSON line to stdout conforming to
``docs/schemas/camera-frame.schema.json``.
"""

from __future__ import annotations

import argparse
import json
import sys

from camera_input.capture import CameraCapture, CameraUnavailableError
from camera_input.detector import PoseDetector
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

    frame_count = 0
    with capture, PoseDetector() as detector:
        while True:
            timestamp_ms, frame = capture.read_frame()
            if frame is None:
                print("Warning: Failed to read frame.", file=sys.stderr)
                continue

            left_pose, right_pose = detector.detect(frame)
            players = assign_players(left_pose, right_pose)

            frame_data = {
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
            print(json.dumps(frame_data), flush=True)

            if debug:
                import cv2
                from camera_input.overlay import (
                    draw_lane_boundaries,
                    draw_player_labels,
                    draw_skeleton,
                )

                draw_lane_boundaries(frame)
                draw_skeleton(frame, left_pose, player_id=1)
                draw_skeleton(frame, right_pose, player_id=2)
                draw_player_labels(frame, players)
                cv2.imshow("Beat Dodge - Camera Input", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            frame_count += 1
            if args.max_frames is not None and frame_count >= args.max_frames:
                break

    if debug:
        import cv2
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
