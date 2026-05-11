"""Course generation: convert song analysis into a Beat Dodge course JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any

#: Kid-friendly movement actions a player can perform.
MOVES: list[str] = ["dodge_left", "dodge_right", "jump", "duck"]

#: The two players supported by the game.
PLAYERS: list[str] = ["player_1", "player_2"]

DIFFICULTIES: tuple[str, ...] = ("easy", "normal", "hard")


@dataclass(frozen=True)
class DifficultySettings:
    """Course density and move-palette settings for one difficulty."""

    name: str
    low_energy_stride: int
    medium_energy_stride: int
    high_energy_stride: int
    moves: tuple[str, ...]
    min_same_player_gap_seconds: float
    min_jump_gap_seconds: float
    min_jump_duck_gap_seconds: float
    min_dodge_flip_gap_seconds: float


DIFFICULTY_SETTINGS: dict[str, DifficultySettings] = {
    "easy": DifficultySettings(
        name="easy",
        low_energy_stride=5,
        medium_energy_stride=4,
        high_energy_stride=3,
        moves=("jump", "duck"),
        min_same_player_gap_seconds=1.2,
        min_jump_gap_seconds=2.0,
        min_jump_duck_gap_seconds=1.6,
        min_dodge_flip_gap_seconds=1.2,
    ),
    "normal": DifficultySettings(
        name="normal",
        low_energy_stride=4,
        medium_energy_stride=3,
        high_energy_stride=2,
        moves=("jump", "duck", "dodge_left", "dodge_right"),
        min_same_player_gap_seconds=0.9,
        min_jump_gap_seconds=1.5,
        min_jump_duck_gap_seconds=1.2,
        min_dodge_flip_gap_seconds=0.9,
    ),
    "hard": DifficultySettings(
        name="hard",
        low_energy_stride=3,
        medium_energy_stride=2,
        high_energy_stride=1,
        moves=("jump", "duck", "dodge_left", "dodge_right"),
        min_same_player_gap_seconds=0.45,
        min_jump_gap_seconds=1.0,
        min_jump_duck_gap_seconds=0.8,
        min_dodge_flip_gap_seconds=0.6,
    ),
}


@dataclass
class MovementPrompt:
    """Internal model for a single movement prompt.

    Attributes
    ----------
    time_seconds:
        Beat-aligned timestamp at which the player should perform the move.
    player:
        Target player identifier (``"player_1"`` or ``"player_2"``).
    move:
        Kid-friendly action the player must perform (e.g. ``"dodge_left"``).
    intensity:
        Energy-derived difficulty level in the range **1–5**.
    metadata:
        Optional context retained for debugging / future extensions
        (e.g. the originating beat index).
    """

    time_seconds: float
    player: str
    move: str
    intensity: int
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _energy_level_at(
    time_seconds: float,
    energy_windows: list[dict[str, Any]],
) -> int:
    """Return the energy level for the window containing *time_seconds*.

    Falls back to the last window when *time_seconds* is at or beyond the
    end of the last window.  Returns ``1`` if *energy_windows* is empty.
    """
    for window in energy_windows:
        if window["start_seconds"] <= time_seconds < window["end_seconds"]:
            return int(window["level"])
    if energy_windows:
        return int(energy_windows[-1]["level"])
    return 1


def _settings_for(difficulty: str) -> DifficultySettings:
    try:
        return DIFFICULTY_SETTINGS[difficulty]
    except KeyError as exc:
        valid = ", ".join(DIFFICULTIES)
        raise ValueError(f"Unknown difficulty {difficulty!r}; expected one of: {valid}") from exc


def _stride_for_energy(level: int, settings: DifficultySettings) -> int:
    if level >= 4:
        return settings.high_energy_stride
    if level <= 2:
        return settings.low_energy_stride
    return settings.medium_energy_stride


def _move_allowed(
    move: str,
    player: str,
    beat_time: float,
    player_last_prompt: dict[str, MovementPrompt],
    settings: DifficultySettings,
) -> bool:
    previous = player_last_prompt.get(player)
    if previous is None:
        return True

    gap = beat_time - previous.time_seconds
    if gap < settings.min_same_player_gap_seconds:
        return False
    if move == "jump" and previous.move == "jump" and gap < settings.min_jump_gap_seconds:
        return False
    if {move, previous.move} == {"jump", "duck"} and gap < settings.min_jump_duck_gap_seconds:
        return False
    if (
        move in {"dodge_left", "dodge_right"}
        and previous.move in {"dodge_left", "dodge_right"}
        and move != previous.move
        and gap < settings.min_dodge_flip_gap_seconds
    ):
        return False
    return True


def _choose_move(
    candidate_moves: list[str],
    player: str,
    beat_time: float,
    player_last_prompt: dict[str, MovementPrompt],
    settings: DifficultySettings,
) -> str:
    for move in candidate_moves:
        if _move_allowed(move, player, beat_time, player_last_prompt, settings):
            return move
    previous = player_last_prompt.get(player)
    if previous is not None and previous.move in candidate_moves:
        return previous.move
    return candidate_moves[0]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def beats_to_prompts(
    beats: list[float],
    energy_windows: list[dict[str, Any]],
    difficulty: str = "normal",
    seed: int | None = None,
) -> list[MovementPrompt]:
    """Convert beat timestamps into balanced two-player movement prompts.

    Density is difficulty- and energy-aware.  Low-energy windows skip more
    beats, high-energy windows allow denser prompts.  Per-player movement rules
    avoid the most obvious physically frustrating chains for kids.
    """
    settings = _settings_for(difficulty)
    rng = random.Random(seed)
    prompts: list[MovementPrompt] = []
    player_last_prompt: dict[str, MovementPrompt] = {}

    for i, beat_time in enumerate(beats):
        energy_level = _energy_level_at(beat_time, energy_windows)
        stride = _stride_for_energy(energy_level, settings)
        if i % stride != 0:
            continue

        player = PLAYERS[len(prompts) % len(PLAYERS)]
        candidate_moves = list(settings.moves)
        if seed is None:
            rotation = (i + len(prompts)) % len(candidate_moves)
            candidate_moves = candidate_moves[rotation:] + candidate_moves[:rotation]
        else:
            rng.shuffle(candidate_moves)

        move = _choose_move(candidate_moves, player, beat_time, player_last_prompt, settings)
        prompt = MovementPrompt(
            time_seconds=beat_time,
            player=player,
            move=move,
            intensity=energy_level,
            metadata={"beat_index": i, "difficulty": difficulty, "stride": stride},
        )
        prompts.append(
            prompt
        )
        player_last_prompt[player] = prompt
    return prompts


def generate_course(
    analysis: dict[str, Any],
    difficulty: str = "normal",
    seed: int | None = None,
) -> dict[str, Any]:
    """Generate a course document from a song analysis dict.

    Parameters
    ----------
    analysis:
        The dict returned by ``song_analyzer.analyzer.analyze()``.  Must
        contain ``source``, ``bpm``, ``duration_seconds``, ``beats``, and
        ``energy_windows``.

    Returns
    -------
    dict
        A course document that conforms to
        ``docs/schemas/course.schema.json`` with ``version``, ``song``,
        and ``events`` fields.  Each event carries ``time_seconds``,
        ``player``, ``move``, and ``intensity``.
    """
    _settings_for(difficulty)
    prompts = beats_to_prompts(analysis["beats"], analysis["energy_windows"], difficulty, seed)
    events = [
        {
            "time_seconds": p.time_seconds,
            "player": p.player,
            "move": p.move,
            "intensity": p.intensity,
        }
        for p in prompts
    ]
    return {
        "version": "1.0.0",
        "difficulty": difficulty,
        "song": {
            "id": analysis["source"],
            "bpm": analysis["bpm"],
            "duration_seconds": analysis["duration_seconds"],
        },
        "events": events,
    }
