"""camera_input — Python camera input service for Beat Dodge."""

from camera_input.capture import CameraCapture, CameraUnavailableError
from camera_input.detector import (
    LandmarkPoint,
    PoseDetector,
    PoseResult,
    REQUIRED_LANDMARKS,
)
from camera_input.players import PlayerData, assign_players
from camera_input.overlay import (
    draw_lane_boundaries,
    draw_player_labels,
    draw_skeleton,
)

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
