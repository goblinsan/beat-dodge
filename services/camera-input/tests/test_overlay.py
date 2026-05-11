"""Tests for camera_input.overlay (draw_skeleton, draw_lane_boundaries,
draw_player_labels)."""

from __future__ import annotations

from unittest.mock import call, patch, MagicMock

import numpy as np
import pytest

from camera_input.detector import LandmarkPoint, PoseResult
from camera_input.players import PlayerData
from camera_input.overlay import (
    PLAYER_COLORS,
    SKELETON_CONNECTIONS,
    draw_lane_boundaries,
    draw_player_labels,
    draw_skeleton,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank_frame(h: int = 480, w: int = 640) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _visible_pose() -> PoseResult:
    """PoseResult with all required landmarks set to visible."""
    lms = {
        "nose": LandmarkPoint(x=0.25, y=0.1, visibility=0.95),
        "left_shoulder": LandmarkPoint(x=0.15, y=0.3, visibility=0.95),
        "right_shoulder": LandmarkPoint(x=0.35, y=0.3, visibility=0.95),
        "left_hip": LandmarkPoint(x=0.15, y=0.55, visibility=0.95),
        "right_hip": LandmarkPoint(x=0.35, y=0.55, visibility=0.95),
        "left_knee": LandmarkPoint(x=0.15, y=0.75, visibility=0.95),
        "right_knee": LandmarkPoint(x=0.35, y=0.75, visibility=0.95),
        "left_ankle": LandmarkPoint(x=0.15, y=0.9, visibility=0.95),
        "right_ankle": LandmarkPoint(x=0.35, y=0.9, visibility=0.95),
        "left_elbow": LandmarkPoint(x=0.1, y=0.4, visibility=0.95),
        "right_elbow": LandmarkPoint(x=0.4, y=0.4, visibility=0.95),
        "left_wrist": LandmarkPoint(x=0.08, y=0.5, visibility=0.95),
        "right_wrist": LandmarkPoint(x=0.42, y=0.5, visibility=0.95),
    }
    return PoseResult(landmarks=lms)


def _invisible_pose() -> PoseResult:
    """PoseResult where all landmarks are below the visibility threshold."""
    lms = {
        "nose": LandmarkPoint(x=0.25, y=0.1, visibility=0.1),
        "left_hip": LandmarkPoint(x=0.2, y=0.5, visibility=0.1),
        "right_hip": LandmarkPoint(x=0.3, y=0.5, visibility=0.1),
    }
    return PoseResult(landmarks=lms)


# ---------------------------------------------------------------------------
# draw_skeleton tests
# ---------------------------------------------------------------------------

class TestDrawSkeleton:
    def test_returns_same_frame_object(self):
        frame = _blank_frame()
        result = draw_skeleton(frame, None)
        assert result is frame

    def test_noop_when_pose_is_none(self):
        with patch("camera_input.overlay.cv2") as mock_cv2:
            draw_skeleton(_blank_frame(), None)
            mock_cv2.line.assert_not_called()
            mock_cv2.circle.assert_not_called()

    def test_draws_lines_for_visible_connections(self):
        with patch("camera_input.overlay.cv2") as mock_cv2:
            draw_skeleton(_blank_frame(), _visible_pose(), player_id=1)
            assert mock_cv2.line.call_count > 0

    def test_draws_circles_for_visible_landmarks(self):
        with patch("camera_input.overlay.cv2") as mock_cv2:
            draw_skeleton(_blank_frame(), _visible_pose(), player_id=1)
            assert mock_cv2.circle.call_count > 0

    def test_no_lines_when_all_landmarks_invisible(self):
        with patch("camera_input.overlay.cv2") as mock_cv2:
            draw_skeleton(_blank_frame(), _invisible_pose(), player_id=1)
            mock_cv2.line.assert_not_called()

    def test_uses_player_color(self):
        with patch("camera_input.overlay.cv2") as mock_cv2:
            draw_skeleton(_blank_frame(), _visible_pose(), player_id=2)
            # All line calls should use player 2's colour
            color = PLAYER_COLORS[2]
            for c in mock_cv2.line.call_args_list:
                assert c.args[3] == color or c[0][3] == color


# ---------------------------------------------------------------------------
# draw_lane_boundaries tests
# ---------------------------------------------------------------------------

class TestDrawLaneBoundaries:
    def test_returns_same_frame_object(self):
        frame = _blank_frame()
        with patch("camera_input.overlay.cv2"):
            result = draw_lane_boundaries(frame)
        assert result is frame

    def test_draws_vertical_line_at_midpoint(self):
        frame = _blank_frame(h=480, w=640)
        with patch("camera_input.overlay.cv2") as mock_cv2:
            draw_lane_boundaries(frame)
            # The first argument pair in cv2.line should span (mid, 0) → (mid, h)
            mid = 640 // 2
            line_calls = mock_cv2.line.call_args_list
            assert any(
                c.args[1] == (mid, 0) and c.args[2] == (mid, 480)
                or (len(c[0]) >= 3 and c[0][1] == (mid, 0) and c[0][2] == (mid, 480))
                for c in line_calls
            )

    def test_draws_two_labels(self):
        with patch("camera_input.overlay.cv2") as mock_cv2:
            draw_lane_boundaries(_blank_frame())
            assert mock_cv2.putText.call_count == 2


# ---------------------------------------------------------------------------
# draw_player_labels tests
# ---------------------------------------------------------------------------

class TestDrawPlayerLabels:
    def test_returns_same_frame_object(self):
        frame = _blank_frame()
        with patch("camera_input.overlay.cv2"):
            result = draw_player_labels(frame, [])
        assert result is frame

    def test_no_drawing_for_invisible_players(self):
        players = [
            PlayerData(player_id=1, visible=False, x=0.0, y=0.0),
            PlayerData(player_id=2, visible=False, x=0.0, y=0.0),
        ]
        with patch("camera_input.overlay.cv2") as mock_cv2:
            draw_player_labels(_blank_frame(), players)
            mock_cv2.circle.assert_not_called()
            mock_cv2.putText.assert_not_called()

    def test_draws_circle_and_label_for_visible_player(self):
        players = [
            PlayerData(player_id=1, visible=True, x=0.25, y=0.5),
        ]
        with patch("camera_input.overlay.cv2") as mock_cv2:
            draw_player_labels(_blank_frame(), players)
            mock_cv2.circle.assert_called_once()
            mock_cv2.putText.assert_called_once()

    def test_draws_for_each_visible_player(self):
        players = [
            PlayerData(player_id=1, visible=True, x=0.2, y=0.5),
            PlayerData(player_id=2, visible=True, x=0.7, y=0.5),
        ]
        with patch("camera_input.overlay.cv2") as mock_cv2:
            draw_player_labels(_blank_frame(), players)
            assert mock_cv2.circle.call_count == 2
            assert mock_cv2.putText.call_count == 2


# ---------------------------------------------------------------------------
# SKELETON_CONNECTIONS content tests
# ---------------------------------------------------------------------------

class TestSkeletonConnections:
    def test_non_empty(self):
        assert len(SKELETON_CONNECTIONS) > 0

    def test_all_entries_are_name_pairs(self):
        for entry in SKELETON_CONNECTIONS:
            assert len(entry) == 2
            assert isinstance(entry[0], str)
            assert isinstance(entry[1], str)
