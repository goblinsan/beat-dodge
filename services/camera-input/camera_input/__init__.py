"""camera_input — Python camera input service for Beat Dodge.

Exports are loaded lazily so tests can import pure data/model modules without
requiring OpenCV, MediaPipe, or display libraries to be installed first.
"""

__all__ = [
    "CameraCapture",
    "CameraUnavailableError",
    "LandmarkPoint",
    "PoseDetector",
    "PoseResult",
    "REQUIRED_LANDMARKS",
    "PlayerData",
    "assign_players",
    "draw_lane_boundaries",
    "draw_player_labels",
    "draw_skeleton",
]


def __getattr__(name: str):
    if name in {"CameraCapture", "CameraUnavailableError"}:
        from camera_input.capture import CameraCapture, CameraUnavailableError

        return {
            "CameraCapture": CameraCapture,
            "CameraUnavailableError": CameraUnavailableError,
        }[name]
    if name in {"LandmarkPoint", "PoseDetector", "PoseResult", "REQUIRED_LANDMARKS"}:
        from camera_input.detector import (
            LandmarkPoint,
            PoseDetector,
            PoseResult,
            REQUIRED_LANDMARKS,
        )

        return {
            "LandmarkPoint": LandmarkPoint,
            "PoseDetector": PoseDetector,
            "PoseResult": PoseResult,
            "REQUIRED_LANDMARKS": REQUIRED_LANDMARKS,
        }[name]
    if name in {"PlayerData", "assign_players"}:
        from camera_input.players import PlayerData, assign_players

        return {
            "PlayerData": PlayerData,
            "assign_players": assign_players,
        }[name]
    if name in {"draw_lane_boundaries", "draw_player_labels", "draw_skeleton"}:
        from camera_input.overlay import (
            draw_lane_boundaries,
            draw_player_labels,
            draw_skeleton,
        )

        return {
            "draw_lane_boundaries": draw_lane_boundaries,
            "draw_player_labels": draw_player_labels,
            "draw_skeleton": draw_skeleton,
        }[name]
    raise AttributeError(f"module 'camera_input' has no attribute {name!r}")
