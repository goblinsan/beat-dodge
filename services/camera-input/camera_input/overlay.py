"""Debug skeleton overlay using OpenCV drawing primitives.

Three public functions annotate a BGR frame in-place and return it:

- :func:`draw_skeleton`       — bone connections and landmark dots for one player
- :func:`draw_lane_boundaries` — vertical centre line and player ID labels
- :func:`draw_player_labels`  — body-centre dot and player ID at detected position
"""

from __future__ import annotations

import cv2
import numpy as np

from camera_input.detector import PoseResult
from camera_input.players import PlayerData


#: Bone connections drawn as lines between landmark pairs.
SKELETON_CONNECTIONS: list[tuple[str, str]] = [
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
]

#: BGR colours for Player 1 and Player 2.
PLAYER_COLORS: dict[int, tuple[int, int, int]] = {
    1: (255, 100, 0),   # blue
    2: (0, 165, 255),   # orange
}

#: Minimum landmark visibility to render a point or bone.
_VIS_THRESHOLD: float = 0.3


def draw_skeleton(
    frame: np.ndarray,
    pose: PoseResult | None,
    player_id: int = 1,
) -> np.ndarray:
    """Draw pose skeleton onto *frame* for one player.

    Bone connections and landmark dots are only rendered when both endpoints
    exceed :data:`_VIS_THRESHOLD` visibility.

    Parameters
    ----------
    frame:
        BGR image (modified in-place).
    pose:
        Detected pose for the player, or ``None`` (no-op).
    player_id:
        Used to select the drawing colour from :data:`PLAYER_COLORS`.

    Returns
    -------
    np.ndarray
        The same *frame* object, annotated.
    """
    if pose is None:
        return frame

    h, w = frame.shape[:2]
    color = PLAYER_COLORS.get(player_id, (0, 255, 0))
    lms = pose.landmarks

    # Bone connections
    for start_name, end_name in SKELETON_CONNECTIONS:
        if start_name in lms and end_name in lms:
            s = lms[start_name]
            e = lms[end_name]
            if s.visibility > _VIS_THRESHOLD and e.visibility > _VIS_THRESHOLD:
                pt1 = (int(s.x * w), int(s.y * h))
                pt2 = (int(e.x * w), int(e.y * h))
                cv2.line(frame, pt1, pt2, color, 2)

    # Landmark dots
    for lm in lms.values():
        if lm.visibility > _VIS_THRESHOLD:
            pt = (int(lm.x * w), int(lm.y * h))
            cv2.circle(frame, pt, 4, color, -1)

    return frame


def draw_lane_boundaries(frame: np.ndarray) -> np.ndarray:
    """Draw a vertical centre line dividing Player 1 and Player 2 lanes.

    Also places a lane label ("P1" / "P2") in the top-left of each half.

    Parameters
    ----------
    frame:
        BGR image (modified in-place).

    Returns
    -------
    np.ndarray
        The same *frame* object, annotated.
    """
    h, w = frame.shape[:2]
    mid = w // 2
    cv2.line(frame, (mid, 0), (mid, h), (0, 255, 255), 2)
    cv2.putText(
        frame, "P1", (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 1.0, PLAYER_COLORS[1], 2,
    )
    cv2.putText(
        frame, "P2", (mid + 10, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 1.0, PLAYER_COLORS[2], 2,
    )
    return frame


def draw_player_labels(
    frame: np.ndarray,
    players: list[PlayerData],
) -> np.ndarray:
    """Annotate each visible player's body centre with a dot and ID label.

    Parameters
    ----------
    frame:
        BGR image (modified in-place).
    players:
        List of :class:`~camera_input.players.PlayerData` objects as returned
        by :func:`~camera_input.players.assign_players`.

    Returns
    -------
    np.ndarray
        The same *frame* object, annotated.
    """
    h, w = frame.shape[:2]
    for player in players:
        if not player.visible:
            continue
        color = PLAYER_COLORS.get(player.player_id, (0, 255, 0))
        cx = int(player.x * w)
        cy = int(player.y * h)
        cv2.circle(frame, (cx, cy), 8, color, -1)
        cv2.putText(
            frame, f"P{player.player_id}", (cx + 10, cy),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2,
        )
    return frame
