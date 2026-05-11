"""Course generation: convert song analysis into a Beat Dodge course JSON.

Two public interfaces
---------------------
beats_to_prompts(beats, energy_windows) -> list[MovementPrompt]
    Convert raw beat timestamps and energy data into an ordered list of
    movement prompts, alternating between the two players and cycling through
    the supported kid-friendly moves.

generate_course(analysis) -> dict
    Wrap the full pipeline: take the dict produced by
    ``song_analyzer.analyzer.analyze()`` and return a course document that
    conforms to ``docs/schemas/course.schema.json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Kid-friendly movement actions a player can perform.
MOVES: list[str] = ["dodge_left", "dodge_right", "jump", "duck"]

#: The two players supported by the game.
PLAYERS: list[str] = ["player_1", "player_2"]


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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def beats_to_prompts(
    beats: list[float],
    energy_windows: list[dict[str, Any]],
) -> list[MovementPrompt]:
    """Convert beat timestamps into balanced two-player movement prompts.

    Assignment rules
    ~~~~~~~~~~~~~~~~
    - **Players** alternate on every beat (even index → player_1, odd → player_2).
    - **Moves** cycle through :data:`MOVES` in order, giving each player a
      variety of kid-friendly actions rather than repeating the same move.
    - **Intensity** is the energy level of the 1-second window that contains
      the beat timestamp.

    Parameters
    ----------
    beats:
        Ordered list of beat timestamps (seconds) from song analysis.
    energy_windows:
        List of energy-window dicts from song analysis, each containing
        ``start_seconds``, ``end_seconds``, and ``level``.

    Returns
    -------
    list[MovementPrompt]
        One prompt per beat, in chronological order.
    """
    prompts: list[MovementPrompt] = []
    for i, beat_time in enumerate(beats):
        prompts.append(
            MovementPrompt(
                time_seconds=beat_time,
                player=PLAYERS[i % len(PLAYERS)],
                move=MOVES[i % len(MOVES)],
                intensity=_energy_level_at(beat_time, energy_windows),
                metadata={"beat_index": i},
            )
        )
    return prompts


def generate_course(analysis: dict[str, Any]) -> dict[str, Any]:
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
    prompts = beats_to_prompts(
        analysis["beats"],
        analysis["energy_windows"],
    )
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
        "song": {
            "id": analysis["source"],
            "bpm": analysis["bpm"],
            "duration_seconds": analysis["duration_seconds"],
        },
        "events": events,
    }
