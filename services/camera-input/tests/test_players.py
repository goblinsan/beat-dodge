"""Tests for camera_input.players (PlayerData, assign_players)."""

from __future__ import annotations

import pytest

from camera_input.detector import LandmarkPoint, PoseResult
from camera_input.players import PlayerData, assign_players, _body_center


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pose(landmarks: dict[str, tuple[float, float, float]]) -> PoseResult:
    """Build a PoseResult from (x, y, visibility) tuples."""
    return PoseResult(
        landmarks={
            name: LandmarkPoint(x=x, y=y, visibility=vis)
            for name, (x, y, vis) in landmarks.items()
        }
    )


def _hip_pose(left_x: float = 0.2, right_x: float = 0.3, y: float = 0.6) -> PoseResult:
    return _make_pose({
        "left_hip": (left_x, y, 0.9),
        "right_hip": (right_x, y, 0.9),
    })


# ---------------------------------------------------------------------------
# _body_center tests
# ---------------------------------------------------------------------------

class TestBodyCenter:
    def test_uses_hip_midpoint_when_available(self):
        pose = _hip_pose(left_x=0.2, right_x=0.4, y=0.6)
        x, y = _body_center(pose)
        assert abs(x - 0.3) < 1e-4
        assert abs(y - 0.6) < 1e-4

    def test_falls_back_to_centroid_without_hips(self):
        pose = _make_pose({
            "nose": (0.1, 0.1, 0.8),
            "left_shoulder": (0.3, 0.5, 0.9),
        })
        x, y = _body_center(pose)
        assert abs(x - 0.2) < 1e-4
        assert abs(y - 0.3) < 1e-4

    def test_returns_zero_zero_for_empty_pose(self):
        pose = PoseResult()
        assert _body_center(pose) == (0.0, 0.0)

    def test_single_hip_uses_that_value(self):
        pose = _make_pose({"left_hip": (0.25, 0.55, 0.9)})
        x, y = _body_center(pose)
        assert abs(x - 0.25) < 1e-4
        assert abs(y - 0.55) < 1e-4


# ---------------------------------------------------------------------------
# assign_players tests
# ---------------------------------------------------------------------------

class TestAssignPlayers:
    def test_returns_exactly_two_players(self):
        result = assign_players(None, None)
        assert len(result) == 2

    def test_player_ids_are_1_and_2(self):
        result = assign_players(None, None)
        assert result[0].player_id == 1
        assert result[1].player_id == 2

    def test_both_invisible_when_no_poses(self):
        result = assign_players(None, None)
        assert result[0].visible is False
        assert result[1].visible is False

    def test_invisible_players_have_zero_coords(self):
        result = assign_players(None, None)
        for p in result:
            assert p.x == 0.0
            assert p.y == 0.0

    def test_player1_visible_when_left_pose_detected(self):
        left = _hip_pose()
        result = assign_players(left, None)
        assert result[0].visible is True
        assert result[1].visible is False

    def test_player2_visible_when_right_pose_detected(self):
        right = _hip_pose()
        result = assign_players(None, right)
        assert result[0].visible is False
        assert result[1].visible is True

    def test_both_visible_when_both_poses_detected(self):
        left = _hip_pose(left_x=0.1, right_x=0.2)
        right = _hip_pose(left_x=0.6, right_x=0.7)
        result = assign_players(left, right)
        assert result[0].visible is True
        assert result[1].visible is True

    def test_player1_body_center_matches_left_pose(self):
        left = _hip_pose(left_x=0.1, right_x=0.3, y=0.6)
        result = assign_players(left, None)
        p1 = result[0]
        assert abs(p1.x - 0.2) < 1e-4
        assert abs(p1.y - 0.6) < 1e-4

    def test_player2_body_center_matches_right_pose(self):
        right = _hip_pose(left_x=0.6, right_x=0.8, y=0.55)
        result = assign_players(None, right)
        p2 = result[1]
        assert abs(p2.x - 0.7) < 1e-4
        assert abs(p2.y - 0.55) < 1e-4

    def test_result_contains_player_data_instances(self):
        result = assign_players(None, None)
        for item in result:
            assert isinstance(item, PlayerData)

    def test_x_and_y_are_floats(self):
        left = _hip_pose()
        result = assign_players(left, None)
        for p in result:
            assert isinstance(p.x, float)
            assert isinstance(p.y, float)
