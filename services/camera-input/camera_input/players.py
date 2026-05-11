"""Player assignment by left/right lane.

Provides :class:`PlayerData` and :func:`assign_players` which map left-half
and right-half :class:`~camera_input.detector.PoseResult` objects to the two
Beat Dodge players (Player 1 = left lane, Player 2 = right lane).

The normalised body-centre position is derived from the hip midpoint when
both hip landmarks are available, falling back to the centroid of all
detected landmarks.
"""

from __future__ import annotations

from dataclasses import dataclass

from camera_input.detector import PoseResult


@dataclass
class PlayerData:
    """Normalised position and visibility for one player in one frame.

    Attributes
    ----------
    player_id:
        ``1`` for the left-lane player or ``2`` for the right-lane player.
    visible:
        ``True`` when a person was detected in this player's lane.
    x:
        Normalised horizontal body-centre position (0–1, full frame).
    y:
        Normalised vertical body-centre position (0–1, full frame).
    """

    player_id: int
    visible: bool
    x: float
    y: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _body_center(pose: PoseResult) -> tuple[float, float]:
    """Compute the body centre as the midpoint of the hip landmarks.

    Falls back to the centroid of all available landmarks when hip landmarks
    are absent.

    Parameters
    ----------
    pose:
        A detected :class:`~camera_input.detector.PoseResult`.

    Returns
    -------
    tuple[float, float]
        ``(x, y)`` in normalised full-frame coordinates (0–1).
    """
    lms = pose.landmarks
    hip_names = ("left_hip", "right_hip")
    xs = [lms[n].x for n in hip_names if n in lms]
    ys = [lms[n].y for n in hip_names if n in lms]
    if xs and ys:
        return round(sum(xs) / len(xs), 4), round(sum(ys) / len(ys), 4)

    # Fallback: centroid of all landmarks
    all_x = [lm.x for lm in lms.values()]
    all_y = [lm.y for lm in lms.values()]
    if all_x and all_y:
        return round(sum(all_x) / len(all_x), 4), round(sum(all_y) / len(all_y), 4)
    return 0.0, 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assign_players(
    left_pose: PoseResult | None,
    right_pose: PoseResult | None,
) -> list[PlayerData]:
    """Assign Player 1 to the left lane and Player 2 to the right lane.

    Both players are always represented in the returned list.  When no person
    is detected in a lane, the corresponding :class:`PlayerData` has
    ``visible=False`` and ``x=y=0.0``.

    Parameters
    ----------
    left_pose:
        Pose detected in the left half of the frame, or ``None``.
    right_pose:
        Pose detected in the right half of the frame, or ``None``.

    Returns
    -------
    list[PlayerData]
        Always exactly two elements: ``[player_1_data, player_2_data]``.
    """
    players: list[PlayerData] = []

    if left_pose is not None:
        x, y = _body_center(left_pose)
        players.append(PlayerData(player_id=1, visible=True, x=x, y=y))
    else:
        players.append(PlayerData(player_id=1, visible=False, x=0.0, y=0.0))

    if right_pose is not None:
        x, y = _body_center(right_pose)
        players.append(PlayerData(player_id=2, visible=True, x=x, y=y))
    else:
        players.append(PlayerData(player_id=2, visible=False, x=0.0, y=0.0))

    return players
