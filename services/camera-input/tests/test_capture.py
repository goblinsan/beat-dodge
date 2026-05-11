"""Tests for camera_input.capture (CameraCapture, CameraUnavailableError)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from camera_input.capture import CameraCapture, CameraUnavailableError


class TestCameraCapture:
    def test_raises_when_camera_unavailable(self):
        with patch("camera_input.capture.cv2") as mock_cv2:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = False
            mock_cv2.VideoCapture.return_value = mock_cap

            with pytest.raises(CameraUnavailableError):
                CameraCapture(device=0)

    def test_opens_device_index(self):
        with patch("camera_input.capture.cv2") as mock_cv2:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cv2.VideoCapture.return_value = mock_cap

            CameraCapture(device=2)
            mock_cv2.VideoCapture.assert_called_once_with(2)

    def test_read_frame_returns_frame_on_success(self):
        with patch("camera_input.capture.cv2") as mock_cv2:
            fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (True, fake_frame)
            mock_cv2.VideoCapture.return_value = mock_cap

            capture = CameraCapture()
            ts, frame = capture.read_frame()

            assert isinstance(ts, int)
            assert ts >= 0
            assert frame is fake_frame

    def test_read_frame_returns_none_on_failure(self):
        with patch("camera_input.capture.cv2") as mock_cv2:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_cv2.VideoCapture.return_value = mock_cap

            capture = CameraCapture()
            ts, frame = capture.read_frame()

            assert isinstance(ts, int)
            assert frame is None

    def test_release_calls_cap_release(self):
        with patch("camera_input.capture.cv2") as mock_cv2:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cv2.VideoCapture.return_value = mock_cap

            capture = CameraCapture()
            capture.release()
            mock_cap.release.assert_called_once()

    def test_context_manager_releases_on_exit(self):
        with patch("camera_input.capture.cv2") as mock_cv2:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cv2.VideoCapture.return_value = mock_cap

            with CameraCapture() as capture:
                pass

            mock_cap.release.assert_called_once()

    def test_error_message_mentions_device(self):
        with patch("camera_input.capture.cv2") as mock_cv2:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = False
            mock_cv2.VideoCapture.return_value = mock_cap

            with pytest.raises(CameraUnavailableError, match="3"):
                CameraCapture(device=3)
