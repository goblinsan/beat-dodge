"""Webcam frame capture using OpenCV.

Provides :class:`CameraCapture` for reading frames from a webcam device and
:exc:`CameraUnavailableError` raised when the device cannot be opened.
"""

from __future__ import annotations

import time

import cv2
import numpy as np


class CameraUnavailableError(RuntimeError):
    """Raised when the requested camera device cannot be opened."""


class CameraCapture:
    """Wraps :class:`cv2.VideoCapture` for webcam access.

    Parameters
    ----------
    device:
        Camera device index passed to :func:`cv2.VideoCapture`.
        Defaults to ``0`` (the first available camera).

    Raises
    ------
    CameraUnavailableError
        If the device cannot be opened.
    """

    def __init__(self, device: int = 0) -> None:
        self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():
            raise CameraUnavailableError(
                f"Camera device {device} is not available. "
                "Ensure a webcam is connected and not in use by another application."
            )

    def read_frame(self) -> tuple[int, np.ndarray | None]:
        """Read one frame from the camera.

        Returns
        -------
        tuple[int, np.ndarray | None]
            ``(timestamp_ms, frame)`` where *timestamp_ms* is the current
            monotonic clock in milliseconds and *frame* is a BGR numpy array,
            or ``None`` if the read failed.
        """
        ok, frame = self._cap.read()
        timestamp_ms = int(time.monotonic() * 1000)
        return timestamp_ms, frame if ok else None

    def release(self) -> None:
        """Release the underlying :class:`cv2.VideoCapture` resource."""
        self._cap.release()

    def __enter__(self) -> "CameraCapture":
        return self

    def __exit__(self, *args: object) -> None:
        self.release()
