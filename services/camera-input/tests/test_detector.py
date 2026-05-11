"""Tests for camera_input.detector (PoseDetector, PoseResult, LandmarkPoint)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from camera_input.detector import (
    LandmarkPoint,
    PoseDetector,
    PoseResult,
    REQUIRED_LANDMARKS,
)


# ---------------------------------------------------------------------------
# Data-class tests (no external dependencies)
# ---------------------------------------------------------------------------

class TestLandmarkPoint:
    def test_stores_xyz_visibility(self):
        lm = LandmarkPoint(x=0.3, y=0.6, visibility=0.9)
        assert lm.x == 0.3
        assert lm.y == 0.6
        assert lm.visibility == 0.9


class TestPoseResult:
    def test_empty_by_default(self):
        pr = PoseResult()
        assert pr.landmarks == {}

    def test_stores_landmarks(self):
        lm = LandmarkPoint(x=0.1, y=0.2, visibility=0.8)
        pr = PoseResult(landmarks={"nose": lm})
        assert pr.landmarks["nose"] is lm


class TestRequiredLandmarks:
    def test_all_expected_names_present(self):
        expected = {
            "nose",
            "left_shoulder", "right_shoulder",
            "left_hip", "right_hip",
            "left_knee", "right_knee",
            "left_ankle", "right_ankle",
            "left_elbow", "right_elbow",
            "left_wrist", "right_wrist",
        }
        assert set(REQUIRED_LANDMARKS.keys()) == expected

    def test_values_are_integers(self):
        for name, idx in REQUIRED_LANDMARKS.items():
            assert isinstance(int(idx), int), f"{name} index should be integer-like"


# ---------------------------------------------------------------------------
# PoseDetector tests (MediaPipe mocked)
# ---------------------------------------------------------------------------

def _make_fake_landmark(x: float = 0.5, y: float = 0.5, vis: float = 0.9) -> MagicMock:
    lm = MagicMock()
    lm.x = x
    lm.y = y
    lm.visibility = vis
    return lm


def _make_pose_landmarks(num_landmarks: int = 33) -> MagicMock:
    """Return a mock pose_landmarks with *num_landmarks* fake landmark entries."""
    lms = MagicMock()
    lms.__getitem__ = lambda self, idx: _make_fake_landmark(
        x=0.4 + idx * 0.001,
        y=0.5,
        vis=0.95,
    )
    return lms


class TestPoseDetector:
    def _make_detector_with_mock_mp(self, left_detected: bool, right_detected: bool):
        """Build a PoseDetector whose underlying MediaPipe instances are mocked.

        Bypasses ``__init__`` so no mediapipe import is required at test time.
        """
        mock_left_result = MagicMock()
        mock_left_result.pose_landmarks = (
            _make_pose_landmarks() if left_detected else None
        )
        mock_right_result = MagicMock()
        mock_right_result.pose_landmarks = (
            _make_pose_landmarks() if right_detected else None
        )

        mock_left_pose = MagicMock()
        mock_left_pose.process.return_value = mock_left_result
        mock_right_pose = MagicMock()
        mock_right_pose.process.return_value = mock_right_result

        # Bypass __init__ to avoid importing mediapipe; inject mocks directly.
        detector = object.__new__(PoseDetector)
        detector._left_pose = mock_left_pose
        detector._right_pose = mock_right_pose
        return detector

    def test_detect_returns_two_values(self):
        detector = self._make_detector_with_mock_mp(True, True)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("camera_input.detector.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = frame
            result = detector.detect(frame)
        assert len(result) == 2

    def test_detect_none_when_no_person(self):
        detector = self._make_detector_with_mock_mp(False, False)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("camera_input.detector.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = frame
            left, right = detector.detect(frame)
        assert left is None
        assert right is None

    def test_detect_pose_result_when_person_detected(self):
        detector = self._make_detector_with_mock_mp(True, False)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("camera_input.detector.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = frame
            left, right = detector.detect(frame)
        assert isinstance(left, PoseResult)
        assert right is None

    def test_left_landmarks_x_in_first_half(self):
        """Left-half landmarks must have x in [0, 0.5]."""
        detector = self._make_detector_with_mock_mp(True, False)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("camera_input.detector.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = frame
            left, _ = detector.detect(frame)
        assert left is not None
        for name, lm in left.landmarks.items():
            assert 0.0 <= lm.x <= 0.5, f"{name}.x={lm.x} out of [0, 0.5]"

    def test_right_landmarks_x_in_second_half(self):
        """Right-half landmarks must have x in [0.5, 1.0]."""
        detector = self._make_detector_with_mock_mp(False, True)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("camera_input.detector.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = frame
            _, right = detector.detect(frame)
        assert right is not None
        for name, lm in right.landmarks.items():
            assert 0.5 <= lm.x <= 1.0, f"{name}.x={lm.x} out of [0.5, 1.0]"

    def test_context_manager_calls_close(self):
        detector = self._make_detector_with_mock_mp(False, False)
        with detector:
            pass
        detector._left_pose.close.assert_called_once()
        detector._right_pose.close.assert_called_once()
