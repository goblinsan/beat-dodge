"""Tests for camera_input.movement."""

from __future__ import annotations

from camera_input.detector import LandmarkPoint, PoseResult
from camera_input.movement import MovementClassifier, action_event_payload
from camera_input.players import PlayerData


def _pose(
    *,
    x: float = 0.25,
    hip_y: float = 0.55,
    shoulder_y: float = 0.32,
    nose_y: float = 0.18,
    visibility: float = 0.95,
) -> PoseResult:
    return PoseResult(
        landmarks={
            "nose": LandmarkPoint(x=x, y=nose_y, visibility=visibility),
            "left_shoulder": LandmarkPoint(x=x - 0.05, y=shoulder_y, visibility=visibility),
            "right_shoulder": LandmarkPoint(x=x + 0.05, y=shoulder_y, visibility=visibility),
            "left_hip": LandmarkPoint(x=x - 0.04, y=hip_y, visibility=visibility),
            "right_hip": LandmarkPoint(x=x + 0.04, y=hip_y, visibility=visibility),
        }
    )


def _player(player_id: int = 1, *, x: float = 0.25, pose: PoseResult | None = None) -> PlayerData:
    return PlayerData(
        player_id=player_id,
        visible=pose is not None,
        x=x,
        y=0.55,
        pose=pose,
    )


def _calibrated_classifier() -> MovementClassifier:
    classifier = MovementClassifier(calibration_frames=2, cooldown_ms=0)
    classifier.update(0, [_player(pose=_pose())])
    classifier.update(16, [_player(pose=_pose())])
    return classifier


def test_calibrates_before_emitting_actions():
    classifier = MovementClassifier(calibration_frames=2)
    actions = classifier.update(0, [_player(pose=_pose(hip_y=0.45))])
    assert actions == []
    assert classifier.status[0].calibrated is False


def test_detects_jump_from_upward_hip_motion():
    classifier = _calibrated_classifier()
    actions = classifier.update(100, [_player(pose=_pose(hip_y=0.43))])
    assert actions[0].action == "jump"
    assert actions[0].confidence >= 0.55


def test_detects_duck_from_downward_body_motion():
    classifier = _calibrated_classifier()
    actions = classifier.update(100, [_player(pose=_pose(hip_y=0.65, shoulder_y=0.44, nose_y=0.31))])
    assert actions[0].action == "duck"


def test_detects_dodge_left_from_body_center_shift():
    classifier = _calibrated_classifier()
    actions = classifier.update(100, [_player(x=0.12, pose=_pose(x=0.12))])
    assert actions[0].action == "dodge_left"


def test_detects_dodge_right_from_body_center_shift():
    classifier = _calibrated_classifier()
    actions = classifier.update(100, [_player(x=0.38, pose=_pose(x=0.38))])
    assert actions[0].action == "dodge_right"


def test_low_visibility_does_not_emit():
    classifier = _calibrated_classifier()
    actions = classifier.update(100, [_player(pose=_pose(hip_y=0.43, visibility=0.2))])
    assert actions == []


def test_action_payload_shape():
    classifier = _calibrated_classifier()
    actions = classifier.update(100, [_player(pose=_pose(hip_y=0.43))])
    payload = action_event_payload(100, actions)
    assert payload["timestamp_ms"] == 100
    assert payload["players"][0]["id"] == 1
    assert payload["players"][0]["action"] == "jump"
