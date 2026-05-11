"""Movement classification for Beat Dodge camera input.

The classifier turns per-frame pose telemetry into sparse gameplay actions.
It intentionally favors simple, forgiving heuristics over choreography-grade
accuracy: capture a standing baseline, compare current body position against
that baseline, emit the strongest action, then apply a short cooldown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean
from typing import Iterable

from camera_input.detector import LandmarkPoint, PoseResult
from camera_input.players import PlayerData


@dataclass(frozen=True)
class PlayerAction:
    """One gameplay action emitted for a player."""

    id: int
    action: str
    confidence: float


@dataclass(frozen=True)
class PlayerTrackingStatus:
    """Per-player status suitable for camera heartbeat messages."""

    id: int
    visible: bool
    calibrated: bool
    confidence: float


@dataclass
class _Baseline:
    x: float
    hip_y: float
    shoulder_y: float
    nose_y: float


@dataclass
class _PlayerHistory:
    samples: list[_Baseline] = field(default_factory=list)
    baseline: _Baseline | None = None
    last_action_ms: dict[str, int] = field(default_factory=dict)


class MovementClassifier:
    """Classify jump, duck, dodge_left, and dodge_right from pose frames."""

    def __init__(
        self,
        calibration_frames: int = 20,
        min_visibility: float = 0.45,
        min_confidence: float = 0.55,
        jump_threshold: float = 0.055,
        duck_threshold: float = 0.07,
        dodge_threshold: float = 0.075,
        cooldown_ms: int = 450,
    ) -> None:
        self.calibration_frames = max(1, calibration_frames)
        self.min_visibility = min_visibility
        self.min_confidence = min_confidence
        self.jump_threshold = jump_threshold
        self.duck_threshold = duck_threshold
        self.dodge_threshold = dodge_threshold
        self.cooldown_ms = cooldown_ms
        self._players: dict[int, _PlayerHistory] = {
            1: _PlayerHistory(),
            2: _PlayerHistory(),
        }
        self._last_status: list[PlayerTrackingStatus] = [
            PlayerTrackingStatus(id=1, visible=False, calibrated=False, confidence=0.0),
            PlayerTrackingStatus(id=2, visible=False, calibrated=False, confidence=0.0),
        ]

    @property
    def status(self) -> list[PlayerTrackingStatus]:
        """Most recent per-player tracking status."""

        return list(self._last_status)

    def reset_calibration(self, player_id: int | None = None) -> None:
        """Clear calibration for one player, or for both players."""

        ids = [player_id] if player_id is not None else list(self._players.keys())
        for pid in ids:
            self._players[pid] = _PlayerHistory()

    def update(self, timestamp_ms: int, players: Iterable[PlayerData]) -> list[PlayerAction]:
        """Update classifier state and return newly detected actions."""

        actions: list[PlayerAction] = []
        statuses: list[PlayerTrackingStatus] = []

        for player in players:
            history = self._players.setdefault(player.player_id, _PlayerHistory())
            baseline_sample = _baseline_from_player(player, self.min_visibility)
            visible = player.visible and baseline_sample is not None
            landmark_confidence = _visibility_confidence(player.pose, self.min_visibility)

            if not visible:
                statuses.append(
                    PlayerTrackingStatus(
                        id=player.player_id,
                        visible=False,
                        calibrated=history.baseline is not None,
                        confidence=0.0,
                    )
                )
                continue

            if history.baseline is None:
                history.samples.append(baseline_sample)
                if len(history.samples) >= self.calibration_frames:
                    history.baseline = _mean_baseline(history.samples)
                statuses.append(
                    PlayerTrackingStatus(
                        id=player.player_id,
                        visible=True,
                        calibrated=history.baseline is not None,
                        confidence=round(landmark_confidence, 3),
                    )
                )
                continue

            candidates = self._classify_candidates(history.baseline, baseline_sample)
            best_action, best_confidence = self._best_candidate(candidates, landmark_confidence)
            statuses.append(
                PlayerTrackingStatus(
                    id=player.player_id,
                    visible=True,
                    calibrated=True,
                    confidence=round(max(landmark_confidence, best_confidence), 3),
                )
            )

            if best_action == "":
                continue
            last_action_at = history.last_action_ms.get(best_action, -self.cooldown_ms)
            if timestamp_ms - last_action_at < self.cooldown_ms:
                continue

            history.last_action_ms[best_action] = timestamp_ms
            actions.append(
                PlayerAction(
                    id=player.player_id,
                    action=best_action,
                    confidence=round(best_confidence, 3),
                )
            )

        self._last_status = sorted(statuses, key=lambda s: s.id)
        return actions

    def _classify_candidates(
        self,
        baseline: _Baseline,
        current: _Baseline,
    ) -> dict[str, float]:
        jump_delta = baseline.hip_y - current.hip_y
        duck_delta = max(
            current.shoulder_y - baseline.shoulder_y,
            current.nose_y - baseline.nose_y,
            current.hip_y - baseline.hip_y,
        )
        left_delta = baseline.x - current.x
        right_delta = current.x - baseline.x

        return {
            "jump": _score_delta(jump_delta, self.jump_threshold),
            "duck": _score_delta(duck_delta, self.duck_threshold),
            "dodge_left": _score_delta(left_delta, self.dodge_threshold),
            "dodge_right": _score_delta(right_delta, self.dodge_threshold),
        }

    def _best_candidate(
        self,
        candidates: dict[str, float],
        landmark_confidence: float,
    ) -> tuple[str, float]:
        action, motion_confidence = max(candidates.items(), key=lambda item: item[1])
        confidence = motion_confidence * landmark_confidence
        if confidence < self.min_confidence:
            return "", 0.0
        return action, confidence


def action_event_payload(timestamp_ms: int, actions: Iterable[PlayerAction]) -> dict:
    """Build the camera action event payload consumed by the game."""

    return {
        "timestamp_ms": timestamp_ms,
        "players": [
            {
                "id": action.id,
                "action": action.action,
                "confidence": action.confidence,
            }
            for action in actions
        ],
    }


def status_event_payload(timestamp_ms: int, statuses: Iterable[PlayerTrackingStatus]) -> dict:
    """Build a heartbeat/status payload for connected game clients."""

    return {
        "timestamp_ms": timestamp_ms,
        "type": "status",
        "players": [
            {
                "id": status.id,
                "visible": status.visible,
                "calibrated": status.calibrated,
                "confidence": status.confidence,
            }
            for status in statuses
        ],
    }


def _baseline_from_player(player: PlayerData, min_visibility: float) -> _Baseline | None:
    if not player.visible or player.pose is None:
        return None

    pose = player.pose
    hip_y = _avg_landmark_y(pose, ("left_hip", "right_hip"), min_visibility)
    shoulder_y = _avg_landmark_y(pose, ("left_shoulder", "right_shoulder"), min_visibility)
    nose_y = _avg_landmark_y(pose, ("nose",), min_visibility)
    if hip_y is None or shoulder_y is None or nose_y is None:
        return None

    return _Baseline(x=player.x, hip_y=hip_y, shoulder_y=shoulder_y, nose_y=nose_y)


def _avg_landmark_y(
    pose: PoseResult,
    names: tuple[str, ...],
    min_visibility: float,
) -> float | None:
    values = [
        pose.landmarks[name].y
        for name in names
        if name in pose.landmarks and pose.landmarks[name].visibility >= min_visibility
    ]
    if not values:
        return None
    return float(fmean(values))


def _visibility_confidence(pose: PoseResult | None, min_visibility: float) -> float:
    if pose is None or not pose.landmarks:
        return 0.0
    relevant: list[LandmarkPoint] = [
        pose.landmarks[name]
        for name in (
            "nose",
            "left_shoulder",
            "right_shoulder",
            "left_hip",
            "right_hip",
        )
        if name in pose.landmarks
    ]
    if not relevant:
        return 0.0
    raw = fmean(max(0.0, lm.visibility - min_visibility) / (1.0 - min_visibility) for lm in relevant)
    return max(0.0, min(1.0, raw))


def _mean_baseline(samples: list[_Baseline]) -> _Baseline:
    return _Baseline(
        x=float(fmean(sample.x for sample in samples)),
        hip_y=float(fmean(sample.hip_y for sample in samples)),
        shoulder_y=float(fmean(sample.shoulder_y for sample in samples)),
        nose_y=float(fmean(sample.nose_y for sample in samples)),
    )


def _score_delta(delta: float, threshold: float) -> float:
    if delta <= threshold:
        return 0.0
    return max(0.0, min(1.0, delta / (threshold * 2.0)))
