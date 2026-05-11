"""MediaPipe pose detection and landmark extraction.

Provides :class:`PoseDetector` which runs MediaPipe Pose independently on
the left and right halves of a frame, enabling two-player tracking.

Named landmark constants (``REQUIRED_LANDMARKS``) cover all joints needed
for the MVP movement classification: head, shoulders, hips, knees, ankles,
elbows, and wrists.

MediaPipe is imported lazily inside :class:`PoseDetector` so that the module
can be loaded and tested without instantiating a live detector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

#: Ordered mapping of human-readable name → MediaPipe BlazePose landmark index.
#: Indices follow the standard 33-point BlazePose topology and are stable
#: across MediaPipe versions.  Using integer literals avoids a module-level
#: ``import mediapipe`` so that the module can be imported without a
#: working MediaPipe installation (e.g. during unit tests with mocks).
REQUIRED_LANDMARKS: dict[str, int] = {
    "nose": 0,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}


@dataclass
class LandmarkPoint:
    """Normalised position and visibility for a single body landmark.

    Attributes
    ----------
    x:
        Horizontal position normalised to the **full frame** width (0–1).
    y:
        Vertical position normalised to the frame height (0–1).
    visibility:
        MediaPipe confidence score (0–1).
    """

    x: float
    y: float
    visibility: float


@dataclass
class PoseResult:
    """Detected pose landmarks for one player in one frame.

    Attributes
    ----------
    landmarks:
        Mapping of landmark name (from :data:`REQUIRED_LANDMARKS`) to its
        normalised position and visibility.
    """

    landmarks: dict[str, LandmarkPoint] = field(default_factory=dict)


class PoseDetector:
    """Detects body pose landmarks using MediaPipe Pose.

    The frame is split vertically at the midpoint.  An independent
    :class:`mediapipe.solutions.pose.Pose` instance processes each half so
    that two players can be tracked simultaneously without interference.

    Parameters
    ----------
    min_detection_confidence:
        Minimum confidence for the initial person detection (0–1).
    min_tracking_confidence:
        Minimum confidence for landmark tracking between frames (0–1).
    """

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        import mediapipe as mp  # lazy import — keeps module importable without mediapipe

        mp_pose = mp.solutions.pose
        self._left_pose = mp_pose.Pose(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._right_pose = mp_pose.Pose(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self, frame: np.ndarray
    ) -> tuple[PoseResult | None, PoseResult | None]:
        """Detect poses in the left and right halves of *frame*.

        Parameters
        ----------
        frame:
            BGR image as returned by :func:`cv2.VideoCapture.read`.

        Returns
        -------
        tuple[PoseResult | None, PoseResult | None]
            ``(left_result, right_result)``.  Either value is ``None`` when
            no person is detected in that half.
        """
        _h, w = frame.shape[:2]
        mid = w // 2

        left_half = frame[:, :mid]
        right_half = frame[:, mid:]

        left_rgb = cv2.cvtColor(left_half, cv2.COLOR_BGR2RGB)
        right_rgb = cv2.cvtColor(right_half, cv2.COLOR_BGR2RGB)

        left_result = self._process_half(
            self._left_pose, left_rgb, x_offset=0.0, x_scale=0.5
        )
        right_result = self._process_half(
            self._right_pose, right_rgb, x_offset=0.5, x_scale=0.5
        )
        return left_result, right_result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _process_half(
        pose: Any,
        rgb_frame: np.ndarray,
        x_offset: float,
        x_scale: float,
    ) -> PoseResult | None:
        """Run *pose* on *rgb_frame* and map landmark x coordinates to the
        full-frame coordinate space.

        Parameters
        ----------
        pose:
            A :class:`mediapipe.solutions.pose.Pose` instance.
        rgb_frame:
            RGB half-frame image.
        x_offset:
            Horizontal offset to add after scaling (0.0 for left, 0.5 for right).
        x_scale:
            Scale factor applied to the per-half x coordinate (0.5 for both halves).
        """
        results = pose.process(rgb_frame)
        if not results.pose_landmarks:
            return None

        lms = results.pose_landmarks.landmark
        points: dict[str, LandmarkPoint] = {}
        for name, idx in REQUIRED_LANDMARKS.items():
            lm = lms[idx]
            points[name] = LandmarkPoint(
                x=round(x_offset + float(lm.x) * x_scale, 4),
                y=round(float(lm.y), 4),
                visibility=round(float(lm.visibility), 4),
            )
        return PoseResult(landmarks=points)

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release MediaPipe resources for both pose estimators."""
        self._left_pose.close()
        self._right_pose.close()

    def __enter__(self) -> "PoseDetector":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
